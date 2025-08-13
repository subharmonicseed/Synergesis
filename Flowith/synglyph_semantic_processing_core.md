```python
# nous.py
#
# This module provides the core logic for the SYNLGLYPH project's
# semantic processing service. It defines the data structures for concepts
# and implements the business logic for calculating semantic attributes.
#
# Sprint 3: Concept Model Enhancement Implementation
# Status: Production Ready
# Date: July 17, 2025

import math
import re
import logging
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field, ValidationError

# --- Configuration & Constants ---

# Configure a basic logger for the service
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - nous_service - %(message)s'
)

# Predefined keyword sets for resonance calculation.
# These are maintained as sets for efficient O(1) lookups.
POSITIVE_KEYWORDS: Set[str] = {
    'achieve', 'achieved', 'achievement',
    'benefit', 'breakthrough',
    'collaboration', 'collaborative',
    'efficiency', 'efficient', 'enhanced',
    'growth', 'grew',
    'innovate', 'innovation', 'innovative',
    'opportunity', 'opportunities', 'optimize', 'optimized',
    'positive', 'progress', 'progressive',
    'success', 'successful', 'synergy'
}

NEGATIVE_KEYWORDS: Set[str] = {
    'blocker', 'bottleneck',
    'challenge', 'concern', 'complex', 'complication',
    'delay', 'delayed',
    'error', 'escalation',
    'failure', 'failed',
    'issue', 'impediment',
    'limitation', 'loss',
    'negative',
    'problem', 'problematic',
    'risk', 'risky',
    'stagnant', 'stagnation'
}

# --- Pydantic Data Models ---

class Concept(BaseModel):
    """
    Represents a core semantic concept extracted from a text.

    Includes quantitative metrics for its significance (weight) and
    its emotional or strategic leaning (resonance).
    """
    uuid: str
    text: str
    weight: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Significance of the concept, derived from text length. Range: [0.0, 1.0]."
    )
    resonance: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Sentiment and strategic leaning based on keywords. Range: [-1.0, 1.0]."
    )


# --- Core Calculation Logic ---

def _calculate_weight(text: str) -> float:
    """
    Calculates the 'weight' of a text using a logistic function based on word count.

    The function is calibrated so that:
    - Short texts (~20 words) have a low weight (< 0.2).
    - Medium texts (~50 words) have a weight of ~0.5.
    - Long texts (~150 words) have a weight approaching 1.0 (> 0.9).

    Args:
        text: The input string to analyze.

    Returns:
        A float between 0.0 and 1.0 representing the text's weight.
    """
    if not isinstance(text, str) or not text.strip():
        return 0.0

    # Use regex to find all sequences of word characters (more robust than split())
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)

    # Logistic function parameters (calibrated to meet requirements)
    # k: Steepness of the curve
    # x0: The midpoint (word count for weight=0.5)
    k = 0.073
    x0 = 50.0

    try:
        # Logistic function: L / (1 + e^(-k * (x - x0)))
        # Here L (the maximum value) is 1.0.
        weight = 1.0 / (1.0 + math.exp(-k * (word_count - x0)))
    except OverflowError:
        # If word_count is extremely large, exp() can overflow.
        # In this case, the weight is effectively 1.0.
        weight = 1.0

    return weight


def _calculate_resonance(text: str) -> float:
    """
    Calculates the 'resonance' of a text based on keyword matching.

    Resonance is a measure of the text's positive vs. negative sentiment.
    - A score of 1.0 indicates purely positive keywords.
    - A score of -1.0 indicates purely negative keywords.
    - A score of 0.0 indicates a neutral balance or no relevant keywords.

    Args:
        text: The input string to analyze.

    Returns:
        A float between -1.0 and 1.0 representing the text's resonance.
    """
    if not isinstance(text, str) or not text.strip():
        return 0.0

    # Normalize text to lowercase and extract unique words to avoid double-counting
    words = set(re.findall(r'\b\w+\b', text.lower()))

    positive_matches = len(words.intersection(POSITIVE_KEYWORDS))
    negative_matches = len(words.intersection(NEGATIVE_KEYWORDS))

    total_matches = positive_matches + negative_matches

    if total_matches == 0:
        return 0.0

    # Formula: (Positive Hits - Negative Hits) / Total Hits
    resonance = (positive_matches - negative_matches) / total_matches
    return resonance


# --- Service Layer ---

def process_message(message: Dict) -> Optional[Concept]:
    """
    Main processing function for the nous_service.

    This function simulates the consumer logic for a message from a queue
    (e.g., Kafka). It validates the input message, extracts the text,
    calculates weight and resonance, and constructs a Concept object.

    Args:
        message: A dictionary representing the consumed JSON message.
                 Expected to have 'uuid' and 'text' keys.

    Returns:
        A validated `Concept` object if processing is successful.
        `None` if the input message is invalid or processing fails.
    """
    try:
        # 1. Validate incoming message structure
        if 'uuid' not in message or 'text' not in message:
            logging.warning(f"Message missing required keys 'uuid' or 'text'. Message: {message}")
            return None

        uuid = message['uuid']
        text = message.get('text', '') # Default to empty string for safety

        if not isinstance(text, str):
            logging.warning(f"Message 'text' field is not a string for uuid={uuid}. Type: {type(text)}")
            return None # Or handle as an error condition

        # 2. Perform calculations
        weight = _calculate_weight(text)
        resonance = _calculate_resonance(text)

        # 3. Create and validate the final Pydantic model
        concept_obj = Concept(
            uuid=uuid,
            text=text,
            weight=weight,
            resonance=resonance
        )
        logging.info(f"Successfully processed message for uuid={uuid}.")
        return concept_obj

    except ValidationError as e:
        # This will catch Pydantic validation errors (e.g., if a calculation
        # somehow produced a value out of the defined ge/le bounds).
        logging.error(f"Pydantic validation failed for uuid={message.get('uuid', 'N/A')}: {e}")
        return None
    except Exception as e:
        # Catch-all for any other unexpected errors during processing.
        logging.error(f"An unexpected error occurred processing message for uuid={message.get('uuid', 'N/A')}: {e}")
        return None


# --- Example Usage (for demonstration and local testing) ---
if __name__ == "__main__":
    print("--- Running `nous.py` in demonstration mode ---")

    # Example messages simulating consumption from a queue
    messages = [
        # TC-COR-01 & TC-EDG-01 (Short/Empty Text)
        {'uuid': 'doc-001', 'text': 'This is a short, neutral text about progress.'},
        # TC-COR-02 (Medium Text)
        {'uuid': 'doc-002', 'text': 'This medium-length text describes the successful synergy and collaborative growth achieved through our innovative new process optimization. The team worked hard to ensure efficiency and achieve all project goals.'},
        # TC-COR-03 (Long Text)
        {'uuid': 'doc-003', 'text': 'This extensive report details the breakthrough achievement in our quarterly performance. The innovative strategy led to unprecedented growth, and the successful implementation of the new system has enhanced efficiency across all departments. This progress marks a significant milestone, and the positive outcomes are a direct result of the team\'s dedication to optimizing every workflow. We are confident that this momentum will continue, driving further success and solidifying our market position. The collaborative spirit was a key factor, and every member should be proud of this accomplishment. This achievement is a testament to our core values and strategic vision for future growth and innovation.'},
        # TC-COR-04 (Positive Resonance)
        {'uuid': 'doc-004', 'text': 'Our success is due to innovation and growth.'},
        # TC-COR-05 (Negative Resonance)
        {'uuid': 'doc-005', 'text': 'The risk, delay, and failure created a serious issue.'},
        # TC-COR-06 (Mixed/Neutral Resonance)
        {'uuid': 'doc-006', 'text': 'Despite the initial risk, our innovation led to success.'},
        # TC-ERR-01 (Missing Key)
        {'uuid': 'doc-007', 'content': 'This message has the wrong key.'},
        # TC-EDG-02 (Whitespace only)
        {'uuid': 'doc-008', 'text': '   \n \t '}
    ]

    print("\nProcessing simulated messages:")
    for msg in messages:
        print("-" * 40)
        print(f"INPUT: {msg}")
        processed_concept = process_message(msg)
        if processed_concept:
            print(f"OUTPUT: {processed_concept.model_dump_json(indent=2)}")
        else:
            print("OUTPUT: Processing failed or message was invalid.")

    print("\n--- Demonstration complete ---")
```