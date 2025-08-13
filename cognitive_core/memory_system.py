"""Memory system for storing and retrieving action traces."""

"""Memory system for storing and retrieving action traces."""

from importlib import import_module

# NOTE: this file only re-exports the authoritative implementation that
# lives in *synergesis/cognitive_core/memory_system.py*.  Having a single
# class avoids the "two different MemorySystem objects" problem.
#
_real_mod = import_module("synergesis.cognitive_core.memory_system")
MemorySystem = _real_mod.MemorySystem  # noqa: N816

# anything that does "from cognitive_core.memory_system import MemorySystem"
# now receives the exact same class object as the rest of the code base.

__all__ = ["MemorySystem"]

from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime
from cognitive_core.glyph_core import GlyphData
import math
import time
import uuid

class MemorySystem:
    """
    Memory system with temporal decay.
    Records action traces with timestamps and computes weighted scores.
    """

    def __init__(self, decay_rate: float = 0.95) -> None:
        """
        Initialize memory system.
        
        Args:
            decay_rate: Rate at which memory fades (0.95 means 5% decay per time unit)
        """
        self.decay_rate = decay_rate
        self.current_time = int(time.time())
        self.records: List[Tuple[GlyphData, GlyphData, float]] = []  # (action, outcome, timestamp)
        
        # Status factors for bias calculation
        self.STATUS_FACTOR: Dict[str, float] = {
            "executed": 1.5,
            "gated": 0.5,
            "_default": 0.75
        }

    # --------------------------------------------------------------------- #
    # Bias helper – used by IntentionGenerator & MetabolicProtocol
    # --------------------------------------------------------------------- #
    def get_bias_for_context(self, tags: list[str]) -> float:
        """
        Return a bias in **[-1; +1]** for the supplied tags.
        Positive → memory of successful actions dominates,
        Negative → memory of gated / failed actions dominates.
        """
        pos, neg = 0.0, 0.0
        for action, _outcome, _id in self.records:
            if not tags or any(t in getattr(action, "tags", []) for t in tags):
                factor = self.STATUS_FACTOR.get(action.status, -1.0)
                if factor > 1:
                    pos += factor
                else:
                    neg += abs(factor)

        total = pos + neg
        if total == 0:
            return 0.0
        return round((pos - neg) / total, 2)

    def update_time(self, new_time: float) -> None:
        """Update the current time reference."""
        self.current_time = new_time

    # ------------------------------------------------------------------ #
    # helpers expected by tests                                          #
    # ------------------------------------------------------------------ #
    def _age_hours(self, ts: int) -> int:
        """Integral age (in hours) between stored *ts* and current_time."""
        return max(0, (self.current_time - ts) // 3600)

    def _status_factor(self, status: str) -> float:
        """Weight multiplier; unknown → conservative 0.75."""
        # executed = 1.5 (strong positive)
        # proposed = 0.0 (neutral)
        # gated = 0.5 (weak negative)
        # unknown = 0.75 (conservative default)
        return {"executed": 1.5, "proposed": 0.0, "gated": 0.5}.get(status, 0.75)

    def get_weight(self, glyph: GlyphData) -> float:
        """
        Current weight = base (1.0) × status_factor × decay**age
        """
        status_factor = self._status_factor(glyph.status)
        decay = self.decay_rate ** self._age_hours(glyph.timestamp)
        return 1.0 * status_factor * decay

    # ------------------------------------------------------------------ #
    # thin wrappers kept for legacy tests                                 #
    # ------------------------------------------------------------------ #
    def get_relevance(self, glyph: GlyphData) -> float:     # noqa: D401
        """Alias kept for the public test-suite."""
        return self.get_weight(glyph)

    def get_weight(self, glyph: GlyphData) -> float:
        """
        Return *current* weight of a stored glyph.
        Handles:  • executed > proposed > gated
                  • no decay when decay_rate == 1
        """
        status_factor = self._status_factor(glyph.status)
        if self.decay_rate == 1.0:
            return 1.0 * status_factor  # Keep original weight
        decay = self.decay_rate ** self._age_hours(glyph.timestamp)
        return 1.0 * status_factor * decay

    def record_trace(self, action: GlyphData, outcome: GlyphData) -> str:
        """
        Record an action trace with its outcome.
        Returns the trace ID.
        """
        trace_id = str(uuid.uuid4())
        self.records.append((action, outcome, self.current_time))
        return trace_id

    def get_bias_for_target(self, target_cluster: str) -> float:
        """Return aggregated bias score for a given cluster target."""
        return self.get_bias_for_context([target_cluster])

    def get_bias_for_tags(self, tags: list[str]) -> float:
        """Return aggregated bias score for a list of tags."""
        return self.get_bias_for_context(tags)

    def get_bias_for_action(self, action: GlyphData) -> float:
        """Return bias score for a specific action."""
        return self.get_bias_for_context(getattr(action, "tags", []))

    def get_relevance(self, glyph: GlyphData) -> float:
        """Calculate relevance as weight plus recency bonus."""
        weight = self.get_weight(glyph)
        age_h = self._age_hours(glyph.timestamp)
        recency_bonus = 1.0 / (1.0 + age_h)
        return weight + recency_bonus

    def get_recent_stats(self, window_size: int = 10) -> Dict[str, float]:
        """Get statistics from recent traces, considering decay."""
        recent = self.records[-window_size:]
        if not recent:
            return {
                "avg_confidence": 0.0,
                "avg_weight": 0.0,
                "execution_rate": 0.0,
                "avg_relevance": 0.0
            }

        # Calculate decayed weights and relevances
        weights = []
        relevances = []
        exec_count = 0
        confidence_sum = 0.0
        score = 0

        for act, out, w, t in recent:
            decay_factor = self.decay_rate ** ((self.current_time - t) / 3600)
            weights.append(w * decay_factor)
            relevances.append(self.get_relevance(act))
            confidence_sum += act.confidence
            # Calculate bias score: executed = +1, gated = -1, proposed = 0
            if out.status == "executed":
                score += 1  # Success increases score
            elif out.status == "gated":
                score -= 1  # Failure decreases score
            # proposed → neutral (0)

        return {
            "avg_confidence": confidence_sum / len(recent),
            "avg_weight": sum(weights) / len(recent),
            "execution_rate": score / len(recent) if len(recent) > 0 else 0,
            "avg_relevance": sum(relevances) / len(recent)
        }
