import multiprocessing as mp
import threading
import time
from dataclasses import replace
from uuid import uuid4

import synergesis_risk_budget as risk

import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_risk_budget import RiskBudgetLedger, RiskBudgetManager, RiskBudgetPolicy


def _manager(path, limit=1.0):
    return RiskBudgetManager(
        graph=GlyphAuditGraph(GlyphLedger(path / ("glyph-" + uuid4().hex + ".jsonl"))),
        ledger=RiskBudgetLedger(path / "budget.jsonl"),
        policy=RiskBudgetPolicy(budget_limit=limit, maximum_single_reservation=1.0),
    )


def _reserve_worker(path, directive, output, barrier):
    try:
        manager = _manager(path, limit=0.5)
        original_events = manager.ledger.events

        def delayed_events():
            result = original_events()
            time.sleep(0.03)
            return result

        manager.ledger.events = delayed_events
        barrier.wait(timeout=10)
        manager.reserve(
            directive_id=directive, action_type="diagnostic.run",
            strategy_key="diagnose", intervention="repair", amount=0.25,
        )
    except Exception as exc:  # communicate outcome across spawn boundary
        output.put(type(exc).__name__ + ":" + str(exc))
    else:
        output.put("ok")


def test_process_contention_cannot_overspend_or_corrupt_chain(tmp_path):
    ctx = mp.get_context("spawn")
    output = ctx.Queue()
    barrier = ctx.Barrier(4)
    processes = [ctx.Process(target=_reserve_worker, args=(tmp_path, f"d:{i}", output, barrier)) for i in range(4)]
    for process in processes:
        process.start()
    results = [output.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(20)
        assert process.exitcode == 0
    assert results.count("ok") == 2
    assert sum(result.startswith("ValueError:cumulative risk budget exhausted") for result in results) == 2
    ledger = RiskBudgetLedger(tmp_path / "budget.jsonl")
    assert ledger.verify()[0] == 2
    assert _manager(tmp_path, limit=0.5).state().reserved == pytest.approx(0.5)


def test_thread_contention_same_directive_allows_one_reservation(tmp_path):
    managers = [_manager(tmp_path), _manager(tmp_path)]
    barrier = threading.Barrier(2)
    results = []

    def attempt(manager):
        barrier.wait(timeout=10)
        try:
            manager.reserve(
                directive_id="same", action_type="diagnostic.run",
                strategy_key="diagnose", intervention="repair", amount=0.2,
            )
        except Exception as exc:
            results.append(exc)
        else:
            results.append(None)

    threads = [threading.Thread(target=attempt, args=(manager,)) for manager in managers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert results.count(None) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    assert RiskBudgetLedger(tmp_path / "budget.jsonl").verify()[0] == 1


def test_terminal_contention_has_one_terminal_event(tmp_path):
    first = _manager(tmp_path)
    reservation = first.reserve(
        directive_id="d", action_type="diagnostic.run",
        strategy_key="diagnose", intervention="repair", amount=0.2,
    )
    second = _manager(tmp_path)
    barrier = threading.Barrier(2)
    results = []

    def finish(manager, operation):
        barrier.wait(timeout=10)
        try:
            getattr(manager, operation)(reservation, cycle_id="cycle", proposal_id="proposal")
        except Exception as exc:
            results.append(exc)
        else:
            results.append(None)

    threads = [threading.Thread(target=finish, args=(manager, operation))
               for manager, operation in ((first, "consume"), (second, "release"))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert results.count(None) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    ledger = RiskBudgetLedger(tmp_path / "budget.jsonl")
    assert ledger.verify()[0] == 2
    assert ledger.events()[0].event_type == "reserved"
    assert ledger.events()[1].event_type in {"consumed", "released"}


def _hold_lock(path, ready, release):
    with RiskBudgetLedger(path / "budget.jsonl").transaction():
        ready.set()
        release.wait(15)


def test_process_lock_timeout_and_release_after_termination(tmp_path, monkeypatch):
    ctx = mp.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    process = ctx.Process(target=_hold_lock, args=(tmp_path, ready, release))
    process.start()
    try:
        assert ready.wait(10)
        monkeypatch.setattr(risk, "_LOCK_TIMEOUT_SECONDS", 0.1)
        with pytest.raises(TimeoutError):
            RiskBudgetLedger(tmp_path / "budget.jsonl").events()
    finally:
        process.terminate()
        process.join(10)
    assert not process.is_alive()
    assert RiskBudgetLedger(tmp_path / "budget.jsonl").events() == ()


def test_nested_instances_release_lock_after_exception(tmp_path):
    ledger = RiskBudgetLedger(tmp_path / "budget.jsonl")
    alias = RiskBudgetLedger(tmp_path / "sub" / ".." / "budget.jsonl")
    with pytest.raises(RuntimeError, match="injected"):
        with ledger.transaction(), alias.transaction(), ledger.transaction():
            raise RuntimeError("injected")
    ctx = mp.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    process = ctx.Process(target=_hold_lock, args=(tmp_path, ready, release))
    process.start()
    try:
        assert ready.wait(10)
    finally:
        release.set()
        process.join(10)
        if process.is_alive():
            process.terminate()
            process.join(10)
    assert process.exitcode == 0


@pytest.mark.parametrize("field", ["action_type", "strategy_key", "intervention", "event_id"])
def test_changed_reservation_identity_does_not_corrupt_ledger(tmp_path, field):
    manager = _manager(tmp_path)
    reservation = manager.reserve(directive_id="d", action_type="a",
                                  strategy_key="s", intervention="i", amount=0.2)
    with pytest.raises(ValueError, match="identity mismatch"):
        manager.consume(replace(reservation, **{field: "different"}), cycle_id="c", proposal_id="p")
    assert manager.ledger.verify()[0] == 1
    manager.consume(reservation, cycle_id="c", proposal_id="p")
    assert manager.state().consumed == pytest.approx(0.2)


def test_unsupported_locking_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(risk, "fcntl", None)
    with pytest.raises(RuntimeError, match="POSIX"):
        RiskBudgetLedger(tmp_path / "budget.jsonl")


def _fork_attempt(path, output):
    try:
        RiskBudgetLedger(path / "budget.jsonl").events()
    except RuntimeError as exc:
        output.put(str(exc))
    else:
        output.put("unsafe")


def test_fork_inherited_lock_state_is_rejected(tmp_path):
    ctx = mp.get_context("fork")
    output = ctx.Queue()
    ledger = RiskBudgetLedger(tmp_path / "budget.jsonl")
    with ledger.transaction():
        process = ctx.Process(target=_fork_attempt, args=(tmp_path, output))
        process.start()
        result = output.get(timeout=10)
        process.join(10)
    assert process.exitcode == 0
    assert "spawn" in result


def test_thread_lock_timeout_is_bounded(tmp_path, monkeypatch):
    ledger = RiskBudgetLedger(tmp_path / "budget.jsonl")
    other = RiskBudgetLedger(tmp_path / "budget.jsonl")
    errors = []

    def attempt():
        try:
            other.events()
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr(risk, "_LOCK_TIMEOUT_SECONDS", 0.1)
    with ledger.transaction():
        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=2)
        assert not thread.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], TimeoutError)
    assert other.events() == ()


def test_graph_failure_keeps_budget_reserved_and_unlocks(tmp_path, monkeypatch):
    manager = _manager(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("graph unavailable")

    monkeypatch.setattr(manager.graph, "create", fail)
    with pytest.raises(OSError, match="graph unavailable"):
        manager.reserve(directive_id="d", action_type="a", strategy_key="s",
                        intervention="i", amount=0.8)
    other = _manager(tmp_path)
    with pytest.raises(ValueError, match="budget exhausted"):
        other.reserve(directive_id="d2", action_type="a", strategy_key="s",
                      intervention="i", amount=0.3)
    assert other.state().reserved == pytest.approx(0.8)
