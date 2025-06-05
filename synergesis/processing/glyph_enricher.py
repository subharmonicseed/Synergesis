"""Enrich glyph data with additional properties."""
from __future__ import annotations

import hashlib
from typing import Dict

from ..glyph_core import GlyphData


def enrich_glyph(glyph: GlyphData) -> GlyphData:
    """Add a simple semantic hash."""
    h = hashlib.sha256(str(glyph).encode("utf-8")).hexdigest()
    glyph["semantic_hash"] = h
    return glyph
