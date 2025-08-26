import pytest
import time
from datetime import datetime
from synergesis.cognitive_core import get_memory

from synergesis.protocols.metabolic_protocol import run_cycle
from cognitive_core.glyph_core import GlyphData
from cognitive_core.intention_generator import IntentionGenerator

def _make_action(confidence: float, ent_delta: float, res_delta: float, tags):
    now = int(datetime.now().timestamp())
    return GlyphData(
        id="a1",
        concept_type="POTENTIAL_ACTION",
        status="proposed",
        source="test",
        timestamp=now,
        tags=tags,
        simulated_outcome={
            "confidence": confidence,
            "result_structural": {
                "local_entropy_delta": ent_delta,
                "local_resonance_delta": res_delta,
            },
        },
    )

def test_positive_bias_softens_thresholds():
    # on crée un tag "success" déjà présent en mémoire → bias positif
    mem = get_memory()
    mem.records = []  # Reset memory for clean test
    
    # Create multiple successful traces
    now = int(time.time())
    mem.current_time = now
    
    for i in range(3):
        # Create successful action
        success = _make_action(0.9, 0.8, 0.6, ["success"])
        success = success.model_copy(update={"status": "executed", "timestamp": now - i * 3600})
        mem.record_trace(success, success)
    
    # Create generator with base confidence
    gen = IntentionGenerator(base_conf=0.75)
    
    # Generate action with same tag
    actions = gen.propose_actions(["success"])
    assert len(actions) == 1
    
    # Check confidence is significantly above base
    action = actions[0]
    assert action.confidence > 0.80  # Should be above base
    assert action.polarité == "positive"
    assert action.alignement == "positive"

def test_negative_bias_hardens_thresholds():
    mem = get_memory()
    bad = _make_action(0.6, 0.0, 0.0, ["fail_tag"])
    bad = bad.model_copy(update={"status": "gated"})
    mem.record_trace(bad, bad)            # trace négative
    # action normalement OK mais avec tag négatif -> devrait être rejetée
    candidate = _make_action(0.80, -0.06, 6, ["fail_tag"])
    accepted = run_cycle([candidate])
    assert len(accepted) == 0, "bias négatif doit durcir les seuils"
