
# File: text_to_glyph.py
# Description: Synergesis Δ-TRANSLATE Protocol - Text-to-Glyph Converter

import time
import random
import logging
import re
from typing import Dict, Any, Optional, List

# Define a minimal ALIGNMENT_MAP and polarity logic
ALIGNMENT_MAP = {
    'Celestial': 1.0,
    'Chthonic': 1.0,
    'Void': 1.0,
    'Harmonic': 1.0,
    'Elemental': 1.0,
}

logger = logging.getLogger("TextToGlyph")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

def _normalize(value: float, min_v: float, max_v: float) -> float:
    if max_v - min_v == 0:
        return 0.5
    return max(0.0, min(1.0, (value - min_v) / (max_v - min_v)))

def text_to_glyph(text: str, source_context: Optional[str] = "llm_response") -> Dict[str, Any]:
    ts = time.time()
    polarity = '0'
    sentiment = 0
    keywords = [word for word in re.findall(r'\b\w+\b', text.lower()) if len(word) > 4][:5]

    if any(w in text.lower() for w in ['hope', 'create', 'vision']):
        polarity = '+'
        sentiment = 0.6
    elif any(w in text.lower() for w in ['fear', 'loss', 'error']):
        polarity = '-'
        sentiment = -0.6
    elif '?' in text:
        polarity = '±'
        sentiment = 0.2

    frequency = max(1, min(144, int(_normalize(len(text), 10, 300) * 143)))
    weight = max(1, min(10, int(_normalize(len(keywords), 0, 5) * 9) + 1))

    alignment = random.choice(list(ALIGNMENT_MAP.keys()))

    glyph = {
        'id': f"auto-glyph-{int(ts)}",
        'polarité': polarity,
        'fréquence': frequency,
        'poids': weight,
        'alignement': alignment,
        'tags': keywords,
        'sourceIds': [source_context],
        'entropy_score': round(random.uniform(0.2, 1.2), 2),
        'timestamp': ts
    }

    logger.info(f"Text converted to glyph: {glyph}")
    return glyph

if __name__ == "__main__":
    sample = "The system shows signs of destabilization, we must create balance and seek transformation."
    g = text_to_glyph(sample)
    print(g)
