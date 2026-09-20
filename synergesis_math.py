"""Verified mathematical core for Synergesis.

This module deliberately separates physically/mathematically defined quantities
from Synergesis design heuristics. No silent fallback or placeholder value is
used for a missing mathematical input: invalid inputs raise ValueError.

Quantum conventions:
- Statevectors are pure states |psi>, normalized to ||psi||_2 = 1.
- Measurement probabilities are p_i = |psi_i|^2.
- Shannon entropy is H(p) = -sum_i p_i log_2(p_i).
- For a density matrix rho, von Neumann entropy is
  S(rho) = -Tr(rho log_2 rho), purity = Tr(rho^2).
- Hamiltonian energy is E = <psi|H|psi> for a statevector, or Tr(rho H).
- A statevector alone does NOT determine hardware energy consumption.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import numpy as np


EPS = 1e-12


def _as_complex_vector(state: Sequence[complex] | np.ndarray) -> np.ndarray:
    psi = np.asarray(state, dtype=np.complex128)
    if psi.ndim != 1 or psi.size == 0:
        raise ValueError("Statevector must be a non-empty 1-D vector.")
    if not np.all(np.isfinite(psi.real)) or not np.all(np.isfinite(psi.imag)):
        raise ValueError("Statevector contains non-finite values.")
    return psi


def normalize_statevector(state: Sequence[complex] | np.ndarray, *, atol: float = 1e-10) -> np.ndarray:
    """Return a normalized statevector; reject the zero vector."""
    psi = _as_complex_vector(state)
    norm = np.linalg.norm(psi)
    if norm <= atol:
        raise ValueError("Cannot normalize the zero quantum state.")
    psi = psi / norm
    if not math.isclose(float(np.linalg.norm(psi)), 1.0, rel_tol=0.0, abs_tol=atol):
        raise RuntimeError("Internal normalization invariant failed.")
    return psi


def measurement_probabilities(state: Sequence[complex] | np.ndarray) -> np.ndarray:
    """Return computational-basis probabilities p_i = |psi_i|^2."""
    psi = normalize_statevector(state)
    p = np.abs(psi) ** 2
    p = np.real_if_close(p).astype(float)
    p /= p.sum()
    return p


def shannon_entropy(probabilities: Iterable[float], *, base: float = 2.0) -> float:
    """Shannon entropy of a probability distribution."""
    p = np.asarray(list(probabilities), dtype=float)
    if p.ndim != 1 or p.size == 0:
        raise ValueError("Probabilities must be a non-empty 1-D sequence.")
    if not np.all(np.isfinite(p)) or np.any(p < -EPS):
        raise ValueError("Invalid probabilities.")
    p = np.clip(p, 0.0, None)
    total = p.sum()
    if not math.isclose(float(total), 1.0, rel_tol=0.0, abs_tol=1e-10):
        raise ValueError("Probabilities must sum to 1.")
    if base <= 0 or math.isclose(base, 1.0):
        raise ValueError("Entropy base must be positive and different from 1.")
    nz = p[p > 0]
    return float(-np.sum(nz * (np.log(nz) / np.log(base))))


def density_matrix(state: Sequence[complex] | np.ndarray) -> np.ndarray:
    """Construct rho = |psi><psi| from a statevector."""
    psi = normalize_statevector(state)
    return np.outer(psi, np.conjugate(psi))


def _validate_density_matrix(rho: np.ndarray, *, atol: float = 1e-9) -> np.ndarray:
    rho = np.asarray(rho, dtype=np.complex128)
    if rho.ndim != 2 or rho.shape[0] != rho.shape[1] or rho.shape[0] == 0:
        raise ValueError("Density matrix must be a non-empty square matrix.")
    if not np.all(np.isfinite(rho.real)) or not np.all(np.isfinite(rho.imag)):
        raise ValueError("Density matrix contains non-finite values.")
    if not np.allclose(rho, rho.conj().T, atol=atol, rtol=0.0):
        raise ValueError("Density matrix must be Hermitian.")
    tr = float(np.trace(rho).real)
    if not math.isclose(tr, 1.0, rel_tol=0.0, abs_tol=atol):
        raise ValueError("Density matrix trace must equal 1.")
    eig = np.linalg.eigvalsh(rho)
    if np.min(eig) < -atol:
        raise ValueError("Density matrix must be positive semidefinite.")
    return rho


def von_neumann_entropy(rho: np.ndarray, *, base: float = 2.0) -> float:
    """S(rho) = -Tr[rho log_base(rho)]."""
    rho = _validate_density_matrix(rho)
    eig = np.linalg.eigvalsh(rho).real
    eig = np.clip(eig, 0.0, None)
    eig /= eig.sum()
    return shannon_entropy(eig, base=base)


def purity(rho: np.ndarray) -> float:
    """Purity P = Tr(rho^2), in [1/d, 1]."""
    rho = _validate_density_matrix(rho)
    value = float(np.trace(rho @ rho).real)
    return float(np.clip(value, 0.0, 1.0))


def fidelity_statevectors(state_a: Sequence[complex] | np.ndarray,
                          state_b: Sequence[complex] | np.ndarray) -> float:
    """Pure-state fidelity F = |<psi|phi>|^2."""
    a = normalize_statevector(state_a)
    b = normalize_statevector(state_b)
    if a.shape != b.shape:
        raise ValueError("Statevectors must have the same dimension.")
    value = float(abs(np.vdot(a, b)) ** 2)
    return float(np.clip(value, 0.0, 1.0))


def trace_distance_density_matrices(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    """Trace distance D(rho,sigma) = 1/2 ||rho-sigma||_1."""
    a = _validate_density_matrix(rho_a)
    b = _validate_density_matrix(rho_b)
    if a.shape != b.shape:
        raise ValueError("Density matrices must have the same shape.")
    diff = a - b
    # diff is Hermitian; its singular values are abs(eigenvalues).
    eig = np.linalg.eigvalsh(diff)
    value = 0.5 * float(np.sum(np.abs(eig)))
    return float(np.clip(value, 0.0, 1.0))


def expectation_value(state: Sequence[complex] | np.ndarray, observable: np.ndarray) -> float:
    """Compute <psi|O|psi> for a Hermitian observable O.

    The result is real by Hermiticity; numerical imaginary residue is discarded.
    """
    psi = normalize_statevector(state)
    op = np.asarray(observable, dtype=np.complex128)
    if op.ndim != 2 or op.shape != (psi.size, psi.size):
        raise ValueError("Observable shape must match state dimension.")
    if not np.allclose(op, op.conj().T, atol=1e-10, rtol=0.0):
        raise ValueError("Observable/Hamiltonian must be Hermitian.")
    value = np.vdot(psi, op @ psi)
    return float(np.real_if_close(value))


def density_expectation_value(rho: np.ndarray, observable: np.ndarray) -> float:
    """Compute Tr(rho O) for a Hermitian observable O."""
    rho = _validate_density_matrix(rho)
    op = np.asarray(observable, dtype=np.complex128)
    if op.ndim != 2 or op.shape != rho.shape:
        raise ValueError("Observable shape must match density matrix dimension.")
    if not np.allclose(op, op.conj().T, atol=1e-10, rtol=0.0):
        raise ValueError("Observable/Hamiltonian must be Hermitian.")
    value = np.trace(rho @ op)
    return float(np.real_if_close(value))


@dataclass(frozen=True)
class QuantumMetrics:
    dimension: int
    qubits: int
    norm: float
    measurement_entropy_bits: float
    pure_state_von_neumann_entropy_bits: float
    purity: float


def quantum_metrics(state: Sequence[complex] | np.ndarray) -> QuantumMetrics:
    """Compute invariant state metrics for a pure statevector."""
    psi = normalize_statevector(state)
    dim = psi.size
    if dim & (dim - 1):
        raise ValueError("Statevector dimension must be a power of two for qubits.")
    probs = measurement_probabilities(psi)
    rho = density_matrix(psi)
    return QuantumMetrics(
        dimension=dim,
        qubits=int(math.log2(dim)),
        norm=float(np.linalg.norm(psi)),
        measurement_entropy_bits=shannon_entropy(probs, base=2.0),
        pure_state_von_neumann_entropy_bits=von_neumann_entropy(rho, base=2.0),
        purity=purity(rho),
    )


# ------------------------ Design metrics (explicit heuristics) ------------------------


def normalized_range_distance(a: float, b: float, lo: float, hi: float) -> float:
    """Normalized absolute difference in [0,1]. This is a dissimilarity component."""
    if not all(np.isfinite([a, b, lo, hi])):
        raise ValueError("All distance inputs must be finite.")
    if hi <= lo:
        raise ValueError("hi must be greater than lo.")
    na = np.clip((a - lo) / (hi - lo), 0.0, 1.0)
    nb = np.clip((b - lo) / (hi - lo), 0.0, 1.0)
    return float(abs(na - nb))


def weighted_symbolic_dissimilarity(components: Sequence[tuple[float, float]]) -> float:
    """Weighted average of normalized dissimilarity components.

    Components are (weight, dissimilarity), with each dissimilarity in [0,1].
    This is intentionally called a dissimilarity, not a mathematical metric.
    """
    if not components:
        raise ValueError("At least one component is required.")
    total_w = 0.0
    total = 0.0
    for weight, value in components:
        if weight < 0 or not np.isfinite(weight) or not np.isfinite(value):
            raise ValueError("Weights must be finite and non-negative; values finite.")
        if not 0.0 <= value <= 1.0:
            raise ValueError("Component dissimilarities must lie in [0,1].")
        total_w += weight
        total += weight * value
    if total_w <= 0:
        raise ValueError("At least one positive weight is required.")
    return float(total / total_w)


def bounded_error_rate(error_indicators: Iterable[bool]) -> float:
    """Exact empirical error rate in [0,1]."""
    values = np.asarray(list(error_indicators), dtype=bool)
    if values.size == 0:
        raise ValueError("Cannot calculate error rate of an empty sample.")
    return float(values.mean())


if __name__ == "__main__":
    # Minimal self-check, independent of Qiskit.
    zero = np.array([1.0, 0.0], dtype=complex)
    plus = np.array([1.0, 1.0], dtype=complex) / math.sqrt(2)
    assert math.isclose(np.linalg.norm(normalize_statevector(zero)), 1.0)
    assert math.isclose(shannon_entropy([0.5, 0.5]), 1.0)
    assert math.isclose(von_neumann_entropy(density_matrix(zero)), 0.0, abs_tol=1e-10)
    assert math.isclose(purity(density_matrix(zero)), 1.0)
    assert math.isclose(fidelity_statevectors(zero, zero), 1.0)
    assert math.isclose(fidelity_statevectors(zero, plus), 0.5)
    assert math.isclose(expectation_value(zero, np.diag([0.0, 1.0])), 0.0)
    print("Synergesis mathematical self-check: PASS")
