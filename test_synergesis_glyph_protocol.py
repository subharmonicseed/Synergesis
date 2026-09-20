import json
import pytest

from synergesis_glyph_protocol import (
    GlyphAuditGraph,
    GlyphLedger,
    SCHEMA_VERSION,
)


def graph(tmp_path):
    return GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))


def test_create_typed_glyph_and_verify_chain(tmp_path):
    g = graph(tmp_path)
    obs = g.create(
        "observation",
        actor="sensor",
        content={"value": 3},
        external_refs=("obs-1",),
    )
    assert obs.schema_version == SCHEMA_VERSION
    checkpoint = g.ledger.verify()
    assert checkpoint.event_count == 1
    assert checkpoint.chain_head is not None
    assert checkpoint.merkle_root is not None


def test_derived_from_creates_queryable_upstream_trace(tmp_path):
    g = graph(tmp_path)
    ev = g.create("evidence", actor="source", content={"claim": "x"})
    hyp = g.create(
        "hypothesis",
        actor="syn",
        content={"statement": "x may imply y"},
        derived_from=(ev.glyph_id,),
    )
    dec = g.create(
        "decision",
        actor="syn",
        content={"decision": "test y"},
        derived_from=(hyp.glyph_id,),
    )
    trace = g.explain_decision(dec.glyph_id)
    assert {x.glyph_id for x in trace.glyphs} == {
        ev.glyph_id,
        hyp.glyph_id,
        dec.glyph_id,
    }


def test_impact_analysis_finds_downstream_dependents(tmp_path):
    g = graph(tmp_path)
    ev = g.create("evidence", actor="source", content={"claim": "x"})
    hyp = g.create(
        "hypothesis",
        actor="syn",
        content={"statement": "h"},
        derived_from=(ev.glyph_id,),
    )
    dec = g.create(
        "decision",
        actor="syn",
        content={"decision": "d"},
        derived_from=(hyp.glyph_id,),
    )
    impact = g.impacted_by(ev.glyph_id)
    assert {x.glyph_id for x in impact.glyphs} == {
        ev.glyph_id,
        hyp.glyph_id,
        dec.glyph_id,
    }


def test_external_ref_deduplication_is_explicit(tmp_path):
    g = graph(tmp_path)
    a = g.create(
        "evidence",
        actor="source",
        content={"x": 1},
        external_refs=("ev-1",),
        dedupe_external_ref="ev-1",
    )
    b = g.create(
        "evidence",
        actor="source",
        content={"x": 999},
        external_refs=("ev-1",),
        dedupe_external_ref="ev-1",
    )
    assert a.glyph_id == b.glyph_id
    assert len(g.ledger.glyphs()) == 1


def test_unknown_relation_is_rejected(tmp_path):
    g = graph(tmp_path)
    a = g.create("concept", actor="syn", content={"name": "a"})
    b = g.create("concept", actor="syn", content={"name": "b"})
    with pytest.raises(ValueError, match="unsupported relation"):
        g.relate(a.glyph_id, b.glyph_id, "telepathy", actor="syn")


def test_dangling_edge_cannot_be_appended(tmp_path):
    g = graph(tmp_path)
    a = g.create("concept", actor="syn", content={"name": "a"})
    with pytest.raises(KeyError, match="unknown glyph"):
        g.relate(a.glyph_id, "g:missing", "supports", actor="syn")


def test_tampering_breaks_hash_chain(tmp_path):
    path = tmp_path / "glyphs.jsonl"
    g = GlyphAuditGraph(GlyphLedger(path))
    g.create("observation", actor="sensor", content={"value": 3})
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"value":3', '"value":4'), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity failure"):
        g.ledger.verify()


def test_sequence_deletion_breaks_chain(tmp_path):
    path = tmp_path / "glyphs.jsonl"
    g = GlyphAuditGraph(GlyphLedger(path))
    a = g.create("concept", actor="syn", content={"name": "a"})
    b = g.create("concept", actor="syn", content={"name": "b"})
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[1] + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sequence failure|chain failure"):
        g.ledger.verify()


def test_confidence_is_bounded(tmp_path):
    g = graph(tmp_path)
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        g.create(
            "hypothesis",
            actor="syn",
            content={"statement": "x"},
            confidence=1.2,
        )


def test_decision_explanation_requires_decision_type(tmp_path):
    g = graph(tmp_path)
    c = g.create("concept", actor="syn", content={"name": "x"})
    with pytest.raises(ValueError, match="decision glyph"):
        g.explain_decision(c.glyph_id)
