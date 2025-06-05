"""Record and manage memory traces."""
from __future__ import annotations

from typing import List

from ..glyph_core import GlyphData


class MemorySystem:
    """Store and weight past actions."""

    def __init__(self) -> None:
        self.traces: List[GlyphData] = []

    def record_trace(self, action_glyph: GlyphData, outcome_glyph: GlyphData) -> None:
        self.traces.append({"action": action_glyph, "outcome": outcome_glyph})

    def get_bias_for_context(self, context_tags: List[str]) -> float:
        return 0.0
