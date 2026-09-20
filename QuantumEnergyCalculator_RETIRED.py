"""Compatibility boundary for the retired quantum-energy implementation.

The former QuantumEnergyCalculator inferred kWh from a statevector. That is
not a physically valid mapping and is intentionally removed.
"""

from synergesis_canonical import (
    EnergyMeasurement,
    expectation,
    density_expectation,
    quantum_report,
)

class QuantumEnergyCalculator:
    def calculate(self, state):
        raise RuntimeError(
            "Retired: a statevector does not determine hardware energy. "
            "Use EnergyMeasurement from measured telemetry, and use "
            "expectation(state, Hamiltonian) for quantum-state energy."
        )
