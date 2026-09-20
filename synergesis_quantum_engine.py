"""Synergesis Quantum Engine — production mathematical layer.

No physical quantity is inferred from arbitrary symbolic fields. Quantum-state
quantities are computed from standard definitions; hardware-energy accounting
is deliberately separate because a statevector alone contains no information
about wall-plug power, runtime, cooling, or device efficiency.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Sequence

import numpy as np

from synergesis_math import (
    density_expectation_value,
    density_matrix,
    expectation_value,
    fidelity_statevectors,
    measurement_probabilities,
    purity,
    shannon_entropy,
    trace_distance_density_matrices,
    von_neumann_entropy,
)


@dataclass(frozen=True)
class QuantumStateReport:
    dimension: int
    qubits: int
    norm: float
    measurement_entropy_bits: float
    von_neumann_entropy_bits: float
    purity: float
    l1_coherence: float
    effective_support: float

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_qubit_dimension(dimension: int) -> int:
    if dimension <= 0 or dimension & (dimension - 1):
        raise ValueError("Dimension must be a positive power of two.")
    return int(math.log2(dimension))


def l1_coherence(rho: np.ndarray, *, normalize: bool = True) -> float:
    """Baumgratz l1 coherence: sum_{i != j}|rho_ij|.

    Optional normalization divides by d-1, yielding [0,1] for a d-dimensional
    quantum state. The unnormalized definition is the canonical quantity.
    """
    rho = np.asarray(rho, dtype=np.complex128)
    d = rho.shape[0] if rho.ndim == 2 and rho.shape[0] == rho.shape[1] else 0
    if d == 0:
        raise ValueError("rho must be a non-empty square matrix.")
    value = float(np.sum(np.abs(rho)) - np.sum(np.abs(np.diag(rho))))
    if normalize:
        if d == 1:
            return 0.0
        # For density matrices, C_l1 <= d-1. This normalized form is useful
        # for cross-dimensional dashboards, while retaining the exact metric.
        value /= d - 1
    return float(max(0.0, value))


def effective_support(probabilities: Sequence[float]) -> float:
    """Inverse participation ratio: 1 / sum_i p_i^2."""
    p = np.asarray(probabilities, dtype=float)
    # Delegate probability validation to Shannon entropy without using its value.
    shannon_entropy(p)
    denom = float(np.sum(p ** 2))
    if denom <= 0:
        raise RuntimeError("Probability invariant failed: sum(p^2) must be > 0.")
    return float(1.0 / denom)


def reduced_density_matrix_for_qubits(
    state: Sequence[complex] | np.ndarray,
    keep_qubits: Sequence[int],
) -> np.ndarray:
    """Partial trace of a pure n-qubit state, keeping selected qubits.

    Qubit numbering follows the conventional computational indexing used by
    Qiskit: q0 is the least-significant qubit in the basis label.
    """
    psi = np.asarray(state, dtype=np.complex128)
    if psi.ndim != 1 or psi.size == 0:
        raise ValueError("Statevector must be a non-empty vector.")
    n = _validate_qubit_dimension(psi.size)
    norm = np.linalg.norm(psi)
    if norm == 0:
        raise ValueError("Cannot reduce the zero vector.")
    psi = psi / norm

    keep = tuple(int(q) for q in keep_qubits)
    if len(set(keep)) != len(keep) or any(q < 0 or q >= n for q in keep):
        raise ValueError("keep_qubits must contain unique valid qubit indices.")
    trace = tuple(q for q in range(n) if q not in keep)

    # Array axis convention here is q_{n-1},...,q_0 so that q0 is least significant.
    tensor = psi.reshape([2] * n)
    rho = np.tensordot(tensor, np.conjugate(tensor), axes=0)
    # rho axes: ket axes [0..n-1], bra axes [n..2n-1].
    # Trace from highest axis down to avoid index shifts.
    current_n = n
    for q in sorted(trace, reverse=True):
        ket_axis = n - 1 - q
        bra_axis = current_n + (n - 1 - q)
        rho = np.trace(rho, axis1=ket_axis, axis2=bra_axis)
        current_n -= 1
    kept_order = sorted(keep)
    if tuple(keep) != tuple(kept_order):
        # Reorder remaining qubit axes to requested keep_qubits order.
        # The trace result is already a matrix after all traces.
        k = len(keep)
        pos = {q: i for i, q in enumerate(kept_order)}
        permutation = [pos[q] for q in keep]
        rho_tensor = rho.reshape([2] * k * 2)
        bra_perm = [p + k for p in permutation]
        rho = np.transpose(rho_tensor, permutation + bra_perm).reshape(2**k, 2**k)
    return np.asarray(rho, dtype=np.complex128)


def quantum_state_report(state: Sequence[complex] | np.ndarray) -> QuantumStateReport:
    psi = np.asarray(state, dtype=np.complex128)
    n = _validate_qubit_dimension(psi.size)
    norm = float(np.linalg.norm(psi))
    if norm == 0 or not np.isfinite(norm):
        raise ValueError("Statevector must have a finite non-zero norm.")
    psi = psi / norm
    probs = measurement_probabilities(psi)
    rho = density_matrix(psi)
    return QuantumStateReport(
        dimension=psi.size,
        qubits=n,
        norm=float(np.linalg.norm(psi)),
        measurement_entropy_bits=shannon_entropy(probs),
        von_neumann_entropy_bits=von_neumann_entropy(rho),
        purity=purity(rho),
        l1_coherence=l1_coherence(rho),
        effective_support=effective_support(probs),
    )


def entanglement_entropy_bits(state: Sequence[complex] | np.ndarray,
                              keep_qubits: Sequence[int]) -> float:
    """Von Neumann entropy of a reduced subsystem of a pure n-qubit state."""
    rho_reduced = reduced_density_matrix_for_qubits(state, keep_qubits)
    return von_neumann_entropy(rho_reduced)


def hamiltonian_energy(state: Sequence[complex] | np.ndarray,
                       hamiltonian: np.ndarray) -> float:
    """Physical expected energy E = <psi|H|psi>."""
    return expectation_value(state, hamiltonian)


def mixed_state_energy(rho: np.ndarray, hamiltonian: np.ndarray) -> float:
    """Physical expected energy E = Tr(rho H)."""
    return density_expectation_value(rho, hamiltonian)


def landauer_minimum_energy(erased_bits: float, temperature_kelvin: float) -> float:
    """Thermodynamic lower bound k_B T ln(2) per irreversibly erased bit.

    This is a lower bound, not a hardware consumption estimate.
    Returns joules.
    """
    if not np.isfinite(erased_bits) or erased_bits < 0:
        raise ValueError("erased_bits must be finite and non-negative.")
    if not np.isfinite(temperature_kelvin) or temperature_kelvin <= 0:
        raise ValueError("temperature_kelvin must be finite and > 0.")
    k_B = 1.380649e-23  # J/K, exact SI definition
    return float(erased_bits * k_B * temperature_kelvin * math.log(2.0))


def compare_states(state_a: Sequence[complex] | np.ndarray,
                   state_b: Sequence[complex] | np.ndarray) -> dict:
    """Return standard pure-state similarity/distance quantities."""
    rho_a = density_matrix(state_a)
    rho_b = density_matrix(state_b)
    return {
        "fidelity": fidelity_statevectors(state_a, state_b),
        "trace_distance": trace_distance_density_matrices(rho_a, rho_b),
    }
