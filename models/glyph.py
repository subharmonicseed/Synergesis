from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

class Glyph(BaseModel):
    """Base Glyph model representing a structured unit of knowledge"""
    
    id: str = Field(
        default_factory=lambda: f"glyph_{uuid.uuid4()}",
        description="Unique identifier for the glyph",
        min_length=1,
        max_length=255
    )
    
    timestamp: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()),
        description="Unix timestamp of creation",
        ge=0
    )
    
    source: str = Field(
        ...,
        description="Origin of the glyph data",
        min_length=1
    )
    
    concept_type: str = Field(
        ...,
        description="Type of concept represented",
        min_length=1
    )
    
    status: str = Field(
        default="generated",
        description="Current status of the glyph",
        min_length=1
    )
    
    polarité: str = Field(
        default="neutral",
        description="Polarity indicator",
        min_length=1
    )
    
    alignement: str = Field(
        default="center",
        description="Alignment type",
        min_length=1
    )
    
    content: str = Field(
        ...,
        description="Main content of the glyph",
        min_length=1,
        max_length=10000
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @property
    def parent_doc_id(self) -> str:
        """Get parent document ID from metadata."""
        return self.metadata.get("parent_doc_id", "")

    @parent_doc_id.setter
    def parent_doc_id(self, value: str) -> None:
        """Set parent document ID in metadata."""
        self.metadata["parent_doc_id"] = value

    @validator('polarité')
    def validate_polarite(cls, v):
        """Ensure polarité is normalized"""
        return v.lower()

    @validator('alignement')
    def validate_alignement(cls, v):
        """Ensure alignement is normalized"""
        return v.lower()

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda dt: int(dt.timestamp())
        }
