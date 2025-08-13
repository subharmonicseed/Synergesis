### **Code Implementation: Concept Model Enhancement**

**Date:** 7/17/2025
**Author:** Lead Developer, Synglyph Project

---

### **1. Executive Summary**

This document provides the complete Python code implementing the enhancements to the `Concept` data model and associated processing logic within the `nous_service`. The changes directly address the findings from the gap analysis (GIA-20250717-CME-01).

*   **Model Update:** The `Concept` Pydantic model in `schemas.py` has been modified to define `weight` and `resonance` as `Optional[float]`, ensuring backward compatibility and aligning with system design principles.
*   **Logic Implementation:** The `SemanticProcessor` class in `semantic_processor.py` is now equipped with baseline analytical functions to calculate `weight` and `resonance` from input text, transforming it from a placeholder into a functional analysis component.
*   **Integration Readiness:** The code is documented, follows Python best practices, and is ready for integration into the main branch and subsequent validation by the `Selene` test suite as part of Sprint 2.

---

### **2. Updated `nous_service` Source Code**

The following files within the `nous_service` have been modified.

#### **2.1. Pydantic Model Definition (`schemas.py`)**

**File Path:** `nous_service/app/api/v1/schemas.py`

**Analysis:** The `Concept` model is updated to make the `weight` and `resonance` fields optional. This is a critical change identified in the gap analysis to allow for graceful degradation and prevent schema validation errors if these values cannot be computed. The `typing.Optional` type hint is used, and the Pydantic `Field` default is set to `None`.

```python
# nous_service/app/api/v1/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid

class Relationship(BaseModel):
    """Defines a directed connection between two Concepts."""
    target_concept_id: uuid.UUID = Field(..., description="The ID of the concept this relationship points to.")
    type: str = Field(..., example="is_a", description="The nature of the relationship (e.g., 'is_a', 'part_of', 'causes').")
    weight: float = Field(default=1.0, description="The strength or confidence of the relationship.")

class Concept(BaseModel):
    """The core data model representing a semantic entity."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique identifier for the concept.")
    name: str = Field(..., example="Artificial Intelligence", description="The primary name or label for the concept.")
    aliases: List[str] = Field(default_factory=list, example=["AI", "Machine Intelligence"], description="Alternative names or synonyms.")
    description: Optional[str] = Field(None, description="A brief, generated summary of the concept.")
    
    # [MODIFIED] - Fields are now Optional[float] with a default of None.
    weight: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0, 
        description="Conceptual importance within the source context (0.0 to 1.0)."
    )
    resonance: Optional[float] = Field(
        None, 
        ge=-1.0, 
        le=1.0, 
        description="Contextual sentiment or emotional charge (-1.0 to 1.0)."
    )
    
    relationships: List[Relationship] = Field(default_factory=list, description="List of relationships to other concepts.")
    metadata: Dict[str, any] = Field(default_for_factory=dict, description="Additional metadata, e.g., source document ID.")

class AnalysisRequest(BaseModel):
    """API model for an incoming analysis request."""
    text: str = Field(..., min_length=10, description="The raw text content to be analyzed.")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="A unique identifier for tracking the request.")

class AnalysisResponse(BaseModel):
    """API model for the response acknowledging an analysis job."""
    message: str = "Analysis job accepted."
    job_id: str
    status_topic: str
```

#### **2.2. Semantic Processing Logic (`semantic_processor.py`)**

**File Path:** `nous_service/app/services/semantic_processor.py`

**Analysis:** The `SemanticProcessor` has been significantly enhanced with new private methods (`_calculate_weight`, `_calculate_resonance`) to perform quantitative analysis.

*   `_calculate_weight`: A simple heuristic based on word count is implemented. It uses a logistic function to produce a normalized score between 0.0 and 1.0, where longer texts are considered more "weighty."
*   `_calculate_resonance`: A baseline sentiment analysis is implemented by matching words against predefined positive and negative word lists. This simulates the behavior of a more complex sentiment model, producing a score from -1.0 (negative) to 1.0 (positive).
*   `process_document`: This core method now invokes the new analytical functions and populates the `Concept` model with the calculated values before publication.

```python
# nous_service/app/services/semantic_processor.py
import re
import math
from app.api.v1.schemas import Concept
from app.services.event_publisher import EventPublisher

class SemanticProcessor:
    """
    Consumes messages from the 'documents.pending' topic,
    runs the semantic modeling pipeline, and publishes the
    resulting Concept model to the 'concepts.completed' topic.
    """
    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher
        # [NEW] Simple keyword lists for baseline resonance calculation.
        self._positive_words = {"good", "great", "excellent", "positive", "success", "benefit", "improve", "achieve", "love"}
        self._negative_words = {"bad", "terrible", "poor", "negative", "failure", "problem", "risk", "hate", "loss"}
        print("Semantic Processor initialized with new analysis capabilities.")

    def _calculate_weight(self, text: str) -> float:
        """
        Calculates the conceptual weight based on text length.
        
        Uses a logistic function to map word count to a 0.0-1.0 scale.
        This heuristic assumes longer texts have higher conceptual importance.
        """
        word_count = len(re.findall(r'\w+', text))
        # Logistic function parameters to control the curve's steepness and midpoint
        midpoint = 50  # Word count at which weight is 0.5
        steepness = 0.05
        weight = 1 / (1 + math.exp(-steepness * (word_count - midpoint)))
        return round(weight, 4)

    def _calculate_resonance(self, text: str) -> float:
        """
        Calculates the contextual resonance (sentiment) of the text.

        This is a simple, rule-based sentiment analysis. It counts positive
        and negative keywords and computes a normalized score from -1.0 to 1.0.
        """
        words = set(re.findall(r'\w+', text.lower()))
        pos_count = len(words.intersection(self._positive_words))
        neg_count = len(words.intersection(self._negative_words))
        
        total_count = pos_count + neg_count
        if total_count == 0:
            return 0.0  # Neutral if no keywords are found

        resonance = (pos_count - neg_count) / total_count
        return round(resonance, 4)

    async def process_document(self, message: dict):
        """
        The core processing logic for a single document.
        """
        text = message.get("text")
        request_id = message.get("request_id")

        if not text or not request_id:
            print(f"Skipping malformed message: {message}")
            return

        print(f"Processing document for request_id: {request_id}")

        # [NEW] Perform analysis to calculate weight and resonance.
        calculated_weight = self._calculate_weight(text)
        calculated_resonance = self._calculate_resonance(text)
        
        print(f"  - Calculated Weight: {calculated_weight}")
        print(f"  - Calculated Resonance: {calculated_resonance}")
        
        # [MODIFIED] Construct the Concept object with the new quantitative fields.
        # A real implementation would extract the 'name' more intelligently.
        main_concept = Concept(
            name="Processed Text Concept",
            aliases=["Document Analysis"],
            description=f"Analysis of text starting with: '{text[:50]}...'",
            weight=calculated_weight,
            resonance=calculated_resonance,
            metadata={"request_id": request_id, "source_text_length": len(text)}
        )

        # Publish the completed, enriched concept.
        await self.publisher.publish_completed_concept(concept=main_concept)
        print(f"Finished processing and published concept for request_id: {request_id}")
```