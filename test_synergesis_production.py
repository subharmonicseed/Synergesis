import pytest
from synergesis_production import fuse_glyphs_production, build_topology, evaluate_cortex

G = [
 {"id":"a","polarité":"+","alignement":"Harmonic","fréquence":10,"poids":2,"tags":["x"],"stability_score":0.9,"symbolic_uncertainty_score":0.2,"status":"ok"},
 {"id":"b","polarité":"-","alignement":"Void","fréquence":20,"poids":3,"tags":["y"],"stability_score":0.8,"symbolic_uncertainty_score":0.3,"status":"ok"},
]

def test_fusion_requires_real_inputs():
    out=fuse_glyphs_production(G)
    assert out["fréquence"] == pytest.approx(16)
    assert "entropy_score" not in out
    assert out["symbolic_uncertainty_score"] == pytest.approx(0.26)

def test_fusion_rejects_missing_data():
    bad=[dict(G[0]),dict(G[1])]; del bad[1]["poids"]
    with pytest.raises(ValueError): fuse_glyphs_production(bad)

def test_topology_is_bounded():
    edges=build_topology(G,{"fréquence":(0,100),"poids":(0,10)},1)
    assert len(edges)==1 and 0 <= edges[0].dissimilarity <= 1

def test_cortex_error_rate_is_bounded():
    out=evaluate_cortex(G,stability_min=.5,uncertainty_max=.8,error_rate_max=.1)
    assert 0 <= out.metrics["error_rate"] <= 1
