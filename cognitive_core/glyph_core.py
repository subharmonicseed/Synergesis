"""Core data models for cognitive operations."""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

class GlyphData(BaseModel):
    """Data model for a glyph node."""
    
    id: str = Field(..., description="Unique identifier for the glyph")
    timestamp: int = Field(..., description="Unix timestamp of creation")
    source: str = Field(..., description="Origin of the glyph data")
    concept_type: str = Field(..., description="Type of concept represented")
    status: str = Field(..., description="Current status of the glyph")
    polarité: str = Field(default="neutral", description="Polarity indicator")
    alignement: str = Field(default="center", description="Alignment type")
    content: str = Field(default="", description="Main content of the glyph")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    target_action_id: str = Field(default="", description="ID of the target action")
    result_structural: Dict[str, float] = Field(default_factory=dict, description="Structural result metrics")
    confidence: float = Field(default=0.0, description="Simulation confidence")
    
    @property
    def parent_doc_id(self) -> str:
        """Get parent document ID from metadata."""
        return self.metadata.get("parent_doc_id", "")

    @parent_doc_id.setter
    def parent_doc_id(self, value: str) -> None:
        """Set parent document ID in metadata."""
        self.metadata["parent_doc_id"] = value
    
    class Config:
        extra = "allow"  # Allow additional fields from Neo4j

    @classmethod
    def from_neo4j(cls, data: Dict[str, Any]) -> "GlyphData":
        """Create GlyphData from Neo4j node data."""
        return cls(**data)

    def to_neo4j(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return self.dict()
