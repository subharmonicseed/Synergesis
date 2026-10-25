"""Executable inheritance, leakage, restart, tamper and safety regressions.

Model doubles in this file are software tests, never experimental evidence.
"""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from synergesis_recursive import (InheritanceContract, InheritedRouter, digest, generation, read_json,
                                 replay_into_roam, sealed, validate_generation, verify_training_batch, write_new)
from synergesis_recursive_tasks import DOMAINS, exact_executor, make_tasks, oracle_answer
from synergesis_recursive_trial import AuditedRuntime, execute_worker, summarize


@pytest.fixture
def contract():
    return InheritanceContract(("llm", "exact"), "llm", DOMAINS, "a"*64, "b"*64)


def batch(contract, *, seed=1, count=3, domains=("arithmetic",), llm_correct=False):
    tasks = make_tasks(seed, f"train-{seed}", domains, count)
    oracle = {t["task_id"]: oracle_answer(t) for t in tasks}
    attempts = [{"task_id": t["task_id"], "strategy": s,
                 "answer": oracle[t["task_id"]] if s == "exact" or llm_correct else "WRONG",
                 "tokens_used": 120 if s == "llm" else 0, "error": None}
                for t in tasks for s in contract.strategies]
    return sealed({"schema": "syn-verified-training-batch-v1", "phase": "train",
                   "contract_digest": contract.fingerprint, "tasks": tasks, "oracle": oracle,
                   "attempts": attempts, "attempts_commitment": digest(attempts)})


def reseal(value):
    return sealed({k: v for k, v in value.items() if k != "digest"})


def child(contract):
    evidence = batch(contract)
    store = {evidence["digest"]: evidence}
    initial = generation(None, [], contract, evidence_store=store)
    learned = generation(initial, [evidence], contract, evidence_store=store)
    return initial, learned, store


def test_three_generations_transmit_executed_learning_and_change_decisions(contract):
    first, second, store = child(contract)
    extra = batch(contract, seed=3, domains=("calendar", "graph"))
    store[extra["digest"]] = extra
    third = generation(second, [extra], contract, evidence_store=store)
    for state, parent in ((second, first), (third, second)):
        validate_generation(state, contract, evidence_store=store, parent=parent)
    tasks = make_tasks(7, "heldout", DOMAINS, 8)
    policies = [InheritedRouter(s, contract, evidence_store=store) for s in (first, second, third)]
    assert [p.select(tasks[0]) for p in policies] == ["llm", "exact", "exact"]
    assert [p.select(tasks[-1]) for p in policies] == ["llm", "llm", "exact"]
    assert third["lineage"] == [first["digest"], second["digest"]]
    assert len(third["batch_digests"]) == 2
    assert sum(exact_executor(t) == oracle_answer(t) for t in tasks) == 24


def test_minimum_evidence_keeps_default(contract):
    evidence = batch(contract, count=2)
    store = {evidence["digest"]: evidence}
    state = generation(None, [evidence], contract, evidence_store=store)
    assert state["policy"]["arithmetic"] == "llm"


def test_verified_counterexamples_can_reverse_inherited_choice(contract):
    _, learned, store = child(contract)
    counterexamples = batch(contract, seed=44, count=6, llm_correct=True)
    for attempt in counterexamples["attempts"]:
        if attempt["strategy"] == "exact":
            attempt["answer"] = "WRONG-SIMULATED-TOOL-REGRESSION"
    counterexamples["attempts_commitment"] = digest(counterexamples["attempts"])
    counterexamples = reseal(counterexamples)
    store[counterexamples["digest"]] = counterexamples
    revised = generation(learned, [counterexamples], contract, evidence_store=store)
    assert learned["policy"]["arithmetic"] == "exact"
    assert revised["policy"]["arithmetic"] == "llm"
    assert revised["batch_digests"][:len(learned["batch_digests"])] == learned["batch_digests"]


def test_equal_accuracy_can_learn_lower_token_cost(contract):
    evidence = batch(contract, llm_correct=True)
    state = generation(None, [evidence], contract, evidence_store={evidence["digest"]: evidence})
    assert state["policy"]["arithmetic"] == "exact"
    no_cost = replace(contract, token_penalty=0)
    evidence = batch(no_cost, llm_correct=True)
    state = generation(None, [evidence], no_cost, evidence_store={evidence["digest"]: evidence})
    assert state["policy"]["arithmetic"] == "llm"


