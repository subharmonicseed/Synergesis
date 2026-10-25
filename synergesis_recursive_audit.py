"""Recheck a completed recursive study offline, including raw provider receipts.

Use: python -m synergesis_recursive_audit STUDY_DIR [--out NEW_RECEIPT]
No model calls, downloads, score changes or modification of the study.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synergesis_recursive import (InheritanceContract, InheritedRouter, check_seal, digest, generation,
                                 read_json, require, write_new, sealed)
from synergesis_recursive_tasks import oracle_answer
from synergesis_recursive_trial import code_identity, summarize


def audit(study: Path, *, check_ledgers: bool = True) -> dict:
    prereg = read_json(study / "preregistration.json")
    check_seal(prereg)
    config = prereg["contract"]
    contract = InheritanceContract(**{**config, "strategies": tuple(config["strategies"]),
                                     "domains": tuple(config["domains"])})
    require(contract.executor_digest == code_identity(), "current source differs from experimental source")
    require(contract.model_digest == prereg["model"]["digest"], "model contract mismatch")
    tasks = read_json(study / "heldout-tasks.json")["tasks"]
    oracle = read_json(study / "heldout-oracle.json")["answers"]
    require(digest(tasks) == prereg["heldout_tasks_digest"]
            and digest(oracle) == prereg["oracle_digest"], "heldout commitment mismatch")
    require(oracle == {t["task_id"]: oracle_answer(t) for t in tasks}, "oracle fails independent recomputation")
    store, states = {}, []
    for index in range(3):
        batches = []
        if index:
            batch = read_json(study / f"training-{index}.json")
            frozen = read_json(study / f"training-{index}-attempts.json")
            check_seal(frozen)
            require(frozen["attempts"] == batch["attempts"], "training attempts changed after freeze")
            require(digest(batch["tasks"]) == prereg[f"train{index}_digest"], "training tasks changed")
            require(batch["oracle"] == {t["task_id"]: oracle_answer(t) for t in batch["tasks"]},
                    "training oracle fails recomputation")
            store[batch["digest"]] = batch
            batches = [batch]
        expected = generation(states[-1] if states else None, batches, contract, evidence_store=store)
        actual = read_json(study / f"generation-{index}.json")
        require(actual == expected, "generation does not follow verified parent experience")
        states.append(actual)
        decisions = read_json(study / f"decisions-{index}.json")
        check_seal(decisions)
        router = InheritedRouter(actual, contract, evidence_store=store)
        require(decisions["loaded_state_digest"] == actual["digest"]
                and decisions["decisions"] == {t["task_id"]: router.select(t) for t in tasks},
                "persisted decisions differ from inherited policy")
    evidence_answers = {t["task_id"]: b["oracle"][t["task_id"]] for b in store.values() for t in b["tasks"]}
    expected_answers = {**evidence_answers, **oracle}
    executions, provider_values, all_tokens = {}, {}, 0
    for folder in sorted((study / "executions").iterdir()):
        require(folder.is_dir() and not folder.is_symlink(), "invalid execution directory")
        request, result = read_json(folder / "request.json"), read_json(folder / "answer.json")
        check_seal(result)
        require(digest(request) == folder.name == result["request_digest"], "execution request changed")
        require(result["task_id"] == request["task"]["task_id"]
                and result["strategy"] == request["strategy"]
                and request["model_digest"] == contract.model_digest
                and request["model"] == prereg["model"]["name"], "execution identity changed")
        tid = result["task_id"]
        require(tid in expected_answers, "unregistered execution task")
        if result["strategy"] == "llm":
            raw = read_json(folder / "provider-response.json")
            require(raw.get("done") is True and raw.get("model") == request["model"], "provider identity mismatch")
            p, q = raw.get("prompt_eval_count"), raw.get("eval_count")
            require(type(p) is int and type(q) is int and 0 <= p <= 4096 and 0 <= q <= 128
                    and result["tokens_used"] == p+q, "token receipt mismatch")
            try:
                content = json.loads(raw["message"]["content"])
            except (ValueError, KeyError, TypeError):
                content = None
            well_formed = (isinstance(content, dict) and set(content) == {"answer"}
                           and isinstance(content["answer"], str) and 0 < len(content["answer"]) <= 300)
            require((result["answer"], result["error"]) ==
                    ((content["answer"], None) if well_formed else ("", "invalid_answer_format")),
                    "parsed answer differs from raw provider response")
            # Explicit post-hoc sensitivity: normalize only an integer answer value.
            value = content.get("answer") if isinstance(content, dict) and set(content) == {"answer"} else None
            provider_values[folder.name] = str(value) if type(value) is int else value if isinstance(value, str) else None
        else:
            from synergesis_recursive_tasks import exact_executor
            require(result["strategy"] == "exact" and result["tokens_used"] == 0
                    and result["error"] is None and result["answer"] == exact_executor(request["task"]),
                    "fixed tool receipt fails recomputation")
        all_tokens += result["tokens_used"]
        executions[folder.name] = (request, result)
    for b in store.values():
        for a in b["attempts"]:
            found = [res for req, res in executions.values() if res["task_id"] == a["task_id"]
                     and res["strategy"] == a["strategy"] and not req["memory"]]
            require(len(found) == 1 and all(found[0][k] == a[k] for k in a), "training has no matching execution")
    frozen = read_json(study / "frozen-heldout-attempts.json")
    check_seal(frozen)
    rows = frozen["attempts"]
    require(len(rows) == 4*len(tasks)
            and len({(r["arm"], r["task_id"]) for r in rows}) == len(rows), "duplicate or missing paired result")
    secondary = {arm: 0 for arm in prereg["arms"]}
    task_map = {t["task_id"]: t for t in tasks}
    routers = {f"syn{i}": InheritedRouter(states[i], contract, evidence_store=store) for i in (1, 2)}
    used = set()
    for row in rows:
        require(row["arm"] in secondary and row["task_id"] in task_map, "unregistered heldout attempt")
        request, result = executions[row["request_digest"]]
        require(request["task"] == task_map[row["task_id"]]
                and all(result[k] == row[k] for k in ("task_id", "strategy", "answer", "tokens_used", "error")),
                "heldout attempt differs from executed request/answer")
        strategy = routers[row["arm"]].select(request["task"]) if row["arm"] in routers else "llm"
        require(strategy == row["strategy"], "executed strategy differs from generation decision")
        expected_memory = [{"task": t, "answer": b["oracle"][t["task_id"]]}
                           for b in store.values() for t in b["tasks"]
                           if t["domain"] == request["task"]["domain"]] if row["arm"] == "journal" else []
        require(request["memory"] == expected_memory, "memory contains unexpected or heldout data")
        answer = provider_values.get(row["request_digest"], row["answer"])
        secondary[row["arm"]] += answer == oracle[row["task_id"]]
        used.add(row["request_digest"])
    actual = read_json(study / "results.json")
    check_seal(actual)
    require(actual["preregistration_digest"] == prereg["digest"], "preregistration changed")
    recomputed = summarize(rows, oracle, tasks)
    require(all(actual[k] == v for k, v in recomputed.items()), "published scores differ from frozen attempts")
    require(actual["physical_executions"] == len(executions)
            and actual["physical_model_calls"] == len(provider_values)
            and actual["physical_tokens"] == all_tokens, "physical cost totals differ")
    require(actual["physical_model_calls"] <= prereg["limits"]["max_calls"]
            and all_tokens <= prereg["limits"]["max_tokens"], "registered budget exceeded")
    training_tokens = sum(r["tokens_used"] for b in store.values() for r in b["attempts"])
    ledger_receipt = None
    if check_ledgers:
        from synergesis_glyph_protocol import GlyphLedger
        from synergesis_prediction import PredictionLedger
        from synergesis_risk_budget import RiskBudgetLedger
        glyphs = GlyphLedger(study / "glyphs.jsonl").verify()
        predictions = PredictionLedger(study / "predictions.jsonl")
        prediction_count, _ = predictions.verify()
        require(prediction_count == len(executions), "an execution lacks verified prediction settlement")
        expected_passes = sum(r["error"] is None and r["answer"] == expected_answers[r["task_id"]]
                              for _, r in executions.values())
        require(sum(r.observed_effect for r in predictions.records()) == expected_passes,
                "prediction outcomes disagree with oracle")
        risk = RiskBudgetLedger(study / "risk.jsonl")
        risk_count, _ = risk.verify()
        events = risk.events()
        require(risk_count == 2*len(executions)
                and sum(e.event_type == "reserved" for e in events) == len(executions)
                and sum(e.event_type == "consumed" for e in events) == len(executions),
                "risk reservations are incomplete")
        require(actual["risk_state"]["reserved"] == 0
                and actual["risk_state"]["consumed"] == len(executions), "risk summary mismatch")
        ledger_receipt = {"glyph_events": glyphs.event_count, "prediction_settlements": prediction_count,
                          "risk_events": risk_count}
    return sealed({"schema": "syn-recursive-offline-verification-v1", "verified": True,
                   "study_results_digest": actual["digest"], "source_digest": code_identity(),
                   "n_heldout": len(tasks), "n_training": len(evidence_answers),
                   "physical_model_calls": len(provider_values), "physical_tokens": all_tokens,
                   "training_tokens": training_tokens, "ledgers": ledger_receipt,
                   "strict_passed": {arm: r["passed"] for arm, r in actual["results"].items()},
                   "posthoc_integer_format_sensitivity_passed": secondary,
                   "warning": "Offline verification checks artifact consistency and recomputes scores; it is not independent attestation of transport, timestamps or operator blindness. Integer-format sensitivity was added after the first study and does not replace its registered score."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--skip-ledgers", action="store_true", help="portable content checks only; report ledgers=null")
    args = parser.parse_args()
    result = audit(args.study, check_ledgers=not args.skip_ledgers)
    if args.out:
        write_new(args.out, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
