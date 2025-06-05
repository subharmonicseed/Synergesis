from synergesis.glyph_core import GlyphData, is_composite_polarity, is_composite_alignment


def test_helpers():
    assert is_composite_polarity({"positive": 1.0})
    assert is_composite_alignment({"Void": 1.0})
