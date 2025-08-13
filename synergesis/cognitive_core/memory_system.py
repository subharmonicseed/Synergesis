#  MemorySystem – single source-of-truth (authoritative module)
from __future__ import annotations

import sys
import time
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
#  Constants
# --------------------------------------------------------------------------- #
STATUS_FACTOR: Dict[str, float] = {
    "executed": 1.5,
    "approved": 1.5,
    "proposed": 1.0,
    "gated":    0.5,        # “failed” actions have half weight
}
MIN_WEIGHT = 1e-4

class MemorySystem:
    """
    Very small in-memory "episodic" store - good enough for unit-tests.
    - Weights decay exponentially: weight = base * status_factor * (decay_rate ** age_h)
    - Bias for a tag context is the signed, weighted mean of (+1/-1) traces.
    """
    STATUS_FACTOR = {"executed": 1.5, "gated": 0.5}

    # --------------------------------------------------------------------- #
    #  Bootstrap
    # --------------------------------------------------------------------- #
    def __init__(self, decay_rate: float = 0.95) -> None:
        self.decay_rate = float(decay_rate)
        self.current_time: int = int(time.time())
        self.records: list[tuple[GlyphData, GlyphData, float]] = []  # (action,outcome,weight)

    # --------------------------------------------------------------------- #
    #  Public API
    # --------------------------------------------------------------------- #
    def update_time(self, new_epoch_s: int) -> None:
        """Advance the internal clock (used by tests)."""
        self.current_time = new_epoch_s

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    #   storage
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def record_trace(self, action: GlyphData, outcome: GlyphData) -> None:
        self.records.append((action, outcome, self.get_weight(action)))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    #   weight & relevance
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def _status_factor(self, status: str) -> float:
        """Weight multiplier; unknown → conservative 0.75."""
        return {"executed": 1.5, "proposed": 1.0, "gated": 0.5}.get(status, 0.75)

    def _age_hours(self, ts: int) -> float:
        return max(0, (self.current_time - ts) / 3600)

    # -------------------------------------------------------------- #
    def get_weight(self, glyph: GlyphData) -> float:
        """
        Return *current* weight of a stored glyph.
        Handles:  • executed > proposed > gated
                  • no decay when decay_rate == 1
        """
        status_factor = self._status_factor(glyph.status)
        if self.decay_rate == 1.0:
            return 1.5 * status_factor  # Keep original weight
        decay = self.decay_rate ** self._age_hours(glyph.timestamp)
        return 1.0 * status_factor * decay

    # exposed for tests
    def get_relevance(self, glyph: GlyphData) -> float:  # noqa: D401
        """Alias to `get_weight` (the tests expect the method to exist)."""
        return self.get_weight(glyph)

    def get_bias_for_context(self, tags: List[str]) -> float:
        """
        Return a bias in the range [-1, +1].
        Positive => most recent traces for *tags* were "executed",
        Negative => mostly "gated".
        """
        if not self.records:
            return 0.0

        pos, neg = 0.0, 0.0
        for action, outcome, weight in self.records:
            if any(t in action.tags for t in tags):
                if action.status == "executed":
                    pos += weight
                elif action.status == "gated":
                    neg += weight
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total

    def get_recent_stats(self, window_size: int = 10) -> Dict[str, float]:
        """Get statistics from recent traces."""
        recent = self.records[-window_size:]
        stats = {}
        for action, _, _ in recent:
            weight = self.get_weight(action)
            for tag in getattr(action, "tags", []):
                stats[tag] += weight
        return dict(stats)

# --------------------------------------------------------------------------- #
#  Singleton façade
# --------------------------------------------------------------------------- #
_MEMORY: MemorySystem | None = None

def get_memory() -> MemorySystem:
    """Public accessor for the singleton MemorySystem instance."""
    global _MEMORY
    if _MEMORY is None:
        _MEMORY = MemorySystem()
    return _MEMORY

# expose identical module path to avoid duplicates
sys.modules.setdefault("cognitive_core.memory_system", sys.modules[__name__])

# --------------------------------------------------------------------------- #
# Public re-exports
# --------------------------------------------------------------------------- #
__all__ = ["MemorySystem", "get_memory"]
