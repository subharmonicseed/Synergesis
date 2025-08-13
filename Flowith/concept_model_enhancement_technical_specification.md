**Document ID:** TS-20250717-CME-02
**Version:** 1.0
**Status:** Approved for Implementation
**Author:** Expert Analyst
**Date:** July 17, 2025

---

### **Technical Specification: Concept Model Enhancement**

### **1.0 Overview & Scope**

This document provides the formal technical specification for implementing quantitative semantic modeling within the SYNLGLYPH system. It details the required modifications to the core data model, defines the business logic for calculating conceptual `weight` and `resonance`, and outlines the implementation tasks.

This specification is the designated implementation guide for the work identified in the gap analysis document `GIA-20250717-CME-01`.

**Scope of Work:**
1.  **Data Model Modification:** Update the Pydantic `Concept` model to support optional `weight` and `resonance` fields.
2.  **Business Logic Implementation:** Implement the core analytical functions within the `SemanticProcessor` to calculate and populate these new fields.
3.  **Task Execution:** Follow the prescribed 6-task plan to deliver this feature.

---

### **2.0 Data Model Specification: `Concept`**

The `Concept` model defined in `nous_service/app/api/v1/schemas.py` must be modified to make the `weight` and `resonance` fields optional. This ensures backward compatibility and allows for cases where these values cannot be calculated.

#### **2.1 Required Modification**

The fields `weight` and `resonance` must be changed from required (`...`) to optional (`Optional[float]`) with a default value of `None`.

#### **2.2 Code-Level Specification**

The following change must be applied to `nous_service/app/api/v1/schemas.py`:

**BEFORE:**
```python
# nous_service/app/api/v1/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid

# ... other models ...

class Concept(BaseModel):
    """The core data model representing a semantic entity."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique identifier for the concept.")
    name: str = Field(..., example="Artificial Intelligence", description="The primary name or label for the concept.")
    aliases: List[str] = Field(default_factory=list, example=["AI", "Machine Intelligence"], description="Alternative names or synonyms.")
    description: Optional[str] = Field(None, description="A brief, generated summary of the concept.")
    weight: float = Field(..., ge=0.0, le=1.0, description="Conceptual importance within the source context (0.0 to 1.0).")
    resonance: float = Field(..., ge=-1.0, le=1.0, description="Contextual sentiment or emotional charge (-1.0 to 1.0).")
    relationships: List[Relationship] = Field(default_factory=list, description="List of relationships to other concepts.")
    metadata: Dict[str, any] = Field(default_for_factory=dict, description="Additional metadata, e.g., source document ID.")

# ... other models ...
```

**AFTER:**
```python
# nous_service/app/api/v1/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid

# ... other models ...

class Concept(BaseModel):
    """The core data model representing a semantic entity."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique identifier for the concept.")
    name: str = Field(..., example="Artificial Intelligence", description="The primary name or label for the concept.")
    aliases: List[str] = Field(default_factory=list, example=["AI", "Machine Intelligence"], description="Alternative names or synonyms.")
    description: Optional[str] = Field(None, description="A brief, generated summary of the concept.")
    weight: Optional[float] = Field(None, ge=0.0, le=1.0, description="Conceptual importance within the source context (0.0 to 1.0).")
    resonance: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Contextual sentiment or emotional charge (-1.0 to 1.0).")
    relationships: List[Relationship] = Field(default_for_factory=list, description="List of relationships to other concepts.")
    metadata: Dict[str, any] = Field(default_for_factory=dict, description="Additional metadata, e.g., source document ID.")

# ... other models ...
```

---

### **3.0 Business Logic Specification: `SemanticProcessor`**

The `SemanticProcessor` class in `nous_service/app/services/semantic_processor.py` must be enhanced with methods to calculate `weight` and `resonance`. The main `process_document` method will be updated to orchestrate these calculations.

> **Assumption:** The following logic assumes that a preliminary NLP step has already occurred to identify the primary `Concept` and its associated name/aliases from the source text.

#### **3.1 Weight Calculation Logic**

The `weight` of a concept measures its prominence or importance within the source text. The baseline implementation will use a normalized term frequency (TF) score.