@pytest.mark.parametrize("mutation", ["seal", "policy", "statistics", "permissions", "missing_store"])
def test_tamper_rejected_even_with_recomputed_hash(contract, mutation):
    _, state, store = child(contract)
    altered = copy.deepcopy(state)
    if mutation == "seal":
        altered["iteration"] = 12
    elif mutation == "policy":
        altered["policy"]["arithmetic"] = "shell.exec"
    elif mutation == "statistics":
        altered["statistics"][0]["successes"] += 10
    elif mutation == "permissions":
        altered["permissions"] = ["network:any"]
    else:
        store = {}
    if mutation != "seal":
        altered = reseal(altered)
    with pytest.raises(ValueError):
        InheritedRouter(altered, contract, evidence_store=store)


@pytest.mark.parametrize("mutation", ["test_evidence", "self_report", "missing_pair", "bool_tokens", "wrong_commitment"])
def test_unverified_feedback_cannot_become_inherited_success(contract, mutation):
    evidence = batch(contract)
    if mutation == "test_evidence":
        evidence["phase"] = "test"
    elif mutation == "self_report":
        evidence["attempts"][0]["passed"] = True
    elif mutation == "missing_pair":
        evidence["attempts"].pop()
    elif mutation == "bool_tokens":
        evidence["attempts"][0]["tokens_used"] = True
    else:
        evidence["attempts_commitment"] = "f"*64
    if mutation != "wrong_commitment":
        evidence["attempts_commitment"] = digest(evidence["attempts"])
    with pytest.raises(ValueError):
        verify_training_batch(reseal(evidence), contract)


def test_false_answer_is_recomputed_as_failure(contract):
    evidence = batch(contract)
    verified = verify_training_batch(evidence, contract)
    assert all(not r["passed"] for r in verified["rows"] if r["strategy"] == "llm")


def test_duplicate_batch_and_reused_tasks_refused(contract):
    _, state, store = child(contract)
    evidence = next(iter(store.values()))
    with pytest.raises(ValueError, match="duplicate"):
        generation(state, [evidence], contract, evidence_store=store)
    changed = copy.deepcopy(evidence)
    changed["attempts"][0]["answer"] = "DIFFERENT"
    changed["attempts_commitment"] = digest(changed["attempts"])
    changed = reseal(changed)
    store[changed["digest"]] = changed
    with pytest.raises(ValueError, match="reused"):
        generation(state, [changed], contract, evidence_store=store)


def test_training_overlap_by_id_and_content_rejected(contract):
    _, state, store = child(contract)
    router = InheritedRouter(state, contract, evidence_store=store)
    task = copy.deepcopy(next(iter(store.values()))["tasks"][0])
    with pytest.raises(ValueError, match="leakage"):
        router.select(task)
    task["task_id"] = "renamed-heldout"
    with pytest.raises(ValueError, match="leakage"):
        router.select(task)


def test_changed_code_model_or_threshold_requires_new_contract(contract):
    _, state, store = child(contract)
    for altered in (replace(contract, model_digest="c"*64), replace(contract, executor_digest="d"*64),
                    replace(contract, minimum_observations=2)):
        with pytest.raises(ValueError, match="contract"):
            InheritedRouter(state, altered, evidence_store=store)


def test_parent_lineage_cannot_be_substituted(contract):
    first, second, store = child(contract)
    other = generation(None, [], contract, evidence_store={})
    other["lineage"] = ["f"*64]
    other["parent_digest"] = "f"*64
    other["iteration"] = 1
    other = reseal(other)
    with pytest.raises(ValueError, match="lineage"):
        validate_generation(second, contract, evidence_store=store, parent=other)
    assert first["iteration"] == 0


def test_real_process_restart_consumes_saved_generation(contract, tmp_path):
    _, state, store = child(contract)
    tasks = make_tasks(91, "fresh", ("arithmetic", "calendar"), 1)
    request, output = tmp_path / "input.json", tmp_path / "decisions.json"
    write_new(request, {"contract": contract.public(), "state": state, "evidence": store, "tasks": tasks})
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent)}
    subprocess.run([sys.executable, "-m", "synergesis_recursive_trial", "route", "--request", str(request),
                    "--out", str(output)], cwd=tmp_path, env=env, check=True, capture_output=True)
    loaded = read_json(output)
    assert loaded["worker_pid"] != os.getpid()
    assert loaded["loaded_state_digest"] == state["digest"]
    assert list(loaded["decisions"].values()) == ["exact", "llm"]


