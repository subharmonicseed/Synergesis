"""Synergesis core entry point with a verified quantitative/quantum layer.

This is intentionally a clean replacement boundary for the old prototype's
QuantumEnergyCalculator. Symbolic/LLM modules can call this service without
confusing state physics with hardware energy consumption.
"""
from __future__ import annotations

from typing import Any
import numpy as np
from fastapi import FastAPI, HTTPException

from synergesis_quantum_engine import (
    compare_states,
    entanglement_entropy_bits,
    hamiltonian_energy,
    quantum_state_report,
)

app = FastAPI(title="Synergesis Verified Quantum API", version="1.0.0")


def _state(payload: Any) -> np.ndarray:
    try:
        return np.asarray(payload, dtype=np.complex128)
    except Exception as exc:
        raise ValueError(f"Invalid quantum state: {exc}") from exc


@app.post("/quantum/analyze")
def analyze_quantum_state(data: dict) -> dict:
    """Analyze a statevector using only mathematically defined quantities."""
    try:
        psi = _state(data["state"])
        report = quantum_state_report(psi).to_dict()
        if "keep_qubits" in data:
            report["entanglement_entropy_bits"] = entanglement_entropy_bits(
                psi, data["keep_qubits"]
            )
        if "hamiltonian" in data:
            report["energy_expectation"] = hamiltonian_energy(
                psi, np.asarray(data["hamiltonian"], dtype=np.complex128)
            )
        return report
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/quantum/compare")
def compare_quantum_states(data: dict) -> dict:
    """Compare two pure states with fidelity and trace distance."""
    try:
        return compare_states(_state(data["state_a"]), _state(data["state_b"]))
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/quantum/definition")
def quantum_definition() -> dict:
    return {
        "state_norm": "||psi||_2 = 1",
        "measurement_probability": "p_i = |psi_i|^2",
        "shannon_entropy_bits": "H(p) = -sum_i p_i log2(p_i)",
        "von_neumann_entropy_bits": "S(rho) = -Tr(rho log2 rho)",
        "purity": "Tr(rho^2)",
        "fidelity_pure_states": "|<psi|phi>|^2",
        "trace_distance": "0.5 ||rho - sigma||_1",
        "state_energy": "<psi|H|psi>",
        "hardware_energy": "not inferable from a statevector alone",
    }
