"""
Integration test for the full learning loop: Memory -> Intention -> Action.
"""

import pytest
import time

from cognitive_core.intention_generator import IntentionGenerator
from cognitive_core.glyph_core import GlyphData
from synergesis.cognitive_core import get_memory
from synergesis.protocols.metabolic_protocol import MetabolicProtocol, ActionThresholds
from synergesis.storage.neo4j_interface import Neo4jStorage

def test_learning_loop_with_negative_bias(mocker):
    """
    Tests that a history of failures leads to gating a similar new action.
    """
    # 1. Setup
    # Mock the storage dependency for the protocol
    mock_storage = mocker.patch("synergesis.protocols.metabolic_protocol.Neo4jStorage")
    protocol = MetabolicProtocol(
        neo=mock_storage,
        thresholds=ActionThresholds(
            confidence_min=0.7,
            entropy_max_delta=-0.05,
            resonance_min_delta=10.0
        )
    )

    # 2. Seed memory with negative bias
    mem = get_memory()
    mem.records = []  # Reset memory
    now = int(time.time())
    mem.current_time = now

    for i in range(5):
        failed_action = GlyphData(
            id=f"failed-action-{i}",
            timestamp=now - i * 100,
            source="test",
            concept_type="POTENTIAL_ACTION",
            status="gated", # This creates the negative bias
            tags=["test-tag"],
            confidence=0.3
        )
        mem.record_trace(failed_action, failed_action) # action and outcome are the same for simplicity

    # 3. Generate a new intention with the same tag
    intention_generator = IntentionGenerator(base_conf=0.8)
    proposed_actions = intention_generator.propose_actions(tags=["test-tag"])
    assert len(proposed_actions) == 1
    new_action = proposed_actions[0]

    # The confidence should be lowered by the negative bias
    assert new_action.confidence < 0.8

    # 4. Pass the new action to the metabolic protocol
    should_execute = protocol.gate_action(new_action)

    # 5. Assert that the protocol gates the action
    assert not should_execute, "Action should have been gated but was not."