def test_oracle_and_executor_agree_on_900_new_inputs():
    for task in make_tasks(109, "crosscheck", DOMAINS, 300):
        assert exact_executor(task) == oracle_answer(task)


@pytest.mark.parametrize("stamp,days,expected", [("2024-02-28", 2, "2024-03-01"),
    ("2025-12-31", 1, "2026-01-01"), ("2024-12-31", 365, "2025-12-31")])
def test_calendar_boundaries(stamp, days, expected):
    task = {"task_id": "edge", "domain": "calendar", "input": {"date": stamp, "days": days}}
    assert exact_executor(task) == oracle_answer(task) == expected


def test_executable_text_cannot_be_a_tool_or_numeric_input():
    task = {"task_id": "attack", "domain": "arithmetic", "input": {"a": "__import__('os')", "b": 1, "c": 2}}
    with pytest.raises(ValueError):
        exact_executor(task)


def test_exclusive_writes_and_ambiguous_json_refused(tmp_path):
    path = tmp_path / "artifact.json"
    write_new(path, {"ok": 1})
    with pytest.raises(FileExistsError):
        write_new(path, {"ok": 2})
    path.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError, match="duplicate"):
        read_json(path)
    path.write_text('{"a":NaN}')
    with pytest.raises(ValueError):
        read_json(path)


@pytest.mark.skipif(os.name == "nt", reason="existing SYN ledgers require POSIX")
def test_verified_inheritance_replays_into_actual_roam_learner(contract, tmp_path):
    from synergesis_roam import ResearchQuestion
    _, state, store = child(contract)
    learner, methods = replay_into_roam(state, contract, evidence_store=store, ledger_path=tmp_path / "roam.jsonl")
    chosen = learner.select(ResearchQuestion.create(domain="arithmetic", question="new task"))
    assert chosen.method_id == methods["arithmetic", "exact"].method_id
    assert len(learner.ledger.events()) == 6
    with pytest.raises(ValueError, match="existing"):
        replay_into_roam(state, contract, evidence_store=store, ledger_path=tmp_path / "roam.jsonl")


@pytest.mark.skipif(os.name == "nt", reason="existing SYN audit and risk ledgers require POSIX")
def test_actual_dispatch_aegis_risk_reality_and_prediction(contract, tmp_path):
    runtime = AuditedRuntime(tmp_path, contract, model="unused", port=11434, seed=26,
                             max_calls=1, max_tokens=10000, deadline_seconds=30)
    task = make_tasks(42, "real-execution", ("arithmetic",), 1)[0]
    result = runtime.execute(task, "exact")
    assert result["answer"] == oracle_answer(task)
    assert runtime.verify(result, oracle_answer(task))
    assert runtime.verify(result, oracle_answer(task))
    assert runtime.risk.state().consumed == 1
    assert runtime.risk.state().reserved == 0
    assert len(runtime.predictions.ledger.records()) == 1
    with pytest.raises(ValueError, match="authority"):
        runtime.execute(task, "shell.exec")
    second = make_tasks(43, "false-claim", ("arithmetic",), 1)[0]
    result = runtime.execute(second, "exact")
    assert not runtime.verify(result, "WRONG")
    assert runtime.predictions.ledger.records()[-1].observed_effect is False


@pytest.mark.skipif(os.name == "nt", reason="existing SYN audit and risk ledgers require POSIX")
def test_exhausted_budget_denies_transport_before_execution(contract, tmp_path):
    runtime = AuditedRuntime(tmp_path, contract, model="unused", port=11434, seed=26,
                             max_calls=0, max_tokens=10000, deadline_seconds=30)
    with pytest.raises(ValueError, match="budget"):
        runtime.execute(make_tasks(7, "denied", ("arithmetic",), 1)[0], "llm")
    assert runtime.risk.state().consumed == 0
    assert not runtime.executions


