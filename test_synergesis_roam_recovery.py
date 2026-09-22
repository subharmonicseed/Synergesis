"""Crash-boundary tests for ROAM's single-writer attempt receipts."""
import json
from dataclasses import dataclass
from pathlib import Path

import synergesis_roam_attention as attention
import synergesis_roam_service as service_module

import pytest

from synergesis_roam_attention import RoamTick
from synergesis_roam_service import RoamServiceLedger, RoamServiceLimits, ServiceTickRecord, SynRoamService


@dataclass(frozen=True)
class Session:
    session_id: str


class Controller:
    def __init__(self, tick):
        self.tick = tick
        self.calls = 0

    def tick_once(self):
        self.calls += 1
        return self.tick


def test_service_completed_receipt_repairs_ledger_after_restart(tmp_path):
    path = tmp_path / "service.jsonl"
    ledger = RoamServiceLedger(path)
    tick = RoamTick("n1", Session("s1"), "researched")
    body = {"sequence": 1, "status": "researched", "need_id": "n1",
            "session_id": "s1", "previous_digest": None}
    record = ServiceTickRecord(**body, digest=service_module._hash(body))
    marker = path.with_name(path.name + ".roam-attempt.json")
    payload = {"phase": "completed", "record": body | {"digest": record.digest},
               "schema": "syn-roam-service-attempt-v1"}
    payload["digest"] = service_module._hash({k: v for k, v in payload.items() if k != "digest"})
    marker.write_text(json.dumps(payload), encoding="utf-8")
    service = SynRoamService(controller=Controller(tick), ledger=ledger,
                             limits=RoamServiceLimits(1, True))
    assert service.tick_once().status == "researched"
    assert ledger.records()[0] == record
    assert not marker.exists()
    assert len(ledger.records()) == 2


def test_service_unknown_started_outcome_fails_closed(tmp_path):
    path = tmp_path / "service.jsonl"
    marker = path.with_name(path.name + ".roam-attempt.json")
    payload = {"phase": "started", "sequence": 1, "previous_digest": None,
               "tick_digest": "x", "schema": "syn-roam-service-attempt-v1"}
    from synergesis_roam_service import _hash
    payload["digest"] = _hash({k: v for k, v in payload.items() if k != "digest"})
    marker.write_text(json.dumps(payload), encoding="utf-8")
    service = SynRoamService(controller=Controller(RoamTick(None, None, "idle")),
                              ledger=RoamServiceLedger(path), limits=RoamServiceLimits(1, True))
    with pytest.raises(RuntimeError, match="unknown"):
        service.tick_once()


def test_service_conflicting_completed_receipt_is_rejected(tmp_path):
    path = tmp_path / "service.jsonl"
    ledger = RoamServiceLedger(path)
    ledger.append(RoamTick("n1", Session("s1"), "researched"))
    records = ledger.records()
    body = {"sequence": 1, "status": "researched", "need_id": "other",
            "session_id": "s2", "previous_digest": None}
    from synergesis_roam_service import _hash
    record = body | {"digest": _hash(body)}
    payload = {"phase": "completed", "record": record, "schema": "syn-roam-service-attempt-v1"}
    payload["digest"] = _hash({k: v for k, v in payload.items() if k != "digest"})
    path.with_name(path.name + ".roam-attempt.json").write_text(json.dumps(payload), encoding="utf-8")
    service = SynRoamService(controller=Controller(RoamTick(None, None, "idle")), ledger=ledger,
                             limits=RoamServiceLimits(1, True))
    with pytest.raises(ValueError, match="conflicting"):
        service.tick_once()


