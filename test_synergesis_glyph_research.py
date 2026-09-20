import pytest

from synergesis_audit_service_v2 import SynAuditServiceV2
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura


def build(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    return core, aura, graph


def test_ingest_creates_evidence_glyph_immediately(tmp_path):
    core, aura, graph = build(tmp_path)
    ev = aura.research_ingest(
        "https://example.test/a",
        "Source A",
        "Body A",
        "web",
    )
    matches = graph.ledger.find_by_external_ref(ev.evidence_id, glyph_type="evidence")
    assert len(matches) == 1
    assert matches[0].content["content_digest_only"] is True
    assert "Body A" not in str(matches[0].content)


def test_candidate_claim_is_derived_from_evidence(tmp_path):
    core, aura, graph = build(tmp_path)
    ev = aura.research_ingest("src", "Title", "Body", "web")
    claim = aura.research.propose_claim("Claim X", [ev.evidence_id])
    hyp = graph.ledger.find_by_external_ref(
        f"claim-state:{claim.claim_id}:candidate",
        glyph_type="hypothesis",
    )[0]
    trace = graph.upstream(hyp.glyph_id)
    assert any(g.glyph_type == "evidence" for g in trace.glyphs)


def test_approval_is_explicit_decision_and_versions_claim(tmp_path):
    core, aura, graph = build(tmp_path)
    ev = aura.research_ingest("src", "Title", "Body", "web")
    claim = aura.research.propose_claim("Claim X", [ev.evidence_id])
    approved = aura.research.approve(claim.claim_id, "human-reviewer")
    assert approved.status == "approved"

    decision = graph.ledger.find_by_external_ref(
        f"claim-review:{claim.claim_id}:approved",
        glyph_type="decision",
    )[0]
    assert decision.content["reviewer"] == "human-reviewer"

    states = graph.ledger.find_by_external_ref(claim.claim_id, glyph_type="hypothesis")
    assert [s.content["status"] for s in states] == ["candidate", "approved"]


def test_only_approved_claim_can_be_committed(tmp_path):
    core, aura, graph = build(tmp_path)
    ev = aura.research_ingest("src", "Title", "Body", "web")
    claim = aura.research.propose_claim("Claim X", [ev.evidence_id])

    with pytest.raises(ValueError, match="only approved claims"):
        aura.research.commit_approved_claim(
            claim.claim_id,
            core.memory,
            "subject",
            "predicate",
            "object",
            0.9,
        )


def test_committed_fact_traces_to_approved_claim_and_evidence(tmp_path):
    core, aura, graph = build(tmp_path)
    ev = aura.research_ingest("src", "Title", "Body", "web")
    claim = aura.research.propose_claim("Claim X", [ev.evidence_id])
    aura.research.approve(claim.claim_id, "reviewer")
    fact = aura.research.commit_approved_claim(
        claim.claim_id,
        core.memory,
        "subject",
        "predicate",
        "object",
        0.9,
    )

    report = SynAuditServiceV2(graph).why_fact(evidence_id=fact.evidence_id)
    ids = {g.glyph_id for g in report.provenance_glyphs}
    approved = graph.ledger.find_by_external_ref(
        f"claim-state:{claim.claim_id}:approved",
        glyph_type="hypothesis",
    )[0]
    evidence = graph.ledger.find_by_external_ref(
        ev.evidence_id,
        glyph_type="evidence",
    )[0]
    assert approved.glyph_id in ids
    assert evidence.glyph_id in ids


def test_rejected_claim_never_enters_memory(tmp_path):
    core, aura, graph = build(tmp_path)
    ev = aura.research_ingest("src", "Title", "Body", "web")
    claim = aura.research.propose_claim("Claim X", [ev.evidence_id])
    rejected = aura.research.reject(claim.claim_id, "reviewer")
    assert rejected.status == "rejected"
    with pytest.raises(ValueError, match="only approved claims"):
        aura.research.commit_approved_claim(
            claim.claim_id,
            core.memory,
            "s",
            "p",
            "o",
            0.8,
        )
    assert core.memory.count() == 0
