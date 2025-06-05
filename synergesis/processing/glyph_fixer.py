"""Basic glyph correction helpers."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List

from ..glyph_core import GlyphData


class CorrectionLevel(Enum):
    SAFE = auto()
    MODERATE = auto()
    AGGRESSIVE = auto()


@dataclass
class CorrectionReport:
    fixed_count: int
    notes: List[str]


class GlyphFixer:
    """Apply simple corrections to glyph data."""

    def __init__(self, level: CorrectionLevel = CorrectionLevel.SAFE) -> None:
        self.level = level

    def fix_single_glyph(self, glyph: GlyphData) -> GlyphData:
        if "status" not in glyph:
            glyph["status"] = "UNKNOWN"
        return glyph

    def fix_glyphs_batch(self, glyphs: List[GlyphData]) -> CorrectionReport:
        notes: List[str] = []
        for g in glyphs:
            before = dict(g)
            self.fix_single_glyph(g)
            if g != before:
                notes.append(f"fixed {g.get('id')}")
        return CorrectionReport(fixed_count=len(notes), notes=notes)
