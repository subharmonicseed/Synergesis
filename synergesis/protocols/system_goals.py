"""Representation of system goals."""
from __future__ import annotations

from typing import TypedDict


class SystemGoal(TypedDict, total=False):
    resonance_target_min: int
    entropy_target_max: float
