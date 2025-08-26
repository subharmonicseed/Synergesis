"""Tests for IntentionGenerator with memory bias."""

import pytest
from datetime import datetime
from typing import List
import time

from cognitive_core.intention_generator import IntentionGenerator
from cognitive_core.glyph_core import GlyphData
from synergesis.cognitive_core import get_memory

def _make_action(confidence: float, ent_delta: float, res_delta: float, tags: List[str]) -> GlyphData:
    """Helper to create test actions."""
    return GlyphData(
        id="a1",
        concept_type="POTENTIAL_ACTION",
        status="executed",  # For positive bias
        source="test",
        timestamp=int(datetime.now().timestamp()),
        tags=tags,
        simulated_outcome={
            "confidence": confidence,
            "result_structural": {
                "local_entropy_delta": ent_delta,
                "local_resonance_delta": res_delta,
            },
        },
    )

def test_positive_bias_increases_confidence():
    """Positive memory bias should increase initial confidence."""
    # Set current time to now
    now = int(time.time())
    mem = get_memory()
    mem.current_time = now
    mem.records = []  # Reset memory for clean test
    
    # Create multiple successful traces
    for i in range(5):  # Multiple traces for stronger bias
        good = _make_action(0.95, -0.2, 10, ["autonomy", "phase_VIII"])
        good = good.model_copy(update={"status": "executed", "timestamp": now - i * 3600})  # 1 hour apart
        mem.record_trace(good, good)
    
    # Create generator with base confidence
    gen = IntentionGenerator(base_conf=0.75)
    
    # Generate action with same tag
    actions = gen.propose_actions(["autonomy", "phase_VIII"])
    assert len(actions) == 1
    
    # Check confidence is significantly above base
    action = actions[0]
    assert action.simulated_outcome["confidence"] > 0.85  # Should be well above base
    assert action.polarité == "positive"
    assert action.alignement == "positive"

def test_negative_bias_decreases_confidence():
    """Negative memory bias should decrease initial confidence."""
    # Set current time to now
    now = int(time.time())
    mem = get_memory()
    mem.current_time = now
    mem.records = []  # Reset memory for clean test
    
    # Create multiple failed traces
    for i in range(5):  # Multiple traces for stronger bias
        bad = _make_action(0.3, 0.2, 1, ["autonomy", "phase_VIII"])
        bad = bad.model_copy(update={"status": "gated", "timestamp": now - i * 3600})  # 1 hour apart
        mem.record_trace(bad, bad)
    
    # Create generator with base confidence
    gen = IntentionGenerator(base_conf=0.75)
    
    # Generate action with same tag
    actions = gen.propose_actions(["autonomy", "phase_VIII"])
    assert len(actions) == 1
    
    # Check confidence is significantly below base
    action = actions[0]
    assert action.confidence < 0.70  # Should be below base
    assert action.polarité == "negative"
    assert action.alignement == "negative"
