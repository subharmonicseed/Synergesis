"""
Synergesis Canonical Quantitative Core
======================================

Production-oriented quantitative layer:
- Quantum quantities use standard quantum-information definitions.
- Symbolic quantities are explicitly labeled as design metrics.
- No dummy constants are returned for missing inputs.
- No "kWh from statevector" inference is performed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


EPS = 1e-12


# ---------------------------------------------------------------------------
# Quantum information
# ---------------------------------------------------------------------------

def normalize_state(state: Sequence[complex] | np.ndarray) -> np.ndarray:
    psi = np.asarray(state, dtype=np.complex128)
    if psi.ndim != 1 or psi.size == 0:
        raise ValueError("Statevector must be a non-empty 1-D vector.")
    if not np.all(np.isfinite(psi.real)) or not np.all(np.isfinite(psi.imag)):
        raise ValueError("Statevector contains non-finite values.")
    norm = float(np.linalg.norm(psi))
    if norm <= EPS:
        raise ValueError("Zero state cannot be normalized.")
    return psi / norm


def probabilities(state: Sequence[complex] | np.ndarray) -> np.ndarray:
    psi = normalize_state(state)
    p = np.abs(psi) ** 2
    p = np.asarray(p, dtype=float)
    p /= p.sum()
    return p


def shannon_entropy(p: Iterable[float], base: float = 2.0) -> float:
    p = np.asarray(list(p), dtype=float)
    if p.ndim != 1 or p.size == 0:
        raise ValueError("Probability vector must be non-empty and 1-D.")
    if not np.all(np.isfinite(p)) or np.any(p < -EPS):
        raise ValueError("Invalid probability vector.")
    p = np.clip(p, 0.0, None)
    if not math.isclose(float(p.sum()), 1.0, abs_tol=1e-10):
        raise ValueError("Probabilities must sum to 1.")
    if base <= 0 or math.isclose(base, 1.0):
        raise ValueError("Entropy base must be > 0 and != 1.")
    nz = p[p > EPS]
    return float(-np.sum(nz * np.log(nz) / np.log(base)))


def density_matrix(state: Sequence[complex] | np.ndarray) -> np.ndarray:
    psi = normalize_state(state)
    return np.outer(psi, psi.conj())


def validate_density_matrix(rho: np.ndarray) -> np.ndarray:
    rho = np.asarray(rho, dtype=np.complex128)
    if rho.ndim != 2 or rho.shape[0] != rho.shape[1] or rho.size == 0:
        raise ValueError("Density matrix must be non-empty and square.")
    if not np.all(np.isfinite(rho.real)) or not np.all(np.isfinite(rho.imag)):
        raise ValueError("Density matrix contains non-finite values.")
    if not np.allclose(rho, rho.conj().T, atol=1e-9, rtol=0):
        raise ValueError("Density matrix must be Hermitian.")
    if not math.isclose(float(np.trace(rho).real), 1.0, abs_tol=1e-9):
        raise ValueError("Density matrix trace must equal 1.")
    eig = np.linalg.eigvalsh(rho).real
    if float(eig.min()) < -1e-9:
        raise ValueError("Density matrix must be positive semidefinite.")
    return rho


def von_neumann_entropy(rho: np.ndarray) -> float:
    rho = validate_density_matrix(rho)
    eig = np.clip(np.linalg.eigvalsh(rho).real, 0.0, None)
    eig /= eig.sum()
    return shannon_entropy(eig)


def purity(rho: np.ndarray) -> float:
    rho = validate_density_matrix(rho)
    return float(np.clip(np.trace(rho @ rho).real, 0.0, 1.0))


def fidelity(state_a: Sequence[complex] | np.ndarray,
             state_b: Sequence[complex] | np.ndarray) -> float:
    a, b = normalize_state(state_a), normalize_state(state_b)
    if a.shape != b.shape:
        raise ValueError("States must have the same dimension.")
    return float(np.clip(abs(np.vdot(a, b)) ** 2, 0.0, 1.0))


def trace_distance(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    a, b = validate_density_matrix(rho_a), validate_density_matrix(rho_b)
    if a.shape != b.shape:
        raise ValueError("Density matrices must have the same shape.")
    eig = np.linalg.eigvalsh(a - b).real
    return float(np.clip(0.5 * np.sum(np.abs(eig)), 0.0, 1.0))


def expectation(state: Sequence[complex] | np.ndarray,
                observable: np.ndarray) -> float:
    psi = normalize_state(state)
    op = np.asarray(observable, dtype=np.complex128)
    if op.shape != (psi.size, psi.size):
        raise ValueError("Observable shape does not match state dimension.")
    if not np.allclose(op, op.conj().T, atol=1e-10, rtol=0):
        raise ValueError("Observable/Hamiltonian must be Hermitian.")
    value = np.vdot(psi, op @ psi)
    return float(np.real_if_close(value))


def density_expectation(rho: np.ndarray, observable: np.ndarray) -> float:
    rho = validate_density_matrix(rho)
    op = np.asarray(observable, dtype=np.complex128)
    if op.shape != rho.shape:
        raise ValueError("Observable shape does not match density matrix.")
    if not np.allclose(op, op.conj().T, atol=1e-10, rtol=0):
        raise ValueError("Observable/Hamiltonian must be Hermitian.")
    return float(np.real_if_close(np.trace(rho @ op)))


def l1_coherence(rho: np.ndarray, normalized: bool = True) -> float:
    rho = validate_density_matrix(rho)
    d = rho.shape[0]
    value = float(np.sum(np.abs(rho)) - np.sum(np.abs(np.diag(rho))))
    if normalized and d > 1:
        value /= d - 1
    return float(max(0.0, value))


def effective_support(p: Iterable[float]) -> float:
    p = np.asarray(list(p), dtype=float)
    shannon_entropy(p)  # validation
    return float(1.0 / np.sum(p ** 2))


def _qubit_count(dimension: int) -> int:
    if dimension <= 0 or dimension & (dimension - 1):
        raise ValueError("Quantum-state dimension must be a positive power of two.")
    return int(math.log2(dimension))


def reduced_density_matrix(state: Sequence[complex] | np.ndarray,
                           keep_qubits: Sequence[int]) -> np.ndarray:
    """
    Partial trace for a pure n-qubit state.

    Qubit numbering follows Qiskit's convention: q0 is least-significant.
    The returned subsystem basis follows the order supplied in keep_qubits.
    """
    psi = normalize_state(state)
    n = _qubit_count(psi.size)
    keep = tuple(int(q) for q in keep_qubits)
    if len(set(keep)) != len(keep) or any(q < 0 or q >= n for q in keep):
        raise ValueError("keep_qubits contains invalid or duplicate indices.")

    # Explicit index construction avoids fragile axis bookkeeping.
    kept_dim = 2 ** len(keep)
    traced = tuple(q for q in range(n) if q not in keep)
    rho = np.zeros((kept_dim, kept_dim), dtype=np.complex128)

    def bits(index: int) -> list[int]:
        return [(index >> q) & 1 for q in range(n)]

    keep_masks = [bits(i) for i in range(psi.size)]
    for i in range(psi.size):
        bi = keep_masks[i]
        for j in range(psi.size):
            bj = keep_masks[j]
            if any(bi[q] != bj[q] for q in traced):
                continue
            ai = sum(bi[q] << k for k, q in enumerate(keep))
            aj = sum(bj[q] << k for k, q in enumerate(keep))
            rho[ai, aj] += psi[i] * np.conj(psi[j])
    return validate_density_matrix(rho)


def entanglement_entropy(state: Sequence[complex] | np.ndarray,
                         keep_qubits: Sequence[int]) -> float:
    return von_neumann_entropy(reduced_density_matrix(state, keep_qubits))


@dataclass(frozen=True)
class QuantumReport:
    dimension: int
    qubits: int
    norm: float
    measurement_entropy_bits: float
    von_neumann_entropy_bits: float
    purity: float
    l1_coherence_normalized: float
    effective_support: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def quantum_report(state: Sequence[complex] | np.ndarray) -> QuantumReport:
    psi = normalize_state(state)
    p = probabilities(psi)
    rho = density_matrix(psi)
    return QuantumReport(
        dimension=psi.size,
        qubits=_qubit_count(psi.size),
        norm=float(np.linalg.norm(psi)),
        measurement_entropy_bits=shannon_entropy(p),
        von_neumann_entropy_bits=von_neumann_entropy(rho),
        purity=purity(rho),
        l1_coherence_normalized=l1_coherence(rho, normalized=True),
        effective_support=effective_support(p),
    )


# Hardware energy is deliberately separate from quantum-state physics.
@dataclass(frozen=True)
class EnergyMeasurement:
    joules: float
    duration_seconds: float
    source: str

    @property
    def watts_average(self) -> float:
        if self.duration_seconds <= 0:
            raise ValueError("Duration must be positive.")
        return self.joules / self.duration_seconds

    @property
    def kwh(self) -> float:
        return self.joules / 3_600_000.0


# ---------------------------------------------------------------------------
# Symbolic layer: design metrics, explicitly not physical laws
# ---------------------------------------------------------------------------

POLARITY_VALUES = {"+": 1.0, "0": 0.0, "-": -1.0}
ALIGNMENT_VALUES = {
    "Celestial": 1.0, "Harmonic": 0.5, "Void": 0.0, "Chthonic": -0.5, "Error": -1.0
}


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if len(values) != len(weights) or not values:
        raise ValueError("Values and weights must have equal non-zero length.")
    v, w = np.asarray(values, float), np.asarray(weights, float)
    if np.any(~np.isfinite(v)) or np.any(~np.isfinite(w)) or np.any(w < 0):
        raise ValueError("Values must be finite and weights non-negative.")
    if float(w.sum()) <= 0:
        raise ValueError("At least one weight must be positive.")
    return float(np.dot(v, w) / w.sum())


def frequency_weighted_average(glyphs: Sequence[Mapping[str, Any]]) -> float:
    vals, weights = [], []
    for g in glyphs:
        if "fréquence" not in g or "poids" not in g:
            raise ValueError("Each glyph needs fréquence and poids for weighted averaging.")
        vals.append(float(g["fréquence"]))
        weights.append(float(g["poids"]))
    return weighted_mean(vals, weights)


def decayed_weight_sum(glyphs: Sequence[Mapping[str, Any]], decay: float = 0.9) -> float:
    if not 0.0 <= decay <= 1.0:
        raise ValueError("Decay must be in [0,1].")
    weights = [float(g["poids"]) for g in glyphs]
    if any(w < 0 or not math.isfinite(w) for w in weights):
        raise ValueError("Glyph weights must be finite and non-negative.")
    # Newer/earlier ordering is explicit: list order is treated as input order.
    return float(sum(w * decay ** i for i, w in enumerate(weights)))


def polarity_composition(glyphs: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    scores = {k: 0.0 for k in POLARITY_VALUES}
    total = 0.0
    for g in glyphs:
        p = g.get("polarité")
        w = float(g.get("poids", 1.0))
        if p not in POLARITY_VALUES or w < 0 or not math.isfinite(w):
            raise ValueError("Simple polarity (+,0,-) and finite non-negative weight required.")
        scores[p] += w
        total += w
    if total <= 0:
        raise ValueError("Total polarity weight must be positive.")
    return {k: v / total for k, v in scores.items() if v > 0}


def tag_jaccard_dissimilarity(a: Iterable[str], b: Iterable[str]) -> float:
    A, B = set(a), set(b)
    if not A and not B:
        return 0.0
    return 1.0 - len(A & B) / len(A | B)


def normalized_numeric_dissimilarity(a: float, b: float,
                                      lo: float, hi: float) -> float:
    if hi <= lo or not all(math.isfinite(x) for x in (a, b, lo, hi)):
        raise ValueError("Invalid numeric range.")
    na = np.clip((a - lo) / (hi - lo), 0.0, 1.0)
    nb = np.clip((b - lo) / (hi - lo), 0.0, 1.0)
    return float(abs(na - nb))


def weighted_symbolic_dissimilarity(components: Sequence[tuple[float, float]]) -> float:
    if not components:
        raise ValueError("At least one component is required.")
    total_w = sum(w for w, _ in components)
    if total_w <= 0:
        raise ValueError("Total weight must be positive.")
    for w, d in components:
        if w < 0 or not math.isfinite(w) or not 0 <= d <= 1 or not math.isfinite(d):
            raise ValueError("Weights must be non-negative and dissimilarities in [0,1].")
    return float(sum(w * d for w, d in components) / total_w)


def empirical_error_rate(errors: Iterable[bool]) -> float:
    x = np.asarray(list(errors), dtype=bool)
    if x.size == 0:
        raise ValueError("Cannot calculate an error rate from an empty sample.")
    return float(x.mean())


# ---------------------------------------------------------------------------
# Canonical glyph fusion
# ---------------------------------------------------------------------------

def fuse_glyphs(glyphs: Sequence[Mapping[str, Any]], decay: float = 0.9) -> dict[str, Any]:
    if len(glyphs) < 2:
        raise ValueError("Fusion requires at least two glyphs.")
    parents = [dict(g) for g in glyphs]
    ids = [g.get("id") for g in parents]
    if any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Every parent glyph must have a non-empty id.")

    frequencies = frequency_weighted_average(parents)
    weights = decayed_weight_sum(parents, decay=decay)
    polarity = polarity_composition(parents)

    tags = sorted(set(t for g in parents for t in g.get("tags", [])))
    result: dict[str, Any] = {
        "id": "fused-" + "-".join(ids),
        "sourceIds": sorted(set(ids)),
        "polarité": polarity,
        "fréquence": frequencies,
        "poids": weights,
        "tags": tags + ["fused"],
        "status": "fused",
        "details": {
            "fusion": {
                "frequency": "weight-normalized arithmetic mean",
                "weight": f"decayed_sum(decay={decay})",
                "polarity": "weight-normalized composition",
                "tags": "set union",
            }
        },
    }

    # An entropy value is NOT invented: only combine an explicitly supplied
    # uncertainty score. If old data contains entropy_score, it is not silently
    # treated as Shannon entropy.
    if all("symbolic_uncertainty_score" in g for g in parents):
        u = weighted_mean(
            [float(g["symbolic_uncertainty_score"]) for g in parents],
            [float(g.get("poids", 1.0)) for g in parents],
        )
        if not 0.0 <= u <= 1.0:
            raise ValueError("symbolic_uncertainty_score must be in [0,1].")
        result["symbolic_uncertainty_score"] = u

    return result


# ---------------------------------------------------------------------------
# Reflexive metrics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReflexiveMetrics:
    count: int
    mean_resonance: float | None
    mean_stability: float | None
    mean_uncertainty: float | None
    error_rate: float | None
    alignment_distribution: dict[str, float]
    polarity_distribution: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reflexive_metrics(glyphs: Sequence[Mapping[str, Any]]) -> ReflexiveMetrics:
    if not glyphs:
        return ReflexiveMetrics(0, None, None, None, None, {}, {})

    resonances = [float(g["resonance"]) for g in glyphs if "resonance" in g]
    stabilities = [float(g["stability_score"]) for g in glyphs if "stability_score" in g]
    uncertainties = [float(g["symbolic_uncertainty_score"])
                     for g in glyphs if "symbolic_uncertainty_score" in g]

    for arr, name in ((resonances, "resonance"), (stabilities, "stability_score"),
                      (uncertainties, "symbolic_uncertainty_score")):
        if any(not math.isfinite(x) for x in arr):
            raise ValueError(f"{name} contains non-finite values.")
    if any(not 0 <= x <= 1 for x in stabilities):
        raise ValueError("stability_score must be in [0,1].")
    if any(not 0 <= x <= 1 for x in uncertainties):
        raise ValueError("symbolic_uncertainty_score must be in [0,1].")

    align = [str(g["alignement"]) for g in glyphs if "alignement" in g]
    pol = [str(g["polarité"]) for g in glyphs if "polarité" in g]
    errors = [
        g.get("status") in {"error", "error_conversion"} or
        g.get("alignement") == "Error" or
        any(str(t).startswith("error") for t in g.get("tags", []))
        for g in glyphs
    ]

    def dist(values: list[str]) -> dict[str, float]:
        if not values:
            return {}
        unique, counts = np.unique(values, return_counts=True)
        total = len(values)
        return {str(k): float(v / total) for k, v in zip(unique, counts)}

    return ReflexiveMetrics(
        count=len(glyphs),
        mean_resonance=float(np.mean(resonances)) if resonances else None,
        mean_stability=float(np.mean(stabilities)) if stabilities else None,
        mean_uncertainty=float(np.mean(uncertainties)) if uncertainties else None,
        error_rate=empirical_error_rate(errors),
        alignment_distribution=dist(align),
        polarity_distribution=dist(pol),
    )