def test_missing_provider_usage_aborts_without_invented_tokens(monkeypatch, tmp_path):
    import synergesis_recursive_trial as trial
    monkeypatch.setattr(trial, "model_identity", lambda *a: {"digest": "b"*64})
    monkeypatch.setattr(trial, "_http", lambda *a, **k: {"done": True, "message": {"content": '{"answer":"3"}'}})
    request = {"task": make_tasks(4, "usage", ("arithmetic",), 1)[0], "strategy": "llm",
               "model": "fake-for-unit-test", "model_digest": "b"*64, "port": 11434, "seed": 26, "memory": []}
    with pytest.raises(ValueError, match="measured usage"):
        execute_worker(request, tmp_path / "answer.json")
    assert not (tmp_path / "answer.json").exists()
    assert (tmp_path / "provider-response.json").is_file()


def test_paired_summary_counts_regressions_and_gain():
    tasks = make_tasks(2, "score", DOMAINS, 1)
    oracle = {t["task_id"]: oracle_answer(t) for t in tasks}
    rows = [{"arm": a, "task_id": t["task_id"], "answer": oracle[t["task_id"]] if a == "syn2" else "WRONG",
             "tokens_used": 0, "error": None} for t in tasks for a in ("reset", "journal", "syn1", "syn2")]
    result = summarize(rows, oracle, tasks)
    assert result["paired_gain"] == 1
    assert len(result["repaired"]) == 3 and result["regressed"] == []
    assert result["mcnemar_exact_two_sided_exploratory"] == .25


@pytest.fixture
def offline_study(monkeypatch, tmp_path):
    """Explicitly simulated model transport, used only for audit software tests."""
    import synergesis_recursive_trial as trial
    from types import SimpleNamespace
    monkeypatch.setattr(trial, "model_identity", lambda *a: {
        "name": "software-test-double", "digest": "b"*64, "size": 0, "details": {}})
    def child(runtime, action, request_path, output, cwd):
        request = read_json(request_path)
        if action == "route":
            trial.route_worker(request, output)
        else:
            answer = exact_executor(request["task"])
            monkeypatch.setattr(trial, "_http", lambda *a, **k: {
                "model": "software-test-double", "done": True, "prompt_eval_count": 100, "eval_count": 10,
                "message": {"content": json.dumps({"answer": answer})}})
            trial.execute_worker(request, output)
    monkeypatch.setattr(trial.AuditedRuntime, "_child", child)
    path = tmp_path / "SIMULATED-NOT-EXPERIMENTAL-EVIDENCE"
    trial.run_study(SimpleNamespace(out=path, model="software-test-double", port=11434,
                                    train_per_domain=3, test_per_domain=1, max_calls=20,
                                    max_tokens=100000, deadline_seconds=60))
    return path


@pytest.mark.skipif(os.name == "nt", reason="audit fixture exercises the existing POSIX ledgers")
def test_offline_audit_recomputes_complete_study(offline_study):
    from synergesis_recursive_audit import audit
    result = audit(offline_study)
    assert result["verified"] and result["n_heldout"] == 3
    assert result["strict_passed"] == {"reset": 3, "journal": 3, "syn1": 3, "syn2": 3}
    assert result["ledgers"]["risk_events"] > 0


@pytest.mark.skipif(os.name == "nt", reason="audit fixture exercises the existing POSIX ledgers")
@pytest.mark.parametrize("target", ["provider", "oracle", "attempt", "policy", "preregistration", "cost"])
def test_offline_audit_detects_tampered_artifacts(offline_study, target):
    from synergesis_recursive_audit import audit
    if target == "provider":
        path = next((offline_study / "executions").glob("*/provider-response.json"))
        content = read_json(path)
        content["message"]["content"] = '{"answer":"forged"}'
    elif target == "oracle":
        path = offline_study / "heldout-oracle.json"
        content = read_json(path)
        content["answers"][next(iter(content["answers"]))] = "forged"
    elif target == "attempt":
        path = offline_study / "frozen-heldout-attempts.json"
        content = read_json(path)
        content["attempts"][0]["answer"] = "forged"
        content = reseal(content)
    elif target == "policy":
        path = offline_study / "generation-2.json"
        content = read_json(path)
        content["policy"]["arithmetic"] = "llm"
        content = reseal(content)
    elif target == "preregistration":
        path = offline_study / "preregistration.json"
        content = read_json(path)
        content["limits"]["max_calls"] += 1
        content = reseal(content)
    else:
        path = offline_study / "results.json"
        content = read_json(path)
        content["physical_tokens"] += 1
        content = reseal(content)
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError):
        audit(offline_study)
