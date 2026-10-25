"""SYN skill-transfer evaluator v0: deterministic, offline and read-only.

Scores externally produced agent answers against a separate fixed oracle.
This code neither runs an LLM nor certifies oracle independence or a real AGI.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

SCHEMA = "syn-skill-transfer-eval-v0"
ARMS = ("baseline", "journal", "research", "skills")
MAX_BYTES = 2_000_000
MAX_TASKS = 10_000


class EvaluationError(ValueError):
    """Badly formed input or a non-comparable evaluation."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise EvaluationError(message)


def _read_json(path: Path) -> Any:
    _require(path.is_file() and not path.is_symlink(), "invalid file path")
    _require(path.stat().st_size <= MAX_BYTES, "file exceeds size cap")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise EvaluationError("invalid JSON") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    _require(path.is_file() and not path.is_symlink(), "invalid file path")
    _require(path.stat().st_size <= MAX_BYTES, "file exceeds size cap")
    items = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                _require(len(items) < MAX_TASKS * len(ARMS), "too many records")
                _require(bool(line.strip()), "blank JSONL line")
                item = json.loads(line)
                _require(isinstance(item, dict), "record must be an object")
                items.append(item)
    except (ValueError, UnicodeError) as exc:
        raise EvaluationError("invalid JSONL") from exc
    return items


def _str(value: Any, what: str) -> str:
    _require(isinstance(value, str) and 0 < len(value) <= 300 and value.strip() == value, f"bad {what}")
    return value


def _nonneg_int(value: Any, what: str) -> int:
    _require(type(value) is int and 0 <= value <= 100_000_000, f"bad {what}")
    return value


def evaluate(manifest: dict[str, Any], truth: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Exact-match paired evaluation, no model/network/hidden-test access.

    Claims only about supplied artifacts; truthful external outcomes and
    experiment pre-registration remain a separate independent responsibility.
    """
    _require(isinstance(manifest, dict), "manifest must be an object")
    required = {"schema", "study_id", "model_id", "arms", "train_task_ids", "test_tasks", "token_budget_per_arm"}
    _require(set(manifest) == required and manifest["schema"] == SCHEMA, "bad manifest schema")
    study_id = _str(manifest["study_id"], "study_id")
    model = _str(manifest["model_id"], "model_id")
    _require(manifest["arms"] == list(ARMS), "arms must contain exactly the four specified conditions")
    budget = _nonneg_int(manifest["token_budget_per_arm"], "token budget")
    train = manifest["train_task_ids"]
    _require(isinstance(train, list) and all(isinstance(x, str) and x.strip() for x in train) and len(set(train)) == len(train), "bad train IDs")
    tasks = manifest["test_tasks"]
    _require(isinstance(tasks, list) and 1 <= len(tasks) <= MAX_TASKS, "bad test task list")
    domain_by_task: dict[str, str] = {}
    for task in tasks:
        _require(isinstance(task, dict) and set(task) == {"task_id", "domain"}, "bad task object")
        task_id, domain = _str(task["task_id"], "task_id"), _str(task["domain"], "domain")
        _require(task_id not in domain_by_task, "duplicate test task")
        domain_by_task[task_id] = domain
    _require(not set(train).intersection(domain_by_task), "train/test leakage: overlapping IDs")
    _require(len(set(domain_by_task.values())) >= 2, "two test domains required")

    truth_map: dict[str, str] = {}
    for row in truth:
        _require(isinstance(row, dict) and set(row) == {"task_id", "answer"}, "bad oracle record")
        tid = _str(row["task_id"], "oracle ID")
        _require(tid in domain_by_task and tid not in truth_map, "unknown or repeated oracle ID")
        truth_map[tid] = _str(row["answer"], "oracle answer")
    _require(set(truth_map) == set(domain_by_task), "incomplete oracle")

    results: dict[tuple[str, str], bool] = {}
    token_totals = dict.fromkeys(ARMS, 0)
    seen_skills: dict[str, set[str]] = defaultdict(set)
    for row in attempts:
        _require(isinstance(row, dict) and set(row) == {"task_id", "arm", "model_id", "answer", "tokens_used", "skill_ids"}, "bad attempt schema")
        tid = _str(row["task_id"], "attempt task ID")
        arm = row["arm"]
        _require(tid in domain_by_task and arm in ARMS, "unknown task or arm")
        _require(row["model_id"] == model, "model identity differs between arms")
        answer = _str(row["answer"], "agent answer")
        tokens = _nonneg_int(row["tokens_used"], "tokens_used")
        skills = row["skill_ids"]
        _require(isinstance(skills, list) and all(isinstance(x, str) and x.strip() for x in skills) and len(set(skills)) == len(skills), "bad skill IDs")
        _require(arm in ("research", "skills") or len(skills) == 0, "skills declared outside skill-enabled arm")
        key = tid, arm
        _require(key not in results, "duplicate result for task and arm")
        results[key] = answer == truth_map[tid]
        token_totals[arm] += tokens
        for skill in skills:
            seen_skills[skill].add(domain_by_task[tid])
    _require(len(results) == len(domain_by_task) * len(ARMS), "all tasks must have all four paired arms")
    _require(all(total <= budget for total in token_totals.values()), "arm exceeded registered token budget")
    by_domain = {d: sorted(t for t, dom in domain_by_task.items() if dom == d) for d in sorted(set(domain_by_task.values()))}
    sorted_ids = sorted(domain_by_task)
    counts = {arm: sum(results[(t, arm)] for t in sorted_ids) for arm in ARMS}
    summary = {}
    for arm in ARMS:
        summary[arm] = {"passed": counts[arm], "total": len(sorted_ids), "pass_rate": counts[arm] / len(sorted_ids), "tokens_used": token_totals[arm]}
    delta_by_domain = {}
    for domain, domain_tasks in by_domain.items():
        delta_by_domain[domain] = {arm: round(sum(results[(t, arm)] for t in domain_tasks) / len(domain_tasks), 8) for arm in ARMS}
    harmed = [t for t in sorted_ids if results[(t, "baseline")] and not results[(t, "skills")]]
    repaired = [t for t in sorted_ids if not results[(t, "baseline")] and results[(t, "skills")]]
    return {
        "schema": SCHEMA,
        "study_id": study_id,
        "model_id": model,
        "n_tasks": len(sorted_ids),
        "n_domains": len(by_domain),
        "results_by_arm": summary,
        "paired_gain_skills_minus_baseline": (counts["skills"] - counts["baseline"]) / len(sorted_ids),
        "paired_gain_skills_minus_journal": (counts["skills"] - counts["journal"]) / len(sorted_ids),
        "repaired_tasks": repaired,
        "regressed_tasks": harmed,
        "pass_rates_by_domain": delta_by_domain,
        "skill_id_domains_observed": {k: sorted(v) for k, v in sorted(seen_skills.items())},
        "claims": "DESCRIPTIVE_ONLY: exact-match scoring of supplied answers; not proof of independent oracle, skill causality, AGI or statistical significance",
        "warnings": [
            "Oracle independence, pre-registration, budgets and task provenance cannot be established from these files alone.",
            "Skill IDs indicate reported usage, not demonstrated causal effectiveness or cross-domain transfer.",
            "No formal statistical claim or confidence interval is computed; multiple repetitions and hidden tests are needed.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--attempts", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(_read_json(args.manifest), _read_jsonl(args.oracle), _read_jsonl(args.attempts))
    except EvaluationError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