def test_service_writes_started_receipt_before_controller_effect(tmp_path):
    path = tmp_path / "service.jsonl"

    class Exploding:
        def __init__(self): self.calls = 0
        def tick_once(self):
            self.calls += 1
            raise OSError("controller effect failed")

    controller = Exploding()
    service = SynRoamService(controller=controller, ledger=RoamServiceLedger(path),
                             limits=RoamServiceLimits(1, True))
    with pytest.raises(OSError, match="controller effect failed"):
        service.tick_once()
    assert controller.calls == 1
    with pytest.raises(RuntimeError, match="unknown"):
        service.tick_once()
    assert controller.calls == 1
    restarted = SynRoamService(controller=Controller(RoamTick(None, None, "idle")),
                                ledger=RoamServiceLedger(path), limits=RoamServiceLimits(1, True))
    with pytest.raises(RuntimeError, match="unknown"):
        restarted.tick_once()
    assert restarted.controller.calls == 0


def test_controller_completion_receipt_clears_after_agenda_commit(tmp_path, monkeypatch):
    from test_synergesis_roam_attention import stack, need
    from synergesis_roam_attention import RoamAttentionController
    stack_graph, agenda, controller = stack(tmp_path)
    item = agenda.add(need("receipt cleanup", 0.9))
    marker = controller._attempt_path
    original = Path.unlink
    failed = False

    def fail_marker(self, *args, **kwargs):
        nonlocal failed
        if self == marker and not failed:
            failed = True
            raise OSError("crash after agenda commit")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_marker)
    with pytest.raises(OSError, match="agenda commit"):
        controller.tick_once()
    assert agenda.get(item.need.need_id).status == "researched"
    monkeypatch.undo()
    restarted = RoamAttentionController(agenda=agenda, roam=controller.roam)
    assert restarted.tick_once().status == "idle"
    assert not marker.exists()


def test_controller_completion_receipt_clears_for_already_evaluated_need(tmp_path):
    from test_synergesis_roam_attention import stack, need
    from synergesis_roam_attention import RoamAttentionController
    from synergesis_roam import OutcomeMetrics
    _, agenda, controller = stack(tmp_path)
    item = agenda.add(need("evaluated receipt", 0.9))
    tick = controller.tick_once()
    controller.evaluate_need(
        need_id=item.need.need_id,
        session=tick.session,
        metrics=OutcomeMetrics(0.8, 0.7, 0.6, 0.5, 0.4, 0.1, 0.2),
    )
    state = agenda.get(item.need.need_id)
    controller._write_attempt({
        "phase": "completed", "need_id": item.need.need_id,
        "need_digest": attention._hash(agenda._need_payload(state.need)),
        "sequence": item.event_count, "session_id": tick.session.session_id,
    })
    restarted = RoamAttentionController(agenda=agenda, roam=controller.roam)
    assert restarted.tick_once().status == "idle"
    assert not controller._attempt_path.exists()


def _write_service_receipt(path, record):
    from synergesis_roam_service import _hash
    payload = {"phase": "completed", "record": record,
               "schema": "syn-roam-service-attempt-v1"}
    payload["digest"] = _hash({k: v for k, v in payload.items() if k != "digest"})
    path.with_name(path.name + ".roam-attempt.json").write_text(json.dumps(payload), encoding="utf-8")


def test_service_rejects_corrupt_inner_record_before_controller(tmp_path):
    path = tmp_path / "service.jsonl"
    body = {"sequence": 1, "status": "idle", "need_id": None,
            "session_id": None, "previous_digest": None, "digest": "corrupt"}
    _write_service_receipt(path, body)
    controller = Controller(RoamTick(None, None, "idle"))
    service = SynRoamService(controller=controller, ledger=RoamServiceLedger(path),
                             limits=RoamServiceLimits(1, True))
    with pytest.raises(RuntimeError, match="operator review"):
        service.tick_once()
    assert controller.calls == 0
    assert not path.exists()


@pytest.mark.parametrize("sequence", [0, -1, True, False])
def test_service_rejects_invalid_receipt_sequence(tmp_path, sequence):
    path = tmp_path / "service.jsonl"
    body = {"sequence": sequence, "status": "idle", "need_id": None,
            "session_id": None, "previous_digest": None,
            "digest": "placeholder"}
    from synergesis_roam_service import _hash
    body["digest"] = _hash({k: v for k, v in body.items() if k != "digest"})
    _write_service_receipt(path, body)
    controller = Controller(RoamTick(None, None, "idle"))
    service = SynRoamService(controller=controller, ledger=RoamServiceLedger(path),
                             limits=RoamServiceLimits(1, True))
    with pytest.raises((ValueError, RuntimeError)):
        service.tick_once()
    assert controller.calls == 0


