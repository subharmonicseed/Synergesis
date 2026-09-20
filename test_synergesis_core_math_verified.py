from fastapi.testclient import TestClient
import math

from SynergesisCore_MathVerified import app

client = TestClient(app)


def test_quantum_endpoint():
    r = client.post('/quantum/analyze', json={"state": [[1,0],[0,0]]})
    assert r.status_code == 400  # nested 2x2 is not a statevector


def test_quantum_endpoint_bell():
    s = [[0.7071067811865476,0],[0,0],[0,0],[0.7071067811865476,0]]
    # JSON complex encoding is not accepted as nested pairs; send real amplitudes.
    s = [0.7071067811865476, 0, 0, 0.7071067811865476]
    r = client.post('/quantum/analyze', json={"state": s, "keep_qubits": [0]})
    assert r.status_code == 200
    data = r.json()
    assert math.isclose(data['measurement_entropy_bits'], 1.0, abs_tol=1e-10)
    assert math.isclose(data['von_neumann_entropy_bits'], 0.0, abs_tol=1e-10)
    assert math.isclose(data['entanglement_entropy_bits'], 1.0, abs_tol=1e-10)


def test_definition_endpoint():
    r = client.get('/quantum/definition')
    assert r.status_code == 200
    assert 'hardware_energy' in r.json()
