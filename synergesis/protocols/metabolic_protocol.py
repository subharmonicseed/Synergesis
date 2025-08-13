"""Metabolic protocol for action gating and execution."""

from __future__ import annotations

from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
from datetime import datetime
import time

logger = logging.getLogger("synergesis.metabolic_protocol")

from synergesis.cognitive_core import get_memory
from synergesis.cognitive_core.glyph_core import GlyphData
from storage.neo4j_interface import Neo4jStorage

_MEMORY = get_memory()

# ---------------------------------------------------------------------------

@dataclass
class ActionThresholds:
    """Thresholds for action gating."""
    confidence_min: float = 0.75
    entropy_max_delta: float = -0.05
    resonance_min_delta: float = 5.0

# ---------------------------------------------------------------------------

def _adjust_thresholds(base: Dict[str, float], bias: float) -> Dict[str, float]:
    """Shift thresholds by memory bias (+ softens, – hardens)."""
    return {k: max(0.0, min(1.0, v + bias * 0.3)) for k, v in base.items()}

# ---------------------------------------------------------------------------

def run_cycle(actions: List[GlyphData]) -> List[GlyphData]:
    """
    Metabolic gating with memory bias.
    Returns the **approved** glyphs; rejected ones are cloned
    with `status="gated_by_memory"` and stored in memory.
    """
    accepted: List[GlyphData] = []
    base_thr = {
        "confidence_min": 0.75,
        "entropy_max_delta": -0.05,
        "resonance_min_delta": 5.0,
    }
    
    for act in actions:
        tags = getattr(act, "tags", [])
        bias = get_memory().get_bias_for_context(tags)  # [-1;+1]
        
        # Adjust thresholds based on bias
        thresholds = _adjust_thresholds(base_thr, bias)
        
        # Check if action meets adjusted thresholds
        if (act.simulated_outcome["confidence"] >= thresholds["confidence_min"] and
            act.simulated_outcome["result_structural"]["local_entropy_delta"] >= thresholds["entropy_max_delta"] and
            act.simulated_outcome["result_structural"]["local_resonance_delta"] >= thresholds["resonance_min_delta"]):
            accepted.append(act)
        else:
            # Clone and reject
            rejected = act.model_copy(
                update={
                    "status": "gated_by_memory",
                    "timestamp": int(time.time())
                }
            )
            get_memory().record_trace(act, rejected)
        
    return accepted

# ---------------------------------------------------------------------------

@dataclass
class MetabolicProtocol:
    """Metabolic protocol for action gating and execution.
    
    The protocol evaluates potential actions based on simulation outcomes and
    system thresholds, deciding whether to execute them or not.
    """

    def __init__(
        self,
        thresholds: Optional[ActionThresholds] = None,
        neo: Optional[Neo4jStorage] = None,
        memory: Optional[MemorySystem] = None
    ):
        """Initialize the metabolic protocol with optional custom thresholds and storage."""
        self.thresholds = thresholds or ActionThresholds()
        self.neo = neo
        self.memory = memory

    def gate_action(self, simulation_result: GlyphData) -> bool:
        """
        Gate a potential action based on simulation outcome.
        
        Args:
            simulation_result: The simulation outcome glyph containing:
                - confidence: float between 0 and 1
                - result_structural: dict with entropy/resonance deltas
                
        Returns:
            bool: True if action should be executed, False otherwise
        """
        tags = getattr(simulation_result, "tags", [])
        bias = get_memory().get_bias_for_context(tags) if self.memory else 0.0
        thr = _adjust_thresholds({
            "confidence_min": self.thresholds.confidence_min,
            "entropy_max_delta": self.thresholds.entropy_max_delta,
            "resonance_min_delta": self.thresholds.resonance_min_delta,
        }, bias)

        return (simulation_result.simulated_outcome["confidence"] >= thr["confidence_min"] and
                simulation_result.simulated_outcome["result_structural"]["local_entropy_delta"] <= thr["entropy_max_delta"] and
                simulation_result.simulated_outcome["result_structural"]["local_resonance_delta"] >= thr["resonance_min_delta"])

    def execute_action(self, action: GlyphData) -> GlyphData:
        """
        Execute an approved action and record the execution.
        
        Args:
            action: The action glyph to execute
            
        Returns:
            GlyphData: The execution record glyph
        """
        if self.neo is None:
            raise ValueError("Neo4jStorage is required for action execution")

        # Record the execution
        result = self.neo.record_execution(action)
        
        # Update memory with the successful execution
        if self.memory is not None:
            self.memory.record_trace(action, result)

        execution_time = datetime.now()
        return GlyphData(
            id=f"exec-{action.id}",
            timestamp=int(execution_time.timestamp()),
            source="metabolic_protocol",
            concept_type="EXECUTED_ACTION",
            status="executed",
            polarité="active",
            alignement="center",
            content=f"Executed action: {action.id}",
            parent_doc_id=action.parent_doc_id,
            metadata={
                "executed_action_id": action.id,
                "execution_timestamp": int(execution_time.timestamp())
            }
        )
        
        # Store in Neo4j if neo is provided
        if self.neo:
            self.neo.upsert_execution_record(execution_record, action.id)
            
        # Record in memory if memory is provided
        if self.memory:
            get_memory().record_trace(action, execution_record)
            
        return execution_record