def test_controller_completed_receipt_repairs_agenda_without_new_research(tmp_path, monkeypatch):
    from test_synergesis_roam_attention import stack, need
    _, agenda, controller = stack(tmp_path)
    item = agenda.add(need("completion before agenda", 0.8))
    calls = []
    research = controller.roam.research_once

    def counted(question):
        calls.append(question)
        return research(question)

    def failed(*args):
        raise OSError("agenda unavailable")

    monkeypatch.setattr(controller.roam, "research_once", counted)
    with monkeypatch.context() as patch:
        patch.setattr(agenda, "mark_researched", failed)
        with pytest.raises(OSError, match="agenda unavailable"):
            controller.tick_once()
    assert agenda.get(item.need.need_id).status == "pending"
    reopened_agenda = attention.ResearchAgenda(
        agenda.path, graph=agenda.graph, weights=agenda.weights, actor=agenda.actor,
    )
    restarted = attention.RoamAttentionController(agenda=reopened_agenda, roam=controller.roam)
    assert restarted.tick_once().status == "idle"
    assert len(calls) == 1
    assert reopened_agenda.get(item.need.need_id).status == "researched"


def test_service_commit_before_marker_cleanup_replays_without_duplicate(tmp_path, monkeypatch):
    ledger = RoamServiceLedger(tmp_path / "service.jsonl")
    controller = Controller(RoamTick(None, None, "idle"))
    service = SynRoamService(controller=controller, ledger=ledger, limits=RoamServiceLimits(1, True))
    unlink = Path.unlink

    def failed(path, *args, **kwargs):
        if path == service._attempt_path:
            raise OSError("cleanup interrupted")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", failed)
        with pytest.raises(OSError, match="cleanup interrupted"):
            service.tick_once()
    assert len(ledger.records()) == 1
    restarted = SynRoamService(controller=controller, ledger=RoamServiceLedger(ledger.path), limits=service.limits)
    restarted.tick_once()
    assert len(ledger.records()) == 2
    assert controller.calls == 2  # One old tick and one new explicit tick.


@pytest.mark.parametrize("boundary", ["controller", "service"])
def test_receipt_creation_failure_prevents_call(tmp_path, monkeypatch, boundary):
    from test_synergesis_roam_attention import stack, need
    _, agenda, controller = stack(tmp_path)
    agenda.add(need("must not execute", 0.9))
    calls = []
    monkeypatch.setattr(controller.roam, "research_once", lambda question: calls.append(question))
    target = controller if boundary == "controller" else SynRoamService(
        controller=controller, ledger=RoamServiceLedger(tmp_path / "service.jsonl"),
        limits=RoamServiceLimits(1, True),
    )

    def failed(payload):
        raise OSError("receipt storage unavailable")

    monkeypatch.setattr(target, "_write_attempt", failed)
    with pytest.raises(OSError, match="storage unavailable"):
        target.tick_once()
    assert calls == []


@pytest.mark.parametrize("boundary", ["controller", "service"])
def test_corrupt_receipt_blocks_before_hooks_or_new_tick(tmp_path, boundary):
    from test_synergesis_roam_attention import stack
    _, _, controller = stack(tmp_path)
    calls = []
    controller.add_tick_hook(lambda: calls.append("hook"))
    target = controller if boundary == "controller" else SynRoamService(
        controller=controller, ledger=RoamServiceLedger(tmp_path / "service.jsonl"),
        limits=RoamServiceLimits(1, True),
    )
    target._attempt_path.write_text('{"truncated":', encoding="utf-8")
    with pytest.raises(RuntimeError, match="operator review"):
        target.tick_once()
    assert calls == []
