import math
import numpy as np

from synergesis_quantum_engine import (
    compare_states,
    entanglement_entropy_bits,
    effective_support,
    hamiltonian_energy,
    l1_coherence,
    landauer_minimum_energy,
    quantum_state_report,
    reduced_density_matrix_for_qubits,
)
from synergesis_math import density_matrix, purity


def test_basis_report():
    r = quantum_state_report([1, 0])
    assert r.qubits == 1
    assert math.isclose(r.norm, 1.0)
    assert math.isclose(r.measurement_entropy_bits, 0.0)
    assert math.isclose(r.von_neumann_entropy_bits, 0.0, abs_tol=1e-12)
    assert math.isclose(r.purity, 1.0, abs_tol=1e-12)
    assert math.isclose(r.l1_coherence, 0.0, abs_tol=1e-12)
    assert math.isclose(r.effective_support, 1.0)


def test_plus_state_has_one_bit_measurement_entropy_and_unit_normalized_l1_coherence():
    plus = np.array([1, 1], dtype=complex) / math.sqrt(2)
    r = quantum_state_report(plus)
    assert math.isclose(r.measurement_entropy_bits, 1.0, abs_tol=1e-12)
    assert math.isclose(r.von_neumann_entropy_bits, 0.0, abs_tol=1e-12)
    assert math.isclose(r.l1_coherence, 1.0, abs_tol=1e-12)
    assert math.isclose(r.effective_support, 2.0, abs_tol=1e-12)


def test_bell_state_entanglement_entropy():
    bell = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2)
    reduced = reduced_density_matrix_for_qubits(bell, [0])
    assert np.allclose(reduced, np.eye(2) / 2)
    assert math.isclose(purity(reduced), 0.5, abs_tol=1e-12)
    assert math.isclose(entanglement_entropy_bits(bell, [0]), 1.0, abs_tol=1e-12)


def test_bell_state_is_globally_pure():
    bell = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2)
    r = quantum_state_report(bell)
    assert math.isclose(r.purity, 1.0, abs_tol=1e-12)
    assert math.isclose(r.von_neumann_entropy_bits, 0.0, abs_tol=1e-12)
    assert math.isclose(r.measurement_entropy_bits, 1.0, abs_tol=1e-12)


def test_hamiltonian_energy():
    z = np.diag([1.0, -1.0]).astype(complex)
    plus = np.array([1, 1], dtype=complex) / math.sqrt(2)
    assert math.isclose(hamiltonian_energy([1, 0], z), 1.0)
    assert math.isclose(hamiltonian_energy([0, 1], z), -1.0)
    assert math.isclose(hamiltonian_energy(plus, z), 0.0, abs_tol=1e-12)


def test_state_comparison():
    a = np.array([1, 0], dtype=complex)
    b = np.array([0, 1], dtype=complex)
    values = compare_states(a, b)
    assert math.isclose(values["fidelity"], 0.0)
    assert math.isclose(values["trace_distance"], 1.0)


def test_landauer_bound():
    expected = 1.380649e-23 * 300.0 * math.log(2.0)
    assert math.isclose(landauer_minimum_energy(1, 300), expected, rel_tol=1e-15)
    assert landauer_minimum_energy(0, 300) == 0.0


def test_effective_support():
    assert math.isclose(effective_support([0.25, 0.25, 0.25, 0.25]), 4.0)
