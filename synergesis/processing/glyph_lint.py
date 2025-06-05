"""Validate glyph structures using Pydantic if available."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..glyph_core import GlyphData

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = None


class GlyphModelPydantic(BaseModel):  # type: ignore[misc]
    id: str

    class Config:
        extra = "allow"


def _basic_validate_glyph(glyph: GlyphData) -> Tuple[int, str]:
    if "id" not in glyph:
        return 1, "missing id"
    return 0, ""


def validate_glyphs_data(
    glyphs_data: List[GlyphData],
    strict_errors: bool = False,
    strict_warnings: bool = False,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """Validate glyphs using Pydantic if available."""
    errors = 0
    warnings = 0
    logs: List[Dict[str, Any]] = []
    for g in glyphs_data:
        if BaseModel:
            try:
                GlyphModelPydantic(**g)  # type: ignore[misc]
            except Exception as exc:
                errors += 1
                logs.append({"id": g.get("id"), "error": str(exc)})
        else:
            err, msg = _basic_validate_glyph(g)
            if err:
                errors += 1
                logs.append({"id": g.get("id"), "error": msg})
    return errors, warnings, logs
