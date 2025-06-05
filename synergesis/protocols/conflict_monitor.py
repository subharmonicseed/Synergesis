"""Protocol conflict monitoring."""
from __future__ import annotations

from typing import List

from ..glyph_core import GlyphData


def detect_conflicts(glyphs: List[GlyphData]) -> List[str]:
    """Return a list of detected protocol conflicts."""
    return []
