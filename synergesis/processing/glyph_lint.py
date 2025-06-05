from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    from pydantic import BaseModel, Field, ValidationError, validator
except Exception:  # pragma: no cover - optional dependency
    BaseModel = None  # type: ignore
    Field = lambda *a, **k: None  # type: ignore
    ValidationError = Exception  # type: ignore
    def validator(*args: Any, **kwargs: Any):
        def deco(func: Any) -> Any:
            return func
        return deco

try:
    from synergesis.glyph_core import GlyphData, CONCEPT_TYPES_TECHNICAL, STATUS_VALUES
except Exception:  # pragma: no cover - fallback definitions
    GlyphData = Dict[str, Any]
    CONCEPT_TYPES_TECHNICAL = {
        "POTENTIAL_ACTION",
        "MEMORY_TRACE",
        "PROBLEM",
        "SOLUTION",
        "TEST",
    }
    STATUS_VALUES = {"from_llm", "received", "translated"}

KNOWN_FIELDS = {"id", "concept_type", "timestamp", "status", "relationships"}


def _basic_validate_glyph(glyph: GlyphData, strict_warnings: bool) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(glyph, dict):
        errors.append("glyph is not a dict")
        return errors, warnings

    gid = glyph.get("id")
    if not isinstance(gid, str) or not gid:
        errors.append("id missing or invalid")

    concept = glyph.get("concept_type")
    if concept is None:
        errors.append("concept_type missing")
    elif CONCEPT_TYPES_TECHNICAL and concept not in CONCEPT_TYPES_TECHNICAL:
        errors.append(f"invalid concept_type '{concept}'")

    ts = glyph.get("timestamp")
    if not isinstance(ts, (int, float)) or float(ts) <= 0:
        errors.append("timestamp must be positive number")

    status = glyph.get("status")
    if status is None:
        errors.append("status missing")
    elif STATUS_VALUES and status not in STATUS_VALUES:
        errors.append(f"invalid status '{status}'")

    if "relationships" in glyph:
        rels = glyph["relationships"]
        if not isinstance(rels, list):
            errors.append("relationships must be a list")
        else:
            for r in rels:
                if not isinstance(r, dict) or "type" not in r:
                    errors.append("invalid relationship item")
                    break

    if strict_warnings:
        extras = set(glyph.keys()) - KNOWN_FIELDS
        for extra in extras:
            warnings.append(f"unknown field '{extra}'")
    return errors, warnings


def _pydantic_validate_glyph(glyph: GlyphData, strict_warnings: bool) -> Tuple[List[str], List[str]]:
    if BaseModel is None:
        return _basic_validate_glyph(glyph, strict_warnings)

    class GlyphModel(BaseModel):
        id: str = Field(..., min_length=1)
        concept_type: str
        timestamp: float
        status: str
        relationships: Optional[List[Dict[str, Any]]] = None

        @validator("concept_type")
        def _val_concept_type(cls, v: str) -> str:
            if CONCEPT_TYPES_TECHNICAL and v not in CONCEPT_TYPES_TECHNICAL:
                raise ValueError("invalid concept_type")
            return v

        @validator("status")
        def _val_status(cls, v: str) -> str:
            if STATUS_VALUES and v not in STATUS_VALUES:
                raise ValueError("invalid status")
            return v

        @validator("timestamp")
        def _val_timestamp(cls, v: float) -> float:
            if v <= 0:
                raise ValueError("timestamp must be > 0")
            return v

        @validator("relationships", each_item=True)
        def _val_relationships(cls, v: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(v, dict) or "type" not in v:
                raise ValueError("invalid relationship item")
            return v

        class Config:
            extra = "ignore"

    errors: List[str] = []
    warnings: List[str] = []
    try:
        GlyphModel(**glyph)
    except ValidationError as exc:
        for e in exc.errors():
            errors.append(e.get("msg", str(e)))

    if strict_warnings:
        extras = set(glyph.keys()) - GlyphModel.__fields__.keys()
        for extra in extras:
            warnings.append(f"unknown field '{extra}'")
    return errors, warnings


def validate_glyphs_data(
    glyphs_data: List[GlyphData],
    *,
    strict_errors: bool = False,
    strict_warnings: bool = False,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """Validate a list of glyph dictionaries.

    Parameters
    ----------
    glyphs_data:
        List of glyph dictionaries to validate.
    strict_errors:
        Use strict Pydantic validation if available.
    strict_warnings:
        Log warnings for unknown fields.

    Returns
    -------
    tuple of (error_count, warning_count, logs)
    """

    error_count = 0
    warning_count = 0
    logs: List[Dict[str, Any]] = []

    validator_fn = _pydantic_validate_glyph if strict_errors else _basic_validate_glyph

    for glyph in glyphs_data:
        errs, warns = validator_fn(glyph, strict_warnings)
        error_count += len(errs)
        warning_count += len(warns)
        gid = glyph.get("id")
        for msg in errs:
            logs.append({"id": gid, "level": "error", "msg": msg})
        for msg in warns:
            logs.append({"id": gid, "level": "warning", "msg": msg})
    return error_count, warning_count, logs


__all__ = ["validate_glyphs_data"]
