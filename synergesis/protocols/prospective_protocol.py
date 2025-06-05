"""Definition of simulated outcomes."""
from __future__ import annotations

from typing import TypedDict


class SimulatedOutcome(TypedDict, total=False):
    local_entropy_delta: float
    local_resonance_delta: float
    confidence: float
