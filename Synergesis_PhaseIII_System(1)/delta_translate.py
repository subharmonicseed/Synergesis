
# File: delta_translate.py
# Description: Synergesis TRANSLATE Protocol - Glyph-to-Language Compiler
# Version: 1.0

import yaml
import math
import random
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import logging
from copy import deepcopy

logger = logging.getLogger("SynergesisTranslate")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(ch)

POLARITY_MAP = {
    '+': {"intent": "Generate/Amplify", "verb_phrase": "generate novel perspectives on", "mood": "Constructive"},
    '-': {"intent": "Refine/Deconstruct", "verb_phrase": "critically refine the core assumptions of", "mood": "Analytical"},
    '0': {"intent": "Observe/Maintain", "verb_phrase": "objectively describe the current state of", "mood": "Neutral"},
    '±': {"intent": "Question/Oscillate", "verb_phrase": "explore the dualities and tensions within", "mood": "Inquisitive"},
    '?': {"intent": "Unknown/Assess", "verb_phrase": "assess the undefined nature of", "mood": "Uncertain"}
}

FREQUENCY_MAP = {
    (1, 40):   {"tempo": "Low (Stable)", "detail": "Abstract/Core", "stability_factor": 1.0, "adverb": "Fundamentally", "noun": "deep stability"},
    (41, 100): {"tempo": "Medium (Rhythmic)", "detail": "Structured/Process", "stability_factor": 0.6, "adverb": "Systematically", "noun": "rhythmic process"},
    (101, 144): {"tempo": "High (Volatile)", "detail": "Granular/Specifics", "stability_factor": 0.2, "adverb": "Rapidly", "noun": "high volatility"},
}

WEIGHT_MAP = {
    (1, 3):   {"importance": "Low/Peripheral", "resource": "Minimal", "adjective": "minor"},
    (4, 7):   {"importance": "Medium/Core", "resource": "Moderate", "adjective": "standard"},
    (8, 10):  {"importance": "High/Critical", "resource": "Significant", "adjective": "critical"},
}

ALIGNMENT_MAP = {
    'Celestial': {"perspective": "Visionary/Conceptual", "domain": "Ideas/Possibilities", "style": "Speculative", "adjective": "visionary"},
    'Chthonic': {"perspective": "Grounded/Analytical", "domain": "Data/Structure/Past", "style": "Critical", "adjective": "grounded"},
    'Void': {"perspective": "Essentialist/Meta", "domain": "Assumptions/Limits/Absence", "style": "Minimalist", "adjective": "essentialist"},
    'Harmonic': {"perspective": "Systemic/Relational", "domain": "Interactions/Equilibrium", "style": "Holistic", "adjective": "systemic"},
    'Elemental': {"perspective": "Dynamic/Transformative", "domain": "Actions/Energy/Change", "style": "Energetic", "adjective": "dynamic"},
    'Error': {"perspective": "Undefined", "domain": "Unknown", "style": "Undefined", "adjective": "undefined"},
}

def _get_map_value(value: int, mapping: Dict[Tuple[int, int], Dict], default_key_index: int = 0) -> Dict:
    for (min_v, max_v), result in mapping.items():
        if min_v <= value <= max_v:
            return result
    keys = list(mapping.keys())
    return mapping[keys[default_key_index]] if keys else {}

def _normalize(value: Optional[float], min_val: float, max_val: float) -> float:
    if pd.isna(value) or pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (float(value) - min_val) / (max_val - min_val)))

def _calculate_resonance(weight: int, frequency: int, entropy: Optional[float]) -> float:
    if not all(pd.notna([weight, frequency])):
        return 0.0
    entropy_val = entropy if pd.notna(entropy) else 0.5
    entropy_damp = (entropy_val * 1.5 + 0.3)
    freq_dev = abs(frequency - 72) / 72.0
    freq_damp = (freq_dev * 1.0 + 1.0)
    try:
        resonance = (weight * 12) / (entropy_damp * freq_damp)
        return round(max(0, resonance), 2)
    except ZeroDivisionError:
        return 0.0

def _get_stability_category(entropy: Optional[float], frequency: int) -> str:
    entropy_val = entropy if pd.notna(entropy) else 0.5
    freq_map = _get_map_value(frequency, FREQUENCY_MAP)
    freq_stability = freq_map.get("stability_factor", 0.5)
    entropy_stability = 1.0 - _normalize(entropy_val, 0.1, 1.8)
    combined_stability = freq_stability * 0.4 + entropy_stability * 0.6
    if combined_stability > 0.7:
        return "HIGH"
    if combined_stability > 0.4:
        return "MEDIUM"
    return "LOW"

def translate_glyph(glyph_json: dict) -> dict:
    output = {"natural_prompt": "[ERROR]", "ai_instruction": "", "semantic_yaml": "", "metrics": {}, "input_glyph": deepcopy(glyph_json)}
    try:
        polarity = glyph_json.get("polarité", "?")
        frequency = int(glyph_json.get("fréquence", 72))
        weight = int(glyph_json.get("poids", 5))
        alignment = glyph_json.get("alignement", "Void")
        tags = glyph_json.get("tags", [])
        entropy = glyph_json.get("entropy_score")
        source_ids = glyph_json.get("sourceIds", [])
        timestamp = glyph_json.get("timestamp", time.time())
        glyph_id = glyph_json.get("id", f"g-{int(time.time()*1000)}")

        pol = POLARITY_MAP.get(polarity, POLARITY_MAP['?'])
        freq = _get_map_value(frequency, FREQUENCY_MAP)
        wgt = _get_map_value(weight, WEIGHT_MAP)
        aln = ALIGNMENT_MAP.get(alignment, ALIGNMENT_MAP['Error'])

        resonance = _calculate_resonance(weight, frequency, entropy)
        emergence = weight * frequency
        stability = _get_stability_category(entropy, frequency)

        output["natural_prompt"] = f"Consider {tags}. From a {aln['adjective']} perspective, {freq['adverb']} {pol['verb_phrase']}. Focus with {wgt['adjective']} importance. Output should reflect a {freq['noun']} nature and {stability} stability."
        output["ai_instruction"] = f"// ID: {glyph_id}\nPRIORITY: {wgt['importance']}\nTASK_VERB: {polarity}\nSUBJECT_FOCUS: {tags}\nSTYLE: {aln['style']}\nTEMPO: {freq['tempo']}\nSTABILITY: {stability}\nRESONANCE: {resonance}\nEMERGENCE: {emergence}"
        output["semantic_yaml"] = yaml.dump({
            "glyph_id": glyph_id,
            "timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
            "symbolic_state": {
                "polarity": pol,
                "frequency": freq,
                "weight": wgt,
                "alignment": aln,
                "tags": tags,
                "entropy_score": entropy,
                "metrics": {
                    "resonance": resonance,
                    "emergence": emergence,
                    "stability": stability
                }
            },
            "source_lineage": source_ids
        }, sort_keys=False, allow_unicode=True)

        output["metrics"] = {
            "resonance": resonance,
            "emergence": emergence,
            "stability": stability
        }

    except Exception as e:
        output["natural_prompt"] = f"[ERROR: {e}]"
        output["ai_instruction"] = f"// ERROR: {e}"
        output["semantic_yaml"] = f"# ERROR: {e}"
        logger.error(f"translate_glyph error: {e}")

    return output
