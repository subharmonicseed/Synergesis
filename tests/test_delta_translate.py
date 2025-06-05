from synergesis.processing.glyph_enricher import enrich_glyph


def test_enrich_glyph():
    g = {"id": "a"}
    enriched = enrich_glyph(g)
    assert "semantic_hash" in enriched
