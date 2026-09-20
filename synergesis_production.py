"""Synergesis production symbolic layer: no placeholders, dummies or silent fallbacks."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence
import math
import time
import uuid
from synergesis_canonical import (
    weighted_mean, frequency_weighted_average, decayed_weight_sum,
    polarity_composition, weighted_symbolic_dissimilarity,
    normalized_numeric_dissimilarity, tag_jaccard_dissimilarity,
    empirical_error_rate, reflexive_metrics,
)

ALIGNMENT_VALUES = {"Celestial": 1.0, "Harmonic": 0.5, "Void": 0.0, "Chthonic": -0.5, "Error": -1.0}
POLARITY_VALUES = {"+": 1.0, "0": 0.0, "-": -1.0}


def _require(g: Mapping[str, Any], key: str) -> Any:
    if key not in g or g[key] is None:
        raise ValueError(f"Missing required glyph field: {key}")
    return g[key]


def fuse_alignment(glyphs: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    values, weights = [], []
    for g in glyphs:
        a = _require(g, "alignement")
        if a not in ALIGNMENT_VALUES:
            raise ValueError(f"Unknown alignment: {a}")
        values.append(ALIGNMENT_VALUES[a]); weights.append(float(_require(g, "poids")))
    if any(w < 0 or not math.isfinite(w) for w in weights) or sum(weights) <= 0:
        raise ValueError("Alignment weights must be finite, non-negative, with positive total.")
    score = weighted_mean(values, weights)
    # Preserve the actual composition; score is an explicit derived coordinate.
    composition: dict[str, float] = {}
    total = sum(weights)
    for g, w in zip(glyphs, weights):
        a = g["alignement"]
        composition[a] = composition.get(a, 0.0) + w / total
    return {"score": score, "composition": composition}


def fuse_glyphs_production(glyphs: Sequence[Mapping[str, Any]], decay: float = 0.9) -> dict[str, Any]:
    if len(glyphs) < 2:
        raise ValueError("Fusion requires at least two glyphs.")
    ids = [str(_require(g, "id")) for g in glyphs]
    if len(set(ids)) != len(ids):
        raise ValueError("Parent glyph IDs must be unique.")
    frequencies = frequency_weighted_average(glyphs)
    weights = decayed_weight_sum(glyphs, decay)
    polarity = polarity_composition(glyphs)
    alignment = fuse_alignment(glyphs)
    tags = sorted({str(t) for g in glyphs for t in g.get("tags", [])})
    result = {
        "id": f"fused-{int(time.time_ns())}-{uuid.uuid4().hex[:8]}",
        "timestamp": time.time(),
        "sourceIds": sorted(ids),
        "polarité": polarity,
        "alignement": alignment,
        "fréquence": frequencies,
        "poids": weights,
        "tags": sorted(set(tags + ["fused"])),
        "status": "fused",
        "details": {"parent_count": len(glyphs), "decay": decay},
    }
    if all("symbolic_uncertainty_score" in g for g in glyphs):
        u = weighted_mean(
            [float(g["symbolic_uncertainty_score"]) for g in glyphs],
            [float(_require(g, "poids")) for g in glyphs],
        )
        if not 0 <= u <= 1: raise ValueError("symbolic_uncertainty_score must be in [0,1].")
        result["symbolic_uncertainty_score"] = u
    return result


@dataclass(frozen=True)
class TopologyEdge:
    source: str
    target: str
    dissimilarity: float
    similarity: float

    def to_dict(self): return asdict(self)


def glyph_dissimilarity(a: Mapping[str, Any], b: Mapping[str, Any],
                        ranges: Mapping[str, tuple[float, float]]) -> float:
    components: list[tuple[float, float]] = []
    if "alignement" in a and "alignement" in b:
        av, bv = a["alignement"], b["alignement"]
        if av not in ALIGNMENT_VALUES or bv not in ALIGNMENT_VALUES:
            raise ValueError("Unknown alignment in topology input.")
        components.append((0.25, normalized_numeric_dissimilarity(
            ALIGNMENT_VALUES[av], ALIGNMENT_VALUES[bv], -1.0, 1.0)))
    if "polarité" in a and "polarité" in b:
        av, bv = a["polarité"], b["polarité"]
        if av not in POLARITY_VALUES or bv not in POLARITY_VALUES:
            raise ValueError("Unknown polarity in topology input.")
        components.append((0.25, normalized_numeric_dissimilarity(
            POLARITY_VALUES[av], POLARITY_VALUES[bv], -1.0, 1.0)))
    if "fréquence" in a and "fréquence" in b:
        lo, hi = ranges["fréquence"]
        components.append((0.15, normalized_numeric_dissimilarity(float(a["fréquence"]), float(b["fréquence"]), lo, hi)))
    if "poids" in a and "poids" in b:
        lo, hi = ranges["poids"]
        components.append((0.10, normalized_numeric_dissimilarity(float(a["poids"]), float(b["poids"]), lo, hi)))
    if "tags" in a and "tags" in b:
        components.append((0.10, tag_jaccard_dissimilarity(a["tags"], b["tags"])))
    if not components:
        raise ValueError("No comparable features exist for topology.")
    return weighted_symbolic_dissimilarity(components)


def build_topology(glyphs: Sequence[Mapping[str, Any]], ranges: Mapping[str, tuple[float, float]],
                   max_dissimilarity: float) -> list[TopologyEdge]:
    if not 0 <= max_dissimilarity <= 1: raise ValueError("max_dissimilarity must be in [0,1].")
    edges = []
    for i, a in enumerate(glyphs):
        for b in glyphs[i+1:]:
            da = glyph_dissimilarity(a, b, ranges)
            if da <= max_dissimilarity:
                edges.append(TopologyEdge(str(_require(a,"id")), str(_require(b,"id")), da, 1-da))
    return edges


@dataclass(frozen=True)
class CortexDecision:
    state: str
    reason: str
    metrics: dict[str, Any]
    def to_dict(self): return asdict(self)


def evaluate_cortex(glyphs: Sequence[Mapping[str, Any]], *, stability_min: float,
                    uncertainty_max: float, error_rate_max: float) -> CortexDecision:
    if not 0 <= stability_min <= 1 or not 0 <= uncertainty_max <= 1 or not 0 <= error_rate_max <= 1:
        raise ValueError("Cortex thresholds must be in [0,1].")
    metrics = reflexive_metrics(glyphs).to_dict()
    if metrics["error_rate"] is not None and metrics["error_rate"] > error_rate_max:
        return CortexDecision("error", "empirical_error_rate_above_threshold", metrics)
    if metrics["mean_stability"] is not None and metrics["mean_stability"] < stability_min:
        return CortexDecision("unstable", "mean_stability_below_threshold", metrics)
    if metrics["mean_uncertainty"] is not None and metrics["mean_uncertainty"] > uncertainty_max:
        return CortexDecision("uncertain", "mean_uncertainty_above_threshold", metrics)
    return CortexDecision("stable", "all_available_metrics_within_thresholds", metrics)
