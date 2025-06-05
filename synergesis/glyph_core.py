"""Core glyph data structures and constants for Synergesis."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

try:
    from typing import NotRequired  # type: ignore
except ImportError:  # pragma: no cover - py<3.11
    from typing_extensions import NotRequired  # type: ignore


class CompositePolarity(TypedDict, total=False):
    positive: NotRequired[float]
    negative: NotRequired[float]
    neutral: NotRequired[float]


class CompositeAlignment(TypedDict, total=False):
    Celestial: NotRequired[float]
    Void: NotRequired[float]
    Chthonic: NotRequired[float]


class GlyphRelationship(TypedDict, total=False):
    type: str
    target: Optional[str]
    source_template: NotRequired[str]
    properties: NotRequired[Dict[str, Any]]


class GlyphData(TypedDict, total=False):
    id: str
    timestamp: float
    source: str
    concept_type: str
    action_type: NotRequired[str]
    status: str
    priority: NotRequired[int]
    confidence: NotRequired[float]
    polarité: NotRequired[str | CompositePolarity]
    alignement: NotRequired[str | CompositeAlignment]
    poids: NotRequired[int]
    fréquence: NotRequired[int]
    tags: NotRequired[List[str]]
    natural_prompt: NotRequired[str]
    details_structured_json: NotRequired[Dict[str, Any]]
    relationships: NotRequired[List[GlyphRelationship]]


SIMPLE_POLARITIES = ["+", "-", "0", "±"]
SIMPLE_ALIGNMENTS = ["Celestial", "Void", "Chthonic"]
RELATIONSHIP_TYPES = [
    "RELATED_TO_CONCEPT",
    "ADDRESSES_PROBLEM",
    "CAUSES",
    "RESULT_OF",
]
STATUS_VALUES = [
    "PROPOSED",
    "GENERATED",
    "SIMULATED",
    "EXECUTED",
    "FAILED",
]
CONCEPT_TYPES_TECHNICAL = ["POTENTIAL_ACTION", "SIMULATED_OUTCOME", "MEMORY_TRACE"]


def is_composite_polarity(value: Any) -> bool:
    """Return True if value looks like a CompositePolarity."""
    return isinstance(value, dict) and not set(value).difference({"positive", "negative", "neutral"})


def is_composite_alignment(value: Any) -> bool:
    """Return True if value looks like a CompositeAlignment."""
    return isinstance(value, dict) and not set(value).difference({"Celestial", "Void", "Chthonic"})

