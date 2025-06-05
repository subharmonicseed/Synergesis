from synergesis.analysis.fusion_engine import FusionEngine


def test_fusion_engine_fuse():
    engine = FusionEngine()
    result = engine.fuse([])
    assert result["concept_type"] == "FUSED_GLYPH"
