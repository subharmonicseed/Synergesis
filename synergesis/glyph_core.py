# synergesis/glyph_core.py
"""
Core data models for the Synergesis project, based on the V8 architecture.
This module defines the structure of Glyphs, their properties, and their relationships.
"""
from typing import List, Dict, Any, Tuple, Union
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from datetime import datetime, timezone
import uuid

# --- Enumerations and Constants ---

class SimplePolarity(str, Enum):
    """Basic polarity values."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class StatusValue(str, Enum):
    """Status values for various system components."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"

# Using a Tuple for composite types as they are simple structures.
# A Pydantic model could be used if they become more complex.
CompositePolarity = Tuple[float, float]  # e.g., (positive_component, negative_component)
CompositeAlignment = Tuple[float, float, float] # e.g., (ideological, ethical, pragmatic)

# --- Core Data Models ---

class Glyph(BaseModel):
    """
    Represents a single, fundamental unit of meaning or data in the system.
    This is the primary node type in the knowledge graph.
    """
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    type: str = "semantic"  # e.g., 'semantic', 'regulatory', 'perceptual'

    # Polarity can be a simple enum value or a more complex composite tuple.
    polarity: Union[SimplePolarity, CompositePolarity] = SimplePolarity.NEUTRAL

    # Alignment can also be simple or composite. For now, we model it as a dict.
    alignment: Dict[str, float] = Field(default_factory=dict)

    weight: float = 1.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # A flexible field for any other data, e.g., from validation or analysis.
    metadata: Dict[str, Any] = Field(default_factory=dict)

class GlyphRelationship(BaseModel):
    """
    Represents a directed, weighted edge between two Glyphs in the knowledge graph.
    """
    source_id: str
    target_id: str
    type: str  # e.g., 'enhances', 'inhibits', 'associates', 'depends_on'
    weight: float = 1.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# --- Helper Functions ---

def is_composite_polarity(polarity: Any) -> bool:
    """Checks if a polarity value is composite."""
    return isinstance(polarity, tuple) and len(polarity) == 2

def is_composite_alignment(alignment: Any) -> bool:
    """Checks if an alignment value is composite."""
    # This is a placeholder; the definition of composite alignment may evolve.
    return isinstance(alignment, tuple) and len(alignment) > 1

# Note: The original architecture mentions 'GlyphData'. I have named the primary model 'Glyph'
# for clarity, as it represents the glyph entity itself. This can be easily aliased
# as 'GlyphData' if strict adherence to the doc's naming is required.
GlyphData = Glyph
