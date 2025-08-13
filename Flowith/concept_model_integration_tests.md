```python
# selene.py
"""
Integration test suite for validating the 'Concept' model enhancements.

This suite, named `selene.py`, provides comprehensive, executable tests for the
new `weight` and `resonance` features. It covers the correctness of the underlying
calculation logic, end-to-end data flow simulation, edge case handling, and
error recovery, ensuring the features meet the specifications outlined in the
test plan: TP-20250717-CME-SELENE.

The tests are designed to be run using the pytest framework.
"""

import math
import re
import json
import logging
from typing import Dict, Any, Optional, Set

import pytest
from pydantic import BaseModel, Field, ValidationError

# ==============================================================================
# 1. Pydantic Models & Core Logic (Simulating the application's implementation)
#    This section simulates the actual code being tested as per Story-611.
# ==============================================================================

# As per Task 1.1: The enhanced Pydantic model.
class Concept(BaseModel):
    """Represents a concept with its calculated weight and resonance."""
    # Other fields would be present here in a real application.
    # text: str
    # id: str
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="The calculated importance of the concept, from 0.0 to 1.0."
    )
    resonance: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="The calculated semantic overtone, from -1.0 (negative) to 1.0 (positive)."
    )


# As per Task 1.3: The resonance calculation logic.
POSITIVE_KEYWORDS: Set[str] = {"brilliant", "excellent", "success", "perfect", "achieve", "wonderful", "innovative"}
NEGATIVE_KEYWORDS: Set[str] = {"failure", "awful", "terrible", "disaster", "problem", "error", "defect"}

def _calculate_resonance(text: str) -> float:
    """Calculates resonance based on keyword matching."""
    words = set(re.findall(r'\b\w+\b', text.lower()))
    
    pos_count = len(words.intersection(POSITIVE_KEYWORDS))
    neg_count = len(words.intersection(NEGATIVE_KEYWORDS))

    total_count = pos_count + neg_count
    if total_count == 0:
        return 0.0
    
    return (pos_count - neg_count) / total_count


# As per Task 1.2: The weight calculation logic.
def _calculate_weight(text: str) -> float:
    """Calculates weight using a logistic function based on word count."""
    word_count = len(re.findall(r'\b\w+\b', text.lower()))
    
    # Logistic function parameters calibrated to meet test case requirements:
    # x0 = 50 (midpoint)
    # k = 0.05 (growth rate)
    midpoint = 50.0
    growth_rate = 0.05
    
    try:
        # The logistic function: 1 / (1 + e^(-k*(x - x0)))
        return 1 / (1 + math.exp(-growth_rate * (word_count - midpoint)))
    except OverflowError:
        # Handles extremely large negative inputs to exp(), returning near-zero.
        return 0.0


def process_document_message(msg_body: str, logger: logging.Logger) -> Optional[Concept]:
    """
    Simulates the core logic of a Kafka consumer service.
    It deserializes a message, processes the text, and returns a Concept object.
    """
    try:
        # Simulate deserializing a JSON message from Kafka
        data: Dict[str, Any] = json.loads(msg_body)
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON message: {msg_body}")
        return None

    if "text" not in data:
        logger.warning(f"Message is missing required 'text' key: {data}")
        return None

    text_content = data.get("text", "")
    if not isinstance(text_content, str):
         logger.warning(f"Value for 'text' key is not a string: {text_content}")
         # Treat non-string content as empty for robustness
         text_content = ""

    # Calculate features
    weight = _calculate_weight(text_content)
    resonance = _calculate_resonance(text_content)

    # Return a structured Pydantic model
    return Concept(weight=weight, resonance=resonance)

# ==============================================================================
# 2. Pytest Test Suite (Story-612)
# ==============================================================================

class TestCalculationCorrectness:
    """
    Tests the core logic of the `_calculate_weight` and `_calculate_resonance` functions.
    Corresponds to Test Cases: TC-COR-01 to TC-COR-07.
    """

    def test_weight_calculation_for_short_text(self):
        """
        TC-COR-01: Verifies that the weight calculation for a short text (e.g., 20 words)
        results in a low value (< 0.2).
        """
        text = "This is a very short text, it has exactly twenty words to test the function's low-end response as expected."
        assert len(text.split()) == 20
        weight = _calculate_weight(text)
        assert weight < 0.2, f"Weight for short text should be < 0.2, but was {weight}"

    def test_weight_calculation_for_medium_text(self):
        """
        TC-COR-02: Verifies that the weight calculation for a medium text (50 words,
        the logistic function's midpoint) results in a value of approximately 0.5.
        """
        text = "This is a medium-length text that has been carefully constructed to contain exactly fifty words in total. This precise length is designed to hit the midpoint of the logistic function, which is the core of our weight calculation logic. The expected result for this specific input is a value very close to 0.5."
        assert len(text.split()) == 50
        weight = _calculate_weight(text)
        assert weight == pytest.approx(0.5), f"Weight for medium text should be ~0.5, but was {weight}"

    def test_weight_calculation_for_long_text(self):
        """
        TC-COR-03: Verifies that the weight calculation for a long text (e.g., 150 words)
        results in a high value approaching 1.0 (> 0.9).
        """
        base_phrase = "This is a single sentence that we are going to repeat many times. "
        # 15 words * 10 repetitions = 150 words
        text = base_phrase * 10
        assert len(text.split()) == 150
        weight = _calculate_weight(text)
        assert weight > 0.9, f"Weight for long text should be > 0.9, but was {weight}"

    def test_resonance_calculation_for_positive_keywords(self):
        """
        TC-COR-04: Verifies that resonance calculation for a text containing only positive
        keywords results in a score of exactly 1.0.
        """
        text = "A brilliant success and a perfect achievement. This innovative work is wonderful."
        resonance = _calculate_resonance(text)
        assert resonance == 1.0

    def test_resonance_calculation_for_negative_keywords(self):
        """
        TC-COR-05: Verifies that resonance calculation for a text containing only negative
        keywords results in a score of exactly -1.0.
        """
        text = "An awful failure and a terrible disaster. This created a serious problem and a defect."
        resonance = _calculate_resonance(text)
        assert resonance == -1.0

    def test_resonance_calculation_for_mixed_keywords(self):
        """
        TC-COR-06: Verifies that resonance calculation for a text with an equal number
        of positive and negative keywords results in a score of exactly 0.0.
        """
        text = "Despite one terrible failure, we had one brilliant success. The project was a problem, but we did achieve our goal."
        # Keywords used: failure, success, problem, achieve (2 neg, 2 pos)
        resonance = _calculate_resonance(text)
        assert resonance == 0.0

    def test_resonance_calculation_for_neutral_text(self):
        """
        TC-COR-07: Verifies that resonance calculation for a text with no relevant
        keywords results in a neutral score of exactly 0.0.
        """
        text = "The quick brown fox jumps over the lazy dog. This is standard placeholder text."
        resonance = _calculate_resonance(text)
        assert resonance == 0.0


class TestIntegrationAndDataFlow:
    """
    Tests the end-to-end flow through a simulated message pipeline.
    Corresponds to Test Case: TC-INT-01.
    """
    
    def test_end_to_end_pipeline_flow(self, caplog):
        """
        TC-INT-01: Tests the full end-to-end pipeline simulation. Verifies that processing
        a valid request results in a well-formed Concept object with weight and
        resonance fields within their defined constraints.
        """
        caplog.set_level(logging.INFO)
        input_text = "This is a test of the full pipeline. It is a brilliant success and a perfect example."
        message = json.dumps({"text": input_text, "request_id": "123-xyz"})

        result_concept = process_document_message(message, logging.getLogger())

        assert isinstance(result_concept, Concept)
        assert 0.0 <= result_concept.weight <= 1.0
        assert -1.0 <= result_concept.resonance <= 1.0
        assert result_concept.resonance > 0 # Should be positive due to keywords
        assert "Message is missing" not in caplog.text
        assert "Failed to decode" not in caplog.text

class TestEdgeCases:
    """
    Tests the system's behavior under boundary and unexpected conditions.
    Corresponds to Test Cases: TC-EDG-01 to TC-EDG-04.
    """

    def test_processing_of_empty_string_input(self, caplog):
        """
        TC-EDG-01: Verifies that the service handles an empty string as input text
        without crashing, producing a valid float for weight and 0.0 for resonance.
        """
        caplog.set_level(logging.INFO)
        message = json.dumps({"text": ""})
        
        result = process_document_message(message, logging.getLogger())

        assert isinstance(result, Concept)
        assert result.resonance == 0.0
        # Weight for 0 words should be a small but valid float.
        assert isinstance(result.weight, float)
        assert result.weight == pytest.approx(_calculate_weight(""))
        assert "Message is missing" not in caplog.text

    def test_processing_of_whitespace_and_punctuation_only(self, caplog):
        """
        TC-EDG-02: Verifies that the service handles text containing only whitespace
        and punctuation without crashing, returning a valid weight and a resonance of 0.0.
        """
        caplog.set_level(logging.INFO)
        message = json.dumps({"text": "  .?! \t\n- "})
        
        result = process_document_message(message, logging.getLogger())
        
        assert isinstance(result, Concept)
        assert result.resonance == 0.0
        # Word count is 0, so weight should be same as empty string case
        assert result.weight == pytest.approx(_calculate_weight(""))
        assert "Message is missing" not in caplog.text

    def test_pydantic_model_weight_validation(self):
        """
        TC-EDG-03: Verifies the Pydantic Concept model raises a ValidationError
        when instantiated with a weight outside its bounds [0.0, 1.0].
        """
        with pytest.raises(ValidationError, match="Input should be less than or equal to 1"):
            Concept(weight=1.5, resonance=0.5)
        
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
            Concept(weight=-0.5, resonance=0.5)

    def test_pydantic_model_resonance_validation(self):
        """
        TC-EDG-04: Verifies the Pydantic Concept model raises a ValidationError
        when instantiated with a resonance outside its bounds [-1.0, 1.0].
        """
        with pytest.raises(ValidationError, match="Input should be less than or equal to 1"):
            Concept(weight=0.5, resonance=2.0)
            
        with pytest.raises(ValidationError, match="Input should be greater than or equal to -1"):
            Concept(weight=0.5, resonance=-2.0)


class TestErrorHandling:
    """
    Tests the robustness of the service when consuming malformed data.
    Corresponds to Test Cases: TC-ERR-01 to TC-ERR-02.
    """

    def test_error_handling_for_message_with_missing_key(self, caplog):
        """
        TC-ERR-01: Verifies robust error handling when a message
        is missing the required 'text' key. The service should log a warning,
        not crash, and not produce an output object.
        """
        caplog.set_level(logging.WARNING)
        # Message is missing the 'text' key
        malformed_message = json.dumps({"content": "some other data", "id": 123})
        
        result = process_document_message(malformed_message, logging.getLogger())
        
        assert result is None
        assert "Message is missing required 'text' key" in caplog.text

    def test_error_handling_for_malformed_json_message(self, caplog):
        """
        TC-ERR-02: Verifies robust error handling for a non-JSON message.
        The consumer should handle the error gracefully, log it,
        and continue running without crashing.
        """
        caplog.set_level(logging.ERROR)
        # This is not a valid JSON string
        malformed_message = "this is not json"
        
        result = process_document_message(malformed_message, logging.getLogger())

        assert result is None
        assert "Failed to decode JSON message" in caplog.text

```