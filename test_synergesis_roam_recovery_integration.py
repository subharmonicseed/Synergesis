"""Recovery through the actual integrated stack with a counted source adapter."""
import pytest

from synergesis_roam_attention import RoamAttentionController
from synergesis_roam_service import RoamServiceLedger, SynRoamService
from test_synergesis_roam_attention import need
from test_synergesis_secure_roam_stack_v2 import SourceAdapter, build


def test_stack_repairs_missing_service_receipt_without_researching_again(tmp_path, monkeypatch):
    calls = []
    search = SourceAdapter.search

    def counted(self, **kwargs):
        calls.append(kwargs)
        return search(self, **kwargs)

    monkeypatch.setattr(SourceAdapter, "search", counted)
    stack = build(tmp_path)
    item = need("Does this repair remain auditable?", 0.8)
    stack.agenda.add(item)
    service = stack.service

    def fail(tick):
        raise OSError("injected service receipt failure")

    monkeypatch.setattr(service.ledger, "append", fail)
    with pytest.raises(OSError, match="injected"):
        service.tick_once()
    state = stack.agenda.get(item.need_id)
    assert state.status == "researched"
    assert len(calls) == 1
    restarted = SynRoamService(
        controller=RoamAttentionController(agenda=stack.agenda, roam=service.controller.roam),
        ledger=RoamServiceLedger(service.ledger.path), limits=service.limits,
    )
    assert restarted.tick_once().status == "idle"
    records = restarted.ledger.records()
    assert [(r.status, r.need_id, r.session_id) for r in records] == [
        ("researched", item.need_id, state.session_id), ("idle", None, None),
    ]
    assert len(calls) == 1


def test_stack_uncertain_research_stops_before_any_new_source_request(tmp_path, monkeypatch):
    calls = []
    search = SourceAdapter.search

    def counted(self, **kwargs):
        calls.append(kwargs)
        return search(self, **kwargs)

    monkeypatch.setattr(SourceAdapter, "search", counted)
    stack = build(tmp_path)
    item = need("What happens after an interrupted search?", 0.8)
    stack.agenda.add(item)
    controller = stack.service.controller
    research = controller.roam.research_once

    def interrupted(question):
        research(question)
        raise OSError("effect occurred, outcome not returned")

    monkeypatch.setattr(controller.roam, "research_once", interrupted)
    with pytest.raises(OSError):
        controller.tick_once()
    assert len(calls) == 1
    restarted = RoamAttentionController(agenda=stack.agenda, roam=controller.roam)
    with pytest.raises(RuntimeError):
        restarted.tick_once()
    assert len(calls) == 1
    assert stack.agenda.get(item.need_id).status == "pending"
