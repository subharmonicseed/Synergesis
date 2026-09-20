from fastapi.testclient import TestClient
from SynergesisCore_Production import app

client = TestClient(app)

G = [
 {"id":"a","polarité":"+","alignement":"Harmonic","fréquence":10,"poids":2,"tags":["x"],"stability_score":0.9,"symbolic_uncertainty_score":0.2,"status":"ok"},
 {"id":"b","polarité":"-","alignement":"Void","fréquence":20,"poids":3,"tags":["y"],"stability_score":0.8,"symbolic_uncertainty_score":0.3,"status":"ok"},
]

def test_definition():
    r = client.get('/definition')
    assert r.status_code == 200
    assert 'hardware_energy' in r.json()['quantum']

def test_fusion_endpoint():
    r = client.post('/glyph/fuse', json={'glyphs': G})
    assert r.status_code == 200
    assert r.json()['fréquence'] == 16

def test_topology_endpoint():
    r = client.post('/topology/build', json={'glyphs': G, 'ranges': {'fréquence':[0,100], 'poids':[0,10]}, 'max_dissimilarity':1})
    assert r.status_code == 200
    assert len(r.json()['edges']) == 1

def test_missing_fusion_data_rejected():
    bad = [dict(x) for x in G]
    del bad[1]['poids']
    r = client.post('/glyph/fuse', json={'glyphs': bad})
    assert r.status_code == 400

def test_quantum_endpoint():
    r = client.post('/quantum/analyze', json={'state': [1,0]})
    assert r.status_code == 200
    assert r.json()['dimension'] == 2
