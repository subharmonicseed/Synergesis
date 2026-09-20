from synergesis_audit_service import SynAuditService
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger


def build(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ev = graph.create(
        "evidence",
        actor="source",
        content={"title": "source"},
        external_refs=("ev-1",),
    )
    obs = graph.create("observation", actor="sensor", content={"x": 1})
    hyp = graph.create(
        "hypothesis",
        actor="syn",
        content={"statement": "h"},
        derived_from=(ev.glyph_id, obs.glyph_id),
    )
    dec = graph.create(
        "decision",
        actor="syn",
        content={"decision": "act"},
        derived_from=(hyp.glyph_id,),
    )
    action = graph.create(
        "action",
        actor="syn",
        content={"action_type": "note.write"},
        derived_from=(dec.glyph_id,),
    )
    outcome = graph.create(
        "outcome",
        actor="executor",
        content={"success": True},
        derived_from=(action.glyph_id,),
    )
    return graph, ev, obs, hyp, dec, action, outcome


def test_why_decision_returns_source_provenance(tmp_path):
    graph, ev, obs, hyp, dec, action, outcome = build(tmp_path)
    report = SynAuditService(graph).why_decision(dec.glyph_id)
    assert report.decision.glyph_id == dec.glyph_id
    assert [x.glyph_id for x in report.evidence] == [ev.glyph_id]
    assert [x.glyph_id for x in report.observations] == [obs.glyph_id]
    assert [x.glyph_id for x in report.hypotheses] == [hyp.glyph_id]


def test_evidence_impact_returns_decision_and_action(tmp_path):
    graph, ev, obs, hyp, dec, action, outcome = build(tmp_path)
    report = SynAuditService(graph).evidence_impact(external_evidence_ref="ev-1")
    assert dec.glyph_id in {x.glyph_id for x in report.decisions}
    assert action.glyph_id in {x.glyph_id for x in report.actions}
    assert outcome.glyph_id in {x.glyph_id for x in report.outcomes}


def test_portable_snapshot_contains_integrity_checkpoint(tmp_path):
    graph, *_ = build(tmp_path)
    snapshot = SynAuditService(graph).portable_snapshot()
    assert snapshot["schema_version"] == "synergesis.glyph.v1"
    assert snapshot["checkpoint"]["event_count"] > 0
    assert snapshot["checkpoint"]["chain_head"]
    assert snapshot["checkpoint"]["merkle_root"]
    assert snapshot["glyphs"]
    assert snapshot["edges"]


def test_evidence_impact_requires_exactly_one_identifier(tmp_path):
    graph, *_ = build(tmp_path)
    service = SynAuditService(graph)
    import pytest
    with pytest.raises(ValueError, match="exactly one"):
        service.evidence_impact()
    with pytest.raises(ValueError, match="exactly one"):
        service.evidence_impact(
            evidence_glyph_id="g:x",
            external_evidence_ref="ev-1",
        )
