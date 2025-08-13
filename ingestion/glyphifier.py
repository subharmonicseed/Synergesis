"""
Glyphifier - Converts text inputs into structured Glyph objects for Neo4j storage

This module handles the conversion of raw text into structured Glyph objects that can be
stored in Neo4j. It includes text processing, validation, and transformation logic.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class Glyph(BaseModel):
    """Base Glyph model representing a structured unit of knowledge"""
    id: str = Field(default_factory=lambda: f"glyph_{uuid.uuid4()}", description="Unique identifier for the glyph")
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()), description="Unix timestamp of creation")
    source: str = Field(..., description="Origin of the glyph data")
    concept_type: str = Field(..., description="Type of concept represented")
    status: str = Field(default="generated", description="Current status of the glyph")
    polarité: str = Field(default="neutral", description="Polarity indicator")
    alignement: str = Field(default="center", description="Alignment type")
    content: str = Field(..., description="Main content of the glyph")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

def glyphify_sleep_phase(
    raw_ctx: str,
    parent_doc_id: str,
    source_chunk_index: int,
    llm_name: str,
    llm: Any,
) -> Dict[str, Any]:
    """
    Convert a text chunk into a structured glyph using LLM.
    
    Args:
        raw_ctx: The raw text context to process
        parent_doc_id: ID of the parent document
        source_chunk_index: Index of this chunk in the source
        llm_name: Name of the LLM being used
        llm: The LLM instance
        
    Returns:
        Dict containing:
            - glyphs: List of generated glyphs
            - raw_ctx: Original context
            - metadata: Processing metadata
    """
    try:
        # Generate glyphs using LLM
        response = llm.generate_glyphe(raw_ctx)
        glyphs_from_llm = response.get("glyphes", [])
        
        # Process each glyph
        validated = []
        for raw in glyphs_from_llm:
            # Normalize field names
            key_map = {"polaritǸ": "polarité"}
            normalized = {key_map.get(k, k): v for k, v in raw.items()}
            
            # Add default values and content
            normalized.setdefault("content", raw_ctx[:1000])
            normalized.setdefault("metadata", {
                "parent_doc_id": parent_doc_id,
                "chunk_index": source_chunk_index,
                "llm_name": llm_name,
            })
            
            # Strict type validation
            if not isinstance(normalized.get("id"), str):
                print(f"Skipping glyph: invalid id type")
                continue
            
            if not isinstance(normalized.get("content"), str):
                print(f"Skipping glyph: invalid content type")
                continue
            
            if not isinstance(normalized.get("status"), str):
                print(f"Skipping glyph: invalid status type")
                continue
            
            if len(normalized["id"]) > 255:
                print(f"Skipping glyph: id too long")
                continue
            
            if len(normalized["content"]) > 10000:
                print(f"Skipping glyph: content too long")
                continue
            
            try:
                # Validate using Pydantic
                glyph = Glyph(**normalized)
                validated.append(glyph.dict())
            except Exception as e:
                print(f"Skipping invalid glyph: {e}")
                
        return {
            "glyphs": validated,
            "raw_ctx": raw_ctx,
            "metadata": {
                "source_chunk_index": source_chunk_index,
                "llm_name": llm_name,
                "timestamp": int(datetime.now().timestamp())
            }
        }
        
    except Exception as e:
        print(f"Error in glyphify_sleep_phase: {e}")
        return {"glyphs": [], "raw_ctx": raw_ctx, "metadata": {"error": str(e)}}
