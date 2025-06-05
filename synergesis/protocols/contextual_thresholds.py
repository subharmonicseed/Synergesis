"""Dynamic threshold calculations."""
from __future__ import annotations

from typing import Any, Dict


def compute_thresholds(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dictionary of dynamic threshold values."""
    return {"entropy_min": 0.35, "resonance_max": 50}
