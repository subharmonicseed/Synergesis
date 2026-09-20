import pytest

from synergesis_cognitive_core import Rule
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_audit_service_v2 import SynAuditServiceV2


def build(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    return core, graph


def test_remember_creates_fact_glyph(tmp_path):
    core, graph = build(tmp_path)
    fact = core.remember(
        "market",
        "trend",
        "up",
        source="sensor",
        confidence=0.9,
        evidence_id="ev-market-1",
    )
    matches = graph.ledger.find_by_external_ref("ev-market-1", glyph_type="fact")
    assert len(matches) == 1
    assert matches[0].content["subject"] == "market"
    assert matches[0].confidence == 0.9


def test_fact_links_to_existing_evidence_glyph(tmp_path):
    core, graph = build(tmp_path)
    evidence = graph.create(
        "evidence",
        actor="source:web",
        content={"title": "Source"},
        external_refs=("ev-1",),
    )
    core.remember(
        "x",
        "is",
        "true",
        source="approved-evidence",
        confidence=0.8,
        evidence_id="ev-1",
    )
    fact = graph.ledger.find_by_external_ref("ev-1", glyph_type="fact")[0]
    trace = graph.upstream(fact.glyph_id)
    assert evidence.glyph_id in {g.glyph_id for g in trace.glyphs}


def test_thales_inference_has_premise_provenance(tmp_path):
    core, graph = build(tmp_path)
    premise = core.remember(
        "alice",
        "status",
        "verified",
        source="test",
        confidence=0.95,
        evidence_id="premise-1",
    )
    rule = Rule(
        name="verified_implies_trusted",
        predicate="status",
        required_object="verified",
        conclusion_predicate="trust",
        conclusion_object="trusted",
    )
    cycle = core.cycle_once(rules=(rule,))
    assert cycle.inferred_count == 1

    inferred_facts = core.memory.query(
        subject="alice",
        predicate="trust",
        object="trusted",
    )
    assert len(inferred_facts) == 1
    conclusion = inferred_facts[0]

    report = SynAuditServiceV2(graph).why_fact(evidence_id=conclusion.evidence_id)
    assert len(report.inferences) == 1
    assert any(g.external_refs == ("premise-1",) for g in report.premise_facts)


def test_repeated_thales_cycle_does_not_collide(tmp_path):
    core, graph = build(tmp_path)
    core.remember(
        "alice",
        "status",
        "verified",
        source="test",
        confidence=0.95,
        evidence_id="premise-1",
    )
    rule = Rule(
        name="verified_implies_trusted",
        predicate="status",
        required_object="verified",
        conclusion_predicate="trust",
        conclusion_object="trusted",
    )
    first = core.cycle_once(rules=(rule,))
    second = core.cycle_once(rules=(rule,))
    assert first.inferred_count == 1
    assert second.inferred_count == 1
    assert len(core.memory.query(predicate="trust", object="trusted")) == 1


def test_world_state_is_versioned_and_supersedes_previous(tmp_path):
    core, graph = build(tmp_path)
    core.remember(
        "system", "state", "ready",
        source="test", confidence=1.0, evidence_id="f1",
    )
    first = core.cycle_once()
    core.remember(
        "system", "load", "high",
        source="test", confidence=0.8, evidence_id="f2",
    )
    second = core.cycle_once()

    service = SynAuditServiceV2(graph)
    one = service.world_state(first.cycle)
    two = service.world_state(second.cycle)
    assert one.world_state.content["fact_count"] == 1
    assert two.world_state.content["fact_count"] == 2
    assert [g.glyph_id for g in two.previous_world_states] == [
        one.world_state.glyph_id
    ]


def test_world_state_digest_matches_cognitive_cycle(tmp_path):
    core, graph = build(tmp_path)
    core.remember(
        "x", "y", "z",
        source="test", confidence=1.0, evidence_id="f1",
    )
    cycle = core.cycle_once()
    world = SynAuditServiceV2(graph).world_state(cycle.cycle)
    assert world.world_state.content["world_digest"] == cycle.world_digest


def test_unknown_fact_query_is_explicit(tmp_path):
    core, graph = build(tmp_path)
    with pytest.raises(KeyError, match="unknown fact evidence id"):
        SynAuditServiceV2(graph).why_fact(evidence_id="missing")