*   **Method:** `_calculate_weight(self, text: str, concept_terms: List[str]) -> Optional[float]`
*   **Logic:**
    1.  Normalize the input `text` by converting it to lowercase and removing punctuation.
    2.  Tokenize the normalized text into a list of words.
    3.  Count the total number of words (`total_words`). If `total_words` is zero, return `None`.
    4.  Count the occurrences of all `concept_terms` (the concept's name and its aliases) within the normalized text.
    5.  Calculate the weight as `(occurrence_count / total_words) * 10`. The scaling factor of 10 helps to spread the values across the 0-1 range for typical document lengths.
    6.  Clip the final value to ensure it is within the `[0.0, 1.0]` bounds.

#### **3.2 Resonance Calculation Logic**

The `resonance` of a concept measures its associated sentiment or emotional charge. The baseline implementation will use a pre-trained sentiment analysis model. The `vaderSentiment` library is recommended for its simplicity and effectiveness without requiring heavy model downloads.

*   **Method:** `_calculate_resonance(self, text: str, concept_terms: List[str]) -> Optional[float]`
*   **Logic:**
    1.  Split the input `text` into individual sentences.
    2.  Identify all sentences that contain any of the `concept_terms` (case-insensitive).
    3.  If no relevant sentences are found, return `None`.
    4.  For each relevant sentence, calculate its sentiment polarity using a `SentimentIntensityAnalyzer`.
    5.  Extract the `compound` score from each sentence's polarity result. The compound score is a normalized, weighted composite score that ranges from -1 (most extreme negative) to +1 (most extreme positive).
    6.  The final `resonance` value is the average of all collected `compound` scores.

#### **3.3 Updated `semantic_processor.py` Implementation**

The following code reflects the complete implementation for the `SemanticProcessor`, including the new logic and updated dependencies.

```python
# app/services/semantic_processor.py
import re
from typing import List, Optional
from app.api.v1.schemas import Concept
from app.services.event_publisher import EventPublisher
# Add this dependency to requirements.txt: vaderSentiment
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class SemanticProcessor:
    """
    Consumes messages, runs the semantic modeling pipeline, and publishes the result.
    """
    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        print("Semantic Processor initialized with quantitative analysis capabilities.")

    def _calculate_weight(self, text: str, concept_terms: List[str]) -> Optional[float]:
        """Calculates conceptual weight based on normalized term frequency."""
        # Normalize text: lowercase and remove punctuation
        normalized_text = re.sub(r'[^\w\s]', '', text.lower())
        words = normalized_text.split()
        
        if not words:
            return None

        total_words = len(words)
        term_count = sum(1 for word in words if word in [t.lower() for t in concept_terms])
        
        # Raw weight is term frequency, scaled to better utilize the 0-1 range
        raw_weight = (term_count / total_words) * 10
        
        # Clip to ensure the value is between 0.0 and 1.0
        return max(0.0, min(1.0, raw_weight))

    def _calculate_resonance(self, text: str, concept_terms: List[str]) -> Optional[float]:
        """Calculates contextual resonance based on average sentiment of relevant sentences."""
        # Split text into sentences
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
        
        lower_concept_terms = [t.lower() for t in concept_terms]
        
        relevant_sentences = [
            s for s in sentences if any(term in s.lower() for term in lower_concept_terms)
        ]

        if not relevant_sentences:
            return None

        compound_scores = [
            self.sentiment_analyzer.polarity_scores(s)['compound'] for s in relevant_sentences
        ]
        
        # Return the average of the compound scores
        return sum(compound_scores) / len(compound_scores)

    async def process_document(self, message: dict):
        """
        The core processing logic for a single document.
        """
        text = message.get("text")
        request_id = message.get("request_id")
        print(f"Processing document for request_id: {request_id}")

        # === STAGE 1: NLP Entity/Concept Extraction (Placeholder) ===
        # In a real system, a sophisticated NLP model (e.g., spaCy, Transformers)
        # would extract concepts and their aliases. For this spec, we use a placeholder.
        main_concept_name = "Example Concept"
        main_concept_aliases = ["example"]
        # =============================================================

        # === STAGE 2: Quantitative Analysis ===
        concept_terms = [main_concept_name] + main_concept_aliases
        calculated_weight = self._calculate_weight(text, concept_terms)
        calculated_resonance = self._calculate_resonance(text, concept_terms)
        # ======================================

        # === STAGE 3: Construct and Publish Concept ===
        final_concept = Concept(
            name=main_concept_name,
            aliases=main_concept_aliases,
            weight=calculated_weight,
            resonance=calculated_resonance,
            metadata={"request_id": request_id, "source_text_snippet": text[:100]}
        )

        await self.publisher.publish_completed_concept(concept=final_concept)
        print(f"Finished processing and published concept for request_id: {request_id}")
```

---

### **4.0 Implementation Plan**

The work shall be executed according to the following 6-task plan, derived from the gap analysis. This plan constitutes the work for Sprint 2.

| Task ID | Story | Epic | Task Description | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Task-401** | Story-107 | EPIC-001 | Update `Concept` Pydantic model in `schemas.py` to make `weight` and `resonance` optional. | **High** |
| **Task-402** | Story-307 | EPIC-003 | Update/create test mocks to include `weight` and `resonance` values. | **High** |
| **Task-403** | Story-108 | EPIC-001 | Implement baseline logic in `SemanticProcessor` to calculate `weight` (e.g., based on term frequency). | **High** |
| **Task-404** | Story-108 | EPIC-001 | Implement baseline logic in `SemanticProcessor` to calculate `resonance` (e.g., using a pre-trained sentiment model). | **High** |
| **Task-405** | Story-108 | EPIC-002 | Ensure the full `Concept` object (with new fields) is correctly serialized and published to the `concepts.completed` Kafka topic. | **Medium** |
| **Task-406** | Story-307 | EPIC-003 | Enhance `test_e2e_pipeline.py` to assert that the consumed `Concept` contains valid `weight` and `resonance` data. | **Medium** |

---

### **5.0 Testing & Validation Requirements**

To ensure the quality and correctness of the implementation, the following testing activities are mandatory:

1.  **Unit Testing:**
    *   Create unit tests for the new `_calculate_weight` method. Test edge cases such as empty text, no matching terms, and results that require clipping.
    *   Create unit tests for the new `_calculate_resonance` method. Test with clearly positive, negative, neutral, and mixed-sentiment texts.
2.  **Integration Testing (`Selene` Suite):**
    *   **Test Mocks:** Any mock `Concept` objects used in tests must be updated to include realistic values for `weight` and `resonance`.
    *   **E2E Pipeline Test:** The `test_e2e_pipeline.py` test must be enhanced. The assertions must validate not only the presence of `weight` and `resonance` fields in the message consumed from Kafka but also that their values are plausible and fall within the expected ranges (`[0.0, 1.0]` for weight, `[-1.0, 1.0]` for resonance).