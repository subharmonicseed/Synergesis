"""Common helper utilities for Synergesis."""
from __future__ import annotations


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value into the 0-1 range given bounds."""
    if max_val == min_val:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def _get_map_value(value: str, mapping_dict: dict[str, str], default_key_index: str) -> str:
    """Return mapped value or mapping for a default key."""
    return mapping_dict.get(value, mapping_dict.get(default_key_index))
