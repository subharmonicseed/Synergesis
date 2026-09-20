"""Canonical Synergesis production API boundary.

Only verified quantitative/quantum and explicit symbolic design metrics are
exposed. Missing measurements are rejected rather than fabricated.
"""
from __future__ import annotations
from typing import Any
import numpy as np
from fastapi import FastAPI, HTTPException
from synergesis_quantum_engine import compare_states, entanglement_entropy_bits, hamiltonian_energy, quantum_state_report
from synergesis_production import fuse_glyphs_production, build_topology, evaluate_cortex

app = FastAPI(title="Synergesis Production API", version="2.0.0")


def _state(value: Any) -> np.ndarray:
    try:
        return np.asarray(value, dtype=np.complex128)
    except Exception as exc:
        raise ValueError(f"Invalid quantum state: {exc}") from exc


@app.post("/quantum/analyze")
def analyze_quantum(data: dict) -> dict:
    try:
        report = quantum_state_report(_state(data["state"])).to_dict()
        if "keep_qubits" in data:
            report["entanglement_entropy_bits"] = entanglement_entropy_bits(_state(data["state"]), data["keep_qubits"])
        if "hamiltonian" in data:
            report["energy_expectation"] = hamiltonian_energy(_state(data["state"]), np.asarray(data["hamiltonian"], dtype=np.complex128))
        return report
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/quantum/compare")
def compare_quantum(data: dict) -> dict:
    try:
        return compare_states(_state(data["state_a"]), _state(data["state_b"]))
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/glyph/fuse")
def fuse_glyphs(data: dict) -> dict:
    try:
        return fuse_glyphs_production(data["glyphs"], decay=data.get("decay", 0.9))
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/topology/build")
def topology(data: dict) -> dict:
    try:
        edges = build_topology(data["glyphs"], data["ranges"], data["max_dissimilarity"])
        return {"edges": [e.to_dict() for e in edges]}
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/cortex/evaluate")
def cortex(data: dict) -> dict:
    try:
        return evaluate_cortex(
            data["glyphs"],
            stability_min=data["stability_min"],
            uncertainty_max=data["uncertainty_max"],
            error_rate_max=data["error_rate_max"],
        ).to_dict()
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/definition")
def definition() -> dict:
    return {
        "quantum": {
            "probability": "p_i = |psi_i|^2",
            "shannon_entropy_bits": "H(p) = -sum p_i log2(p_i)",
            "von_neumann_entropy_bits": "S(rho) = -Tr(rho log2 rho)",
            "state_energy": "<psi|H|psi>",
            "hardware_energy": "requires measurement/telemetry; not inferred from statevector",
        },
        "symbolic": {
            "fusion": "explicit weighted/decayed aggregation from supplied glyph data",
            "topology": "bounded weighted dissimilarity; not claimed to be a mathematical metric",
            "cortex_error_rate": "empirical fraction of observed glyphs classified as errors",
        },
    }
