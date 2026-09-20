import math
import numpy as np
from synergesis_canonical import *

def test_quantum_basic():
    psi = np.array([1, 1], complex) / math.sqrt(2)
    r = quantum_report(psi)
    assert math.isclose(r.norm, 1)
    assert math.isclose(r.measurement_entropy_bits, 1)
    assert math.isclose(r.von_neumann_entropy_bits, 0, abs_tol=1e-10)
    assert math.isclose(r.purity, 1)
    assert math.isclose(r.effective_support, 2)

def test_bell_entanglement():
    bell = np.zeros(4, complex)
    bell[0] = bell[3] = 1 / math.sqrt(2)
    rho_a = reduced_density_matrix(bell, [0])
    assert np.allclose(rho_a, np.eye(2) / 2)
    assert math.isclose(entanglement_entropy(bell, [0]), 1, abs_tol=1e-10)

def test_fidelity_trace_distance():
    z = np.array([1,0], complex)
    p = np.array([1,1], complex) / math.sqrt(2)
    assert math.isclose(fidelity(z,z), 1)
    assert math.isclose(fidelity(z,p), .5)
    assert math.isclose(trace_distance(density_matrix(z), density_matrix(p)), math.sqrt(.5), rel_tol=1e-10)

def test_energy_is_hamiltonian_expectation():
    z = np.array([1,0], complex)
    H = np.diag([2., 5.])
    assert math.isclose(expectation(z,H), 2)

def test_fusion_has_no_dummy_entropy():
    a={"id":"a","polarité":"+","fréquence":60,"poids":2,"tags":["x"]}
    b={"id":"b","polarité":"-","fréquence":80,"poids":1,"tags":["y"]}
    f=fuse_glyphs([a,b])
    assert math.isclose(f["fréquence"], (60*2+80*1)/3)
    assert math.isclose(f["poids"], 2 + .9*1)
    assert "entropy_score" not in f

def test_error_rate_is_bounded():
    m=reflexive_metrics([
        {"id":"a","alignement":"Error","polarité":"-"},
        {"id":"b","alignement":"Harmonic","polarité":"+"},
    ])
    assert math.isclose(m.error_rate, .5)

def test_invalid_inputs_fail_closed():
    for bad in ([0,0], [float("nan"),0]):
        try:
            normalize_state(bad)
            assert False
        except ValueError:
            pass
