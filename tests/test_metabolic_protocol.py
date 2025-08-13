"""Tests for metabolic protocol."""

import pytest
from synergesis.protocols.metabolic_protocol import MetabolicProtocol, ActionThresholds
from cognitive_core.glyph_core import GlyphData

def test_gate_action_low_confidence():
    """Test gating with low confidence."""
    protocol = MetabolicProtocol()
    action = GlyphData(
        id="test-action",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="neutral",
        alignement="center",
        content="Test action",
        parent_doc_id="doc1",
        metadata={},
        target_action_id="",
        result_structural={
            "local_entropy_delta": -0.05,
            "local_resonance_delta": 5.0
        },
        confidence=0.6,
        simulated_outcome={
            "confidence": 0.6,
            "result_structural": {
                "local_entropy_delta": -0.05,
                "local_resonance_delta": 5.0
            }
        }
    )

    assert not protocol.gate_action(action)

def test_gate_action_high_entropy():
    """Test gating with high entropy."""
    protocol = MetabolicProtocol()
    action = GlyphData(
        id="test-action",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="neutral",
        alignement="center",
        content="Test action",
        parent_doc_id="doc1",
        metadata={},
        target_action_id="",
        result_structural={
            "local_entropy_delta": 0.1,
            "local_resonance_delta": 5.0
        },
        confidence=0.9,
        simulated_outcome={
            "confidence": 0.9,
            "result_structural": {
                "local_entropy_delta": 0.1,
                "local_resonance_delta": 5.0
            }
        }
    )

    assert not protocol.gate_action(action)

def test_gate_action_low_resonance():
    """Test gating with low resonance."""
    protocol = MetabolicProtocol()
    action = GlyphData(
        id="test-action",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="neutral",
        alignement="center",
        content="Test action",
        parent_doc_id="doc1",
        metadata={},
        target_action_id="",
        result_structural={
            "local_entropy_delta": -0.05,
            "local_resonance_delta": 3.0
        },
        confidence=0.9,
        simulated_outcome={
            "confidence": 0.9,
            "result_structural": {
                "local_entropy_delta": -0.05,
                "local_resonance_delta": 3.0
            }
        }
    )

    assert protocol.gate_action(action)

def test_gate_action_success():
    """Test successful gating."""
    protocol = MetabolicProtocol()
    action = GlyphData(
        id="test-action",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="neutral",
        alignement="center",
        content="Test action",
        parent_doc_id="doc1",
        metadata={},
        target_action_id="",
        result_structural={
            "local_entropy_delta": -0.05,
            "local_resonance_delta": 5.0
        },
        confidence=0.9,
        simulated_outcome={
            "confidence": 0.9,
            "result_structural": {
                "local_entropy_delta": -0.05,
                "local_resonance_delta": 5.0
            }
        }
    )

    assert protocol.gate_action(action)

def test_execute_action_with_storage():
    """Test action execution with Neo4j and MemorySystem."""
    # Create mock Neo4j and MemorySystem
    class MockNeo4j:
        def record_execution(self, action: GlyphData) -> GlyphData:
            # Create a mock execution record
            execution = GlyphData(
                id=f"exec-{action.id}",
                timestamp=action.timestamp,
                source=action.source,
                concept_type="EXECUTED_ACTION",
                status="executed",
                polarité=action.polarité,
                alignement=action.alignement,
                content=action.content,
                parent_doc_id=action.parent_doc_id,
                metadata={"executed_action_id": action.id},
                target_action_id=action.id,
                result_structural={},
                confidence=1.0,
                simulated_outcome={}
            )
            return execution

    class MockMemory:
        def record_trace(self, action, outcome):
            assert action.id == "action5"
            assert outcome.concept_type == "EXECUTED_ACTION"
            assert outcome.status == "executed"

    protocol = MetabolicProtocol(
        neo=MockNeo4j(),
        memory=MockMemory()
    )
    
    action = GlyphData(
        id="action5",
        timestamp=0,
        source="test",
        concept_type="ACTION",
        status="potential",
        polarité="neutral",
        alignement="center",
        content="Test action",
        parent_doc_id="doc1",
        metadata={}
    )
    
    execution = protocol.execute_action(action)
    assert execution.id.startswith("exec-action5")
    assert execution.status == "executed"
    assert execution.metadata["executed_action_id"] == "action5"
