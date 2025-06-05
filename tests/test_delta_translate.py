from synergesis.processing.delta_translate import translate_glyph


def test_translate_glyph():
    g = {"id": "a"}
    res = translate_glyph(g)
    assert res["translated"] == g
