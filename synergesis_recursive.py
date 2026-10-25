"""Verified, bounded strategy inheritance between explicitly created SYN generations.

The learned object is a routing policy over fixed executors, not model weights or
generated Python. Training outcomes are recomputed against a committed oracle.
Snapshots contain sufficient statistics, never permissions or executable text.
An operator able to replace all evidence can forge history: hashes are not trust.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "syn-recursive-generation-v1"
MAX_ROWS = 4096
MAX_BYTES = 4_000_000


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sealed(body: dict) -> dict:
    require("digest" not in body, "body already has digest")
    return {**body, "digest": digest(body)}


def check_seal(value: dict) -> None:
    require(isinstance(value, dict) and isinstance(value.get("digest"), str),
            "missing digest")
    require(digest({k: v for k, v in value.items() if k != "digest"}) == value["digest"],
            "digest mismatch")


def read_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_BYTES,
            "invalid or oversized input")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: require(False, "non-finite JSON"))
    require(isinstance(value, dict), "JSON object required")
    canonical(value)
    return value


def write_new(path: Path, value: dict) -> None:
    """Exclusive creation; a partial artifact fails validation and is never resumed."""
    import os
    require(not path.is_symlink(), "symlink output forbidden")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _label(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 160 and value.strip() == value


@dataclass(frozen=True)
class InheritanceContract:
    """Trusted configuration supplied separately from inherited state."""
    strategies: tuple[str, ...]
    default_strategy: str
    domains: tuple[str, ...]
    executor_digest: str
    model_digest: str
    minimum_observations: int = 3
    token_penalty: float = 0.01

    def __post_init__(self):
        require(isinstance(self.strategies, tuple) and 2 <= len(self.strategies) <= 8
                and len(set(self.strategies)) == len(self.strategies)
                and all(_label(s) for s in self.strategies), "invalid strategies")
        require(self.default_strategy in self.strategies, "unknown default")
        require(isinstance(self.domains, tuple) and 1 <= len(self.domains) <= 32
                and len(set(self.domains)) == len(self.domains)
                and all(_label(d) for d in self.domains), "invalid domains")
        for value in (self.executor_digest, self.model_digest):
            require(isinstance(value, str) and len(value) == 64
                    and all(c in "0123456789abcdef" for c in value), "invalid code/model digest")
        require(type(self.minimum_observations) is int and 2 <= self.minimum_observations <= 100,
                "invalid evidence threshold")
        require(type(self.token_penalty) in (int, float)
                and math.isfinite(self.token_penalty) and 0 <= self.token_penalty <= .1,
                "invalid fixed token penalty")

    def public(self) -> dict:
        from dataclasses import asdict
        result = asdict(self)
        result["strategies"] = list(self.strategies)
        result["domains"] = list(self.domains)
        return result

    @property
    def fingerprint(self) -> str:
        return digest(self.public())


def verify_training_batch(batch: dict, contract: InheritanceContract) -> dict:
    """Recompute exact-match outcomes, never accept a producer's 'passed' flag.

    A trainer calls this only AFTER attempts have been frozen. The solver worker
    receives tasks without answers; the evaluator owns this training-only oracle.
    """
    check_seal(batch)
    require(set(batch) == {"schema", "phase", "contract_digest", "tasks", "oracle",
                           "attempts", "attempts_commitment", "digest"}, "bad training fields")
    require(batch["schema"] == "syn-verified-training-batch-v1"
            and batch["phase"] == "train", "only training evidence may be inherited")
    require(batch["contract_digest"] == contract.fingerprint, "training contract changed")
    tasks, oracle, attempts = batch["tasks"], batch["oracle"], batch["attempts"]
    require(isinstance(tasks, list) and 1 <= len(tasks) <= MAX_ROWS, "bad training tasks")
    require(isinstance(oracle, dict) and isinstance(attempts, list)
            and len(attempts) <= MAX_ROWS * len(contract.strategies), "bad training evidence")
    require(digest(attempts) == batch["attempts_commitment"], "attempt commitment mismatch")
    task_map, contents = {}, set()
    for task in tasks:
        require(isinstance(task, dict) and set(task) == {"task_id", "domain", "input"},
                "bad public task; answers are forbidden")
        require(_label(task["task_id"]) and task["task_id"] not in task_map
                and task["domain"] in contract.domains and isinstance(task["input"], dict),
                "bad training task identity")
        fingerprint = digest({"domain": task["domain"], "input": task["input"]})
        require(fingerprint not in contents, "duplicate task content")
        contents.add(fingerprint)
        task_map[task["task_id"]] = task
    require(set(oracle) == set(task_map) and all(isinstance(v, str) and 0 < len(v) <= 300
                                               for v in oracle.values()), "bad training oracle")
    seen, rows = set(), []
    for attempt in attempts:
        require(isinstance(attempt, dict) and set(attempt) == {
            "task_id", "strategy", "answer", "tokens_used", "error"}, "bad training attempt")
        key = attempt["task_id"], attempt["strategy"]
        require(key[0] in task_map and key[1] in contract.strategies and key not in seen,
                "unknown or duplicate training attempt")
        seen.add(key)
        require(type(attempt["tokens_used"]) is int and 0 <= attempt["tokens_used"] <= 100_000,
                "bad measured token count")
        require(attempt["error"] is None or _label(attempt["error"]), "bad execution error")
        require(isinstance(attempt["answer"], str) and len(attempt["answer"]) <= 300,
                "bad answer")
        passed = attempt["error"] is None and attempt["answer"] == oracle[key[0]]
        rows.append({"task_id": key[0], "domain": task_map[key[0]]["domain"],
                     "task_digest": digest({"domain": task_map[key[0]]["domain"],
                                             "input": task_map[key[0]]["input"]}),
                     "strategy": key[1], "passed": passed, "tokens_used": attempt["tokens_used"]})
    require(len(seen) == len(task_map) * len(contract.strategies),
            "training requires paired attempts for every registered strategy")
    return {"batch_digest": batch["digest"], "rows": sorted(rows, key=lambda r: (r["task_id"], r["strategy"]))}


def _statistics(evidence: list[dict], contract: InheritanceContract) -> tuple[list[dict], dict]:
    buckets = defaultdict(list)
    for batch in evidence:
        for row in batch["rows"]:
            buckets[row["domain"], row["strategy"]].append(row)
    stats, policy = [], {}
    for domain in contract.domains:
        candidates = []
        for strategy in contract.strategies:
            rows = buckets[domain, strategy]
            successes = sum(r["passed"] for r in rows)
            tokens = sum(r["tokens_used"] for r in rows)
            # Beta(1,1) smoothing; this is an estimate, not a confidence bound.
            probability = (successes + 1) / (len(rows) + 2)
            mean_tokens = tokens / len(rows) if rows else 0
            utility = probability - contract.token_penalty * mean_tokens / 1000
            stats.append({"domain": domain, "strategy": strategy, "n": len(rows),
                          "successes": successes, "tokens": tokens,
                          "probability": probability, "utility": utility})
            candidates.append((utility, strategy == contract.default_strategy, strategy, len(rows)))
        if all(r[3] >= contract.minimum_observations for r in candidates):
            # Stable default on exact ties; learning cannot introduce a new executor.
            policy[domain] = sorted(candidates, key=lambda r: (-r[0], -r[1], r[2]))[0][2]
        else:
            policy[domain] = contract.default_strategy
    return stats, policy


def generation(previous: dict | None, batches: list[dict],
               contract: InheritanceContract, *, evidence_store: dict[str, dict]) -> dict:
    """Create a child from verified new experience, preserving the entire lineage."""
    if previous is not None:
        validate_generation(previous, contract, evidence_store=evidence_store)
    require(isinstance(batches, list) and len(batches) <= 32, "invalid batch list")
    inherited = list(previous["batch_digests"]) if previous else []
    for batch in batches:
        verified = verify_training_batch(batch, contract)
        key = verified["batch_digest"]
        require(key not in inherited, "duplicate evidence batch")
        require(key in evidence_store and evidence_store[key] == batch,
                "new evidence not present in trusted store")
        inherited.append(key)
    require(len(inherited) <= 128, "generation evidence cap exceeded")
    summaries = [verify_training_batch(evidence_store[key], contract) for key in inherited]
    task_ids, task_digests = set(), set()
    for batch in summaries:
        for row in batch["rows"]:
            if row["strategy"] == contract.strategies[0]:
                require(row["task_id"] not in task_ids and row["task_digest"] not in task_digests,
                        "reused training task across generations")
                task_ids.add(row["task_id"])
                task_digests.add(row["task_digest"])
    stats, policy = _statistics(summaries, contract)
    lineage = list(previous["lineage"]) + [previous["digest"]] if previous else []
    return sealed({"schema": SCHEMA, "iteration": len(lineage), "lineage": lineage,
                   "parent_digest": previous["digest"] if previous else None,
                   "contract_digest": contract.fingerprint, "batch_digests": inherited,
                   "statistics": stats, "policy": policy})


def validate_generation(state: dict, contract: InheritanceContract, *,
                        evidence_store: dict[str, dict], parent: dict | None = None) -> None:
    check_seal(state)
    require(set(state) == {"schema", "iteration", "lineage", "parent_digest", "contract_digest",
                           "batch_digests", "statistics", "policy", "digest"}, "bad generation fields")
    require(state["schema"] == SCHEMA and state["contract_digest"] == contract.fingerprint,
            "generation contract mismatch")
    lineage, keys = state["lineage"], state["batch_digests"]
    require(isinstance(lineage, list) and len(lineage) <= 128
            and type(state["iteration"]) is int and state["iteration"] == len(lineage)
            and all(isinstance(x, str) and len(x) == 64 for x in lineage)
            and len(set(lineage)) == len(lineage), "invalid lineage")
    require(state["parent_digest"] == (lineage[-1] if lineage else None), "parent mismatch")
    require(isinstance(keys, list) and len(keys) <= 128
            and all(isinstance(k, str) and k in evidence_store for k in keys)
            and len(set(keys)) == len(keys), "missing or duplicate evidence")
    verified = [verify_training_batch(evidence_store[k], contract) for k in keys]
    stats, policy = _statistics(verified, contract)
    require(state["statistics"] == stats and state["policy"] == policy,
            "inherited policy differs from recomputed evidence")
    # Recheck duplication even when loading artifacts rather than advancing.
    tasks = [(r["task_id"], r["task_digest"]) for b in verified for r in b["rows"]
             if r["strategy"] == contract.strategies[0]]
    require(len({t[0] for t in tasks}) == len(tasks) and len({t[1] for t in tasks}) == len(tasks),
            "reused training task across generations")
    if parent is not None:
        validate_generation(parent, contract, evidence_store=evidence_store)
        require(state["parent_digest"] == parent["digest"]
                and state["lineage"] == parent["lineage"] + [parent["digest"]]
                and keys[:len(parent["batch_digests"])] == parent["batch_digests"],
                "lineage or inherited evidence was rewritten")


class InheritedRouter:
    """A validated read-only decision provider; no oracle or mutable learner."""
    def __init__(self, state: dict, contract: InheritanceContract, *, evidence_store: dict[str, dict]):
        validate_generation(state, contract, evidence_store=evidence_store)
        self._policy = dict(state["policy"])
        self._default = contract.default_strategy
        self.state_digest = state["digest"]
        self._known_ids = {r["task_id"] for k in state["batch_digests"]
                           for r in evidence_store[k]["tasks"]}
        self._known_content = {digest({"domain": r["domain"], "input": r["input"]})
                               for k in state["batch_digests"] for r in evidence_store[k]["tasks"]}

    def select(self, task: dict) -> str:
        require(isinstance(task, dict) and set(task) == {"task_id", "domain", "input"}
                and _label(task["task_id"]) and isinstance(task["domain"], str)
                and isinstance(task["input"], dict), "bad decision task")
        require(task["task_id"] not in self._known_ids
                and digest({"domain": task["domain"], "input": task["input"]}) not in self._known_content,
                "train/test leakage")
        return self._policy.get(task["domain"], self._default)


def replay_into_roam(state: dict, contract: InheritanceContract, *, evidence_store: dict[str, dict],
                     ledger_path: Path):
    """Reconstruct the existing SYN-ROAM learner from verified generation evidence.

    Only a NEW, caller-selected experimental ledger is allowed. No user profile
    or ResearchAgenda is changed. This adapter requires the existing POSIX runtime.
    """
    from synergesis_roam import (MethodLedger, MethodOutcome, OutcomeMetrics, ResearchMethodLearner,
                                SearchStep, SelectionConfig, make_method)
    validate_generation(state, contract, evidence_store=evidence_store)
    require(not ledger_path.exists() and not ledger_path.is_symlink(), "refusing existing ROAM ledger")
    learner = ResearchMethodLearner(ledger=MethodLedger(ledger_path), config=SelectionConfig(0, False))
    methods = {}
    for domain in contract.domains:
        for strategy in contract.strategies:
            method = make_method(name=f"recursive:{strategy}", domain=domain,
                                 steps=(SearchStep("recursive-local", "explore", "{question}", 1),),
                                 created_by="SYN-RECURSIVE")
            methods[domain, strategy] = learner.register(method)
    # Import exact verified correctness as verified_yield, all unrelated metrics zero.
    # ROAM's raw reward differs from the smoothed cost-sensitive router above;
    # consumers must explicitly choose which selection rule they are using.
    for key in state["batch_digests"]:
        for row in verify_training_batch(evidence_store[key], contract)["rows"]:
            identity = digest([key, row["task_id"], row["strategy"]])
            learner.ledger.append(MethodOutcome(
                outcome_id=f"recursive:{identity}", session_id=f"recursive:{identity}",
                method_id=methods[row["domain"], row["strategy"]].method_id, domain=row["domain"],
                metrics=OutcomeMetrics(float(row["passed"]), 0, 0, 0, 0, 0, 0),
                utility=float(row["passed"]), evaluated_at="2026-10-25T00:00:00+00:00"))
    return learner, methods
