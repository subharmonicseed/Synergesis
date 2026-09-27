import json
import multiprocessing
import os
import time

import synergesis_roam as roam
from dataclasses import asdict, replace

import pytest

from synergesis_roam import (
    MethodLedger, MethodOutcome, OutcomeMetrics, ResearchMethodLearner,
    ResearchQuestion, RoamSession, SelectionConfig, UtilityWeights, _canon, _hash,
)


METRICS = OutcomeMetrics(0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.25)
WEIGHTS = UtilityWeights(1, 1, 1, 1, 1, 1, 1)


def outcome(session="session-1", outcome_id="outcome-1", utility=1.25, evaluated="t1"):
    return MethodOutcome(outcome_id, session, "method-1", "science", METRICS, utility, evaluated)


def _append_process(path, session, gate, results):
    try:
        ledger = MethodLedger(path)
        original_hash = roam._hash

        def delayed_hash(value):
            time.sleep(0.01)
            return original_hash(value)

        roam._hash = delayed_hash
        gate.wait(timeout=8)
        stored = ledger.append(outcome(session=session, outcome_id=f"outcome-{session}",
                                       evaluated=f"process:{os.getpid()}"))
        results.put((session, "ok", stored.evaluated_at))
    except BaseException as exc:
        results.put((session, repr(exc)))


def test_same_semantic_session_returns_original_and_writes_once(tmp_path):
    ledger = MethodLedger(tmp_path / "outcomes.jsonl")
    first = ledger.append(outcome(evaluated="first-time"))
    retried = ledger.append(outcome(evaluated="later-time"))
    assert retried == first
    assert len(ledger.outcomes()) == 1
    assert ledger.stats("method-1").observations == 1


def test_conflict_and_malformed_input_do_not_mutate(tmp_path):
    ledger = MethodLedger(tmp_path / "outcomes.jsonl")
    ledger.append(outcome())
    before = ledger.path.read_bytes()
    with pytest.raises(ValueError, match="conflicting"):
        ledger.append(outcome(utility=9.0, evaluated="retry"))
    with pytest.raises(ValueError, match="outcome_id"):
        ledger.append(outcome(session="session-2"))
    with pytest.raises(ValueError):
        ledger.append(replace(outcome(session=""), session_id=" "))
    with pytest.raises(ValueError):
        ledger.append(replace(outcome(), utility=float("nan")))
    assert ledger.path.read_bytes() == before


def _run_appenders(tmp_path, sessions):
    ctx = multiprocessing.get_context("spawn")
    gate = ctx.Barrier(len(sessions))
    results = ctx.Queue()
    processes = [
        ctx.Process(target=_append_process, args=(str(tmp_path / "parallel.jsonl"), session, gate, results))
        for session in sessions
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(12)
            assert not process.is_alive(), "writer process did not finish"
            assert process.exitcode == 0
        answers = [results.get(timeout=2) for _ in processes]
        assert [answer[1] for answer in answers] == ["ok"] * len(processes)
        return answers, MethodLedger(tmp_path / "parallel.jsonl")
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(2)
        results.close()
        results.join_thread()


def test_spawned_processes_append_distinct_sessions_without_lost_events(tmp_path):
    _, ledger = _run_appenders(tmp_path, [f"s{i}" for i in range(4)])
    assert len(ledger.outcomes()) == 4
    assert [event["sequence"] for event in ledger.events()] == [1, 2, 3, 4]


def test_spawned_processes_count_same_session_once(tmp_path):
    answers, ledger = _run_appenders(tmp_path, ["same"] * 4)
    assert len({answer[2] for answer in answers}) == 1
    assert len(ledger.events()) == 1
    assert ledger.stats("method-1").observations == 1


def test_restart_and_retry_returns_stored_timestamp(tmp_path):
    path = tmp_path / "restart.jsonl"
    session = RoamSession(
        "stable-session", ResearchQuestion.create(domain="science", question="q"),
        "method-1", (), 0, 0.0, "completed", "plan",
    )
    first_learner = ResearchMethodLearner(
        ledger=MethodLedger(path),
        config=SelectionConfig(0.0, False),
    )
    first = first_learner.record_outcome(session=session, metrics=METRICS, weights=WEIGHTS)
    restarted = ResearchMethodLearner(
        ledger=MethodLedger(path),
        config=SelectionConfig(0.0, False),
    )
    again = restarted.record_outcome(session=session, metrics=METRICS, weights=WEIGHTS)
    assert again == first
    assert len(restarted.ledger.outcomes()) == 1


def test_legacy_duplicate_sessions_and_corrupt_chain_fail_closed(tmp_path):
    path = tmp_path / "legacy.jsonl"
    payload = asdict(outcome())
    body1 = {"sequence": 1, "previous_digest": None, "payload": payload}
    event1 = {**body1, "digest": _hash(body1)}
    body2 = {"sequence": 2, "previous_digest": event1["digest"], "payload": {**payload, "evaluated_at": "other"}}
    event2 = {**body2, "digest": _hash(body2)}
    path.write_text(_canon(event1) + "\n" + _canon(event2) + "\n", encoding="utf-8")
    ledger = MethodLedger(path)
    with pytest.raises(ValueError, match="reconciliation"):
        ledger.outcomes()
    before = path.read_bytes()
    with pytest.raises(ValueError, match="reconciliation"):
        ledger.append(outcome(session="new"))
    assert path.read_bytes() == before

    event2["digest"] = "bad"
    path.write_text(_canon(event1) + "\n" + _canon(event2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        ledger.events()


@pytest.mark.parametrize("sequence", [True, 1.0])
def test_noninteger_historical_sequence_rejected_even_with_valid_hash(tmp_path, sequence):
    path = tmp_path / "bad-sequence.jsonl"
    body = {"sequence": sequence, "previous_digest": None, "payload": asdict(outcome())}
    path.write_text(_canon({**body, "digest": _hash(body)}) + "\n")
    with pytest.raises(ValueError, match="sequence"):
        MethodLedger(path).events()


@pytest.mark.parametrize("utility", [True, float("inf"), float("-inf")])
def test_invalid_utility_is_rejected_before_creating_journal(tmp_path, utility):
    ledger = MethodLedger(tmp_path / "invalid.jsonl")
    with pytest.raises(ValueError, match="utility"):
        ledger.append(outcome(utility=utility))
    assert not ledger.path.exists()
