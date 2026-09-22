import json

import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_roam_attention import (
    AttentionMeasurements,
    AttentionWeights,
    ResearchAgenda,
    ResearchNeed,
)


def make_stack(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    agenda = ResearchAgenda(
        tmp_path / "agenda.jsonl",
        graph=graph,
        weights=AttentionWeights(1, 1, 1, 1),
    )
    return graph, agenda


def make_need(question="recovery"):
    return ResearchNeed.create(
        domain="science", question=question, hypothesis="H", reason="gap",
        measurements=AttentionMeasurements(.5, .5, .5, .5),
    )


def test_invalid_parent_does_not_change_either_ledger(tmp_path):
    graph, agenda = make_stack(tmp_path)
    need = ResearchNeed.create(
        domain="science", question="bad", hypothesis=None, reason="gap",
        source_glyph_ids=("g:missing",),
        measurements=AttentionMeasurements(.5, .5, .5, .5),
    )
    before_graph = graph.ledger.verify().event_count
    with pytest.raises(KeyError):
        agenda.add(need)
    assert not (tmp_path / "agenda.jsonl").exists()
    assert not (tmp_path / "agenda.jsonl.pending").exists()
    assert graph.ledger.verify().event_count == before_graph


def test_restart_recovers_crash_before_graph_create(tmp_path, monkeypatch):
    graph, agenda = make_stack(tmp_path)
    need = make_need()
    original = graph.create
    calls = [0]

    def fail_once(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("interrupted")
        return original(*args, **kwargs)

    monkeypatch.setattr(graph, "create", fail_once)
    with pytest.raises(RuntimeError):
        agenda.add(need)
    assert not (tmp_path / "agenda.jsonl").exists()
    monkeypatch.setattr(graph, "create", original)
    recovered = ResearchAgenda(tmp_path / "agenda.jsonl", graph=graph, weights=agenda.weights)
    assert recovered.get(need.need_id).status == "pending"
    assert len(graph.ledger.find_by_external_ref(need.need_id, glyph_type="goal")) == 1


def test_restart_recovers_crash_after_graph_create(tmp_path, monkeypatch):
    graph, agenda = make_stack(tmp_path)
    need = make_need("after graph")
    original = graph.create

    def create_then_fail(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(graph, "create", original)
        raise RuntimeError("interrupted")

    monkeypatch.setattr(graph, "create", create_then_fail)
    with pytest.raises(RuntimeError):
        agenda.add(need)
    recovered = ResearchAgenda(tmp_path / "agenda.jsonl", graph=graph, weights=agenda.weights)
    assert recovered.get(need.need_id).status == "pending"
    assert len(graph.ledger.find_by_external_ref(need.need_id, glyph_type="goal")) == 1


def test_recovery_is_idempotent_after_agenda_append(tmp_path):
    graph, agenda = make_stack(tmp_path)
    need = make_need("duplicate")
    original = agenda._append_event_if_needed

    def append_then_fail(event):
        original(event)
        raise RuntimeError("interrupted")

    agenda._append_event_if_needed = append_then_fail
    with pytest.raises(RuntimeError):
        agenda.add(need)
    rows = (tmp_path / "agenda.jsonl").read_text().splitlines()
    recovered = ResearchAgenda(tmp_path / "agenda.jsonl", graph=graph, weights=agenda.weights)
    assert len(recovered._events()) == len(rows) == 1
    assert len(graph.ledger.find_by_external_ref(need.need_id, glyph_type="goal")) == 1
    # A second restart consumes no new intent and emits no duplicate event.
    again = ResearchAgenda(tmp_path / "agenda.jsonl", graph=graph, weights=agenda.weights)
    assert len(again._events()) == 1


def test_legacy_jsonl_lifecycle_remains_supported(tmp_path):
    graph, agenda = make_stack(tmp_path)
    need = make_need("legacy")
    agenda.add(need)
    restored = ResearchAgenda(tmp_path / "agenda.jsonl", graph=graph, weights=agenda.weights)
    assert restored.get(need.need_id).status == "pending"
    assert restored.mark_researched(need.need_id, "session-1").status == "researched"


def test_legacy_orphan_is_flagged_for_explicit_reconciliation(tmp_path):
    graph, agenda = make_stack(tmp_path)
    need = make_need("orphan")
    event = agenda._event_for(need, "pending", None, None, 1)
    (tmp_path / "agenda.jsonl").write_text(json.dumps(event) + "\n")
    with pytest.raises(ValueError, match="missing graph projection"):
        ResearchAgenda(tmp_path / "agenda.jsonl", graph=graph, weights=agenda.weights)


def test_recovery_repairs_partial_graph_edges_with_fresh_objects(tmp_path, monkeypatch):
    from dataclasses import replace
    graph, agenda = make_stack(tmp_path)
    parent = graph.create('evidence', actor='test', content={'source': 'fixture'})
    need = replace(make_need(), source_glyph_ids=(parent.glyph_id,))
    original = graph.ledger.append_edge
    def fail_edge(**kwargs):
        raise OSError('interrupted before parent edge')
    monkeypatch.setattr(graph.ledger, 'append_edge', fail_edge)
    with pytest.raises(OSError):
        agenda.add(need)
    graph2, recovered = make_stack(tmp_path)
    glyph = graph2.ledger.find_by_external_ref(need.need_id, glyph_type='goal')[0]
    assert recovered.get(need.need_id).status == 'pending'
    assert {e.target for e in graph2.ledger.edges_from(glyph.glyph_id, relation='derived_from')} == {parent.glyph_id}
    graph2.ledger.verify()


def test_old_completed_intent_cannot_create_supersedes_cycle(tmp_path):
    graph, agenda = make_stack(tmp_path)
    need = make_need()
    agenda.add(need)
    old_event = agenda._events()[0]
    agenda.mark_researched(need.need_id, 'session1')
    agenda._write_intent(old_event)  # Simulate a leftover already-committed intent.
    graph2, recovered = make_stack(tmp_path)
    assert recovered.get(need.need_id).status == 'researched'
    assert len(recovered._events()) == 2
    goals = graph2.ledger.find_by_external_ref(need.need_id, glyph_type='goal')
    assert not graph2.ledger.edges_from(goals[0].glyph_id, relation='supersedes')
    assert [e.target for e in graph2.ledger.edges_from(goals[1].glyph_id, relation='supersedes')] == [goals[0].glyph_id]


def test_intent_keeps_original_score_after_configuration_change(tmp_path, monkeypatch):
    from dataclasses import replace
    graph, agenda = make_stack(tmp_path)
    need = replace(make_need(), measurements=AttentionMeasurements(.1, .9, .2, .4))
    def fail(event):
        raise OSError('agenda append unavailable')
    monkeypatch.setattr(agenda, '_append_event_if_needed', fail)
    with pytest.raises(OSError):
        agenda.add(need)
    old_score = graph.ledger.find_by_external_ref(need.need_id, glyph_type='goal')[0].content['attention_score']
    graph2 = GlyphAuditGraph(GlyphLedger(tmp_path / 'glyphs.jsonl'))
    recovered = ResearchAgenda(tmp_path / 'agenda.jsonl', graph=graph2, weights=AttentionWeights(0, 1, 0, 0), actor='new-actor')
    assert recovered.get(need.need_id).status == 'pending'
    assert graph2.ledger.find_by_external_ref(need.need_id, glyph_type='goal')[0].content['attention_score'] == old_score


def test_conflicting_existing_event_is_rejected_before_graph_mutation(tmp_path):
    graph, agenda = make_stack(tmp_path)
    need = make_need()
    agenda.add(need)
    event = {**agenda._events()[0], 'status': 'cancelled'}
    agenda._write_intent(event)
    before = graph.ledger.verify().event_count
    with pytest.raises(ValueError, match='conflicting agenda event'):
        make_stack(tmp_path)
    assert graph.ledger.verify().event_count == before
    assert len(agenda._events()) == 1


def test_legacy_projection_without_provenance_edges_is_rejected(tmp_path):
    from dataclasses import replace, asdict
    graph, agenda = make_stack(tmp_path)
    parent = graph.create('evidence', actor='test', content={})
    need = replace(make_need(), source_glyph_ids=(parent.glyph_id,))
    event = agenda._event_for(need, 'pending', None, None, 1)
    graph.create('goal', actor='SYN-ROAM', content={
        'kind': 'research_need', 'domain': need.domain, 'question': need.question,
        'hypothesis': need.hypothesis, 'reason': need.reason,
        'measurements': asdict(need.measurements), 'attention_score': .5,
        'status': 'pending', 'session_id': None},
        external_refs=(need.need_id, f'need-state:{need.need_id}:1'))
    (tmp_path / 'agenda.jsonl').write_text(json.dumps(event) + '\n')
    with pytest.raises(ValueError, match='links incomplete'):
        make_stack(tmp_path)
