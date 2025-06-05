"""Placeholder for glyph translation utilities."""
from __future__ import annotations

from typing import Any, Dict

from ..glyph_core import GlyphData
from ..utils.common_helpers import _normalize, _get_map_value


def translate_glyph(glyph: GlyphData) -> Dict[str, Any]:
    """Return a basic translation of a glyph.

    This stub simply returns the input glyph under the key ``translated``.
    """
    return {"translated": glyph}

