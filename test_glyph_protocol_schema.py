import json
from pathlib import Path

import jsonschema
import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger, to_wire


def load_schema():
    return json.loads(
        Path(__file__).with_name("glyph_protocol_v1.schema.json").read_text(encoding="utf-8")
    )


def test_generated_glyph_conforms_to_public_schema(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    glyph = graph.create(
        "observation",
        actor="sensor",
        content={"x": 1},
        external_refs=("obs-1",),
    )
    jsonschema.validate(to_wire(glyph), load_schema())


def test_generated_edge_conforms_to_public_schema(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    a = graph.create("concept", actor="syn", content={"name": "a"})
    b = graph.create("concept", actor="syn", content={"name": "b"})
    edge = graph.relate(a.glyph_id, b.glyph_id, "supports", actor="syn")
    jsonschema.validate(to_wire(edge), load_schema())


def test_generated_ledger_events_conform_to_public_schema(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    graph.create("concept", actor="syn", content={"name": "a"})
    for event in graph.ledger.events():
        jsonschema.validate(to_wire(event), load_schema())


def test_schema_rejects_historical_symbolic_glyph_as_protocol_object():
    bad = {
        "id": "g1",
        "polarité": "+",
        "fréquence": 72,
        "alignement": "Celestial",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_schema())
