import os
import sys

# Ensure project root is on the path
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from synergesis.ingestion.glyphifier import glyphify_sleep_phase


def test_glyphify_sleep_phase_tiny():
    result = glyphify_sleep_phase("hello world", "docX", 0, "ts")
    glyphs = result["glyphs"]
    assert len(glyphs) == 2
    for glyph in glyphs:
        assert "id" in glyph
        assert "status" in glyph
        assert "timestamp" in glyph
        assert "sourceIds" in glyph
