from synergesis.ingestion.glyphifier import glyphify_sleep_phase


def test_glyphify_sleep_phase_stub():
    result = glyphify_sleep_phase("hello", "doc1", 0, "ts")
    glyphs = result["glyphs"]
    if glyphs:
        g = glyphs[0]
        assert g["id"] == "stub-glyph"
        assert g["status"] == "generated_from_llm"
        assert "timestamp" in g
        assert g["sourceIds"] == ["doc1"]
    assert "ctx_hash" in result
