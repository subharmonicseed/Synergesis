"""Tests for the simulation engine."""

import pytest
from synergesis.cognitive_core.simulation_engine import SimulationEngine
from synergesis.cognitive_core.glyph_core import GlyphData

def test_simulate_action_entropy():
    """Test entropy damping simulation."""
    se = SimulationEngine()
    act = GlyphData(
        id="X",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="test",
        alignement="test",
        content="Test action",
        parent_doc_id="test_doc",
        metadata={"action_type": "ENTROPY_DAMPING"},
    )
    out = se.simulate_action(act, {"now_ts": 1.0})
    d = out.result_structural["local_entropy_delta"]
    assert d < 0, "entropy should decrease"

def test_simulate_action_resonance():
    """Test resonance boost simulation."""
    se = SimulationEngine()
    act = GlyphData(
        id="Y",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="test",
        alignement="test",
        content="Test action",
        parent_doc_id="test_doc",
        metadata={"action_type": "RESONANCE_BOOST"},
    )
    out = se.simulate_action(act, {"now_ts": 1.0})
    d = out.result_structural["local_resonance_delta"]
    assert d > 0, "resonance should increase"

def test_simulate_action_confidence():
    """Test confidence range."""
    se = SimulationEngine()
    act = GlyphData(
        id="Z",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="test",
        alignement="test",
        content="Test action",
        parent_doc_id="test_doc",
        metadata={"action_type": "ENTROPY_DAMPING"},
    )
    out = se.simulate_action(act, {"now_ts": 1.0})
    assert 0.6 <= out.confidence <= 0.9, "confidence should be between 0.6 and 0.9"
