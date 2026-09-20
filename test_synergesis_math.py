import math
import numpy as np
import pytest

from synergesis_math import (
    bounded_error_rate,
    density_matrix,
    density_expectation_value,
    expectation_value,
    fidelity_statevectors,
    measurement_probabilities,
    normalize_statevector,
    purity,
    quantum_metrics,
    shannon_entropy,
    trace_distance_density_matrices,
    von_neumann_entropy,
)


def test_basis_state_invariants():
    psi = [1, 0]
    assert np.allclose(measurement_probabilities(psi), [1, 0])
    assert math.isclose(shannon_entropy([1, 0]), 0.0, abs_tol=1e-12)
    rho = density_matrix(psi)
    assert math.isclose(von_neumann_entropy(rho), 0.0, abs_tol=1e-12)
    assert math.isclose(purity(rho), 1.0, abs_tol=1e-12)


def test_bell_measurement_entropy_and_pure_state_entropy():
    bell = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2)
    metrics = quantum_metrics(bell)
    assert metrics.qubits == 2
    assert math.isclose(metrics.norm, 1.0, abs_tol=1e-12)
    assert math.isclose(metrics.measurement_entropy_bits, 1.0, abs_tol=1e-12)
    # Global Bell state is pure, so S(rho)=0; measurement entropy need not be 0.
    assert math.isclose(metrics.pure_state_von_neumann_entropy_bits, 0.0, abs_tol=1e-12)
    assert math.isclose(metrics.purity, 1.0, abs_tol=1e-12)


def test_maximally_mixed_qubit():
    rho = np.eye(2, dtype=complex) / 2
    assert math.isclose(von_neumann_entropy(rho), 1.0, abs_tol=1e-12)
    assert math.isclose(purity(rho), 0.5, abs_tol=1e-12)


def test_fidelity_and_trace_distance():
    z = np.array([1, 0], dtype=complex)
    o = np.array([0, 1], dtype=complex)
    assert math.isclose(fidelity_statevectors(z, z), 1.0)
    assert math.isclose(fidelity_statevectors(z, o), 0.0)
    assert math.isclose(trace_distance_density_matrices(density_matrix(z), density_matrix(o)), 1.0)


def test_expectation_values():
    psi = np.array([1, 0], dtype=complex)
    h = np.diag([2.5, -1.0]).astype(complex)
    assert math.isclose(expectation_value(psi, h), 2.5, abs_tol=1e-12)
    assert math.isclose(density_expectation_value(density_matrix(psi), h), 2.5, abs_tol=1e-12)


def test_normalization_is_deterministic():
    psi = normalize_statevector([2, 0])
    assert np.allclose(psi, [1, 0])


@pytest.mark.parametrize("bad", [[0, 0], [1, np.nan]])
def test_invalid_state_rejected(bad):
    with pytest.raises(ValueError):
        normalize_statevector(bad)


def test_error_rate_is_bounded():
    assert bounded_error_rate([False, True, True, False]) == 0.5
    assert 0.0 <= bounded_error_rate([False, True]) <= 1.0
