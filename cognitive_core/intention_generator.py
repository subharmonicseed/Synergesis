"""Intention generator with memory bias integration."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
import time

from cognitive_core.glyph_core import GlyphData
from synergesis.cognitive_core import get_memory, MemorySystem

class IntentionGenerator:
    """Generate potential actions taking memory bias into account."""

    def __init__(self, base_conf: float = 0.75) -> None:
        """Initialize with base confidence level."""
        self.base_conf = base_conf

    # ---------- helpers ----------------------------------------------------
    def _compute_bias(self, tags: List[str]) -> float:
        """Return bias ∈ [-1, +1] from memory for given tags."""
        mem = get_memory()
        return mem.get_bias_for_context(tags)  # déjà borné

    def _apply_bias(self, base_conf: float, bias: float) -> float:
        """Apply memory bias to adjust confidence."""
        # Calculate adjusted confidence: negative bias lowers confidence
        # Using very strong bias factor (1.5) to ensure significant impact
        adjusted_conf = base_conf + bias * 1.5  # Using very strong bias factor
        # Clamp between 0.05 and 0.95 to maintain valid range
        return max(0.05, min(0.95, adjusted_conf))

    def _get_relevant_traces(self, tags: List[str]) -> List[Tuple[GlyphData, GlyphData]]:
        """Return all traces whose action possède au moins un des tags."""
        mem = get_memory()
        return [
            (action, outcome)
            for action, outcome, _ in mem.records
            if any(tag in getattr(action, "tags", []) for tag in tags)
        ]

    # ---------- public -----------------------------------------------------
    def propose_actions(self, tags: List[str] | None = None) -> List[GlyphData]:
        """Propose actions with bias-adjusted confidence."""
        tags = tags or ["autonomy", "phase_VIII"]
        
        bias = get_memory().get_bias_for_context(tags)  # [-1;+1]
        # Adjust confidence based on bias with a smaller factor
        conf = max(0.05, min(0.95, self.base_conf + bias * 0.20))
        
        # Set polarity and alignment based on bias
        polar, align = "neutral", "Void"
        if bias > 0.2:
            polar, align = "positive", "positive"
        elif bias < -0.2:
            polar, align = "negative", "negative"
        else:
            polar, align = "neutral", "neutral"
        
        # Create action with adjusted confidence
        return [GlyphData(
            id=f"gen-{uuid4()}",
            timestamp=int(time.time()),
            source="sem-intentiongenerator-C01",
            concept_type="POTENTIAL_ACTION",
            status="proposed",
            polarité=polar,
            alignement=align,
            content="Generated action",
            parent_doc_id="",
            metadata={"tags": tags},
            target_action_id="",
            result_structural={
                "local_entropy_delta": 0.0,
                "local_resonance_delta": 0.0
            },
            confidence=conf,
            simulated_outcome={
                "confidence": conf,
                "result_structural": {
                    "local_entropy_delta": 0.0,
                    "local_resonance_delta": 0.0
                }
            }
        )]
