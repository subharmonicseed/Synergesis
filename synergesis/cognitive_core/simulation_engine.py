"""Simulation engine for potential actions."""

from __future__ import annotations
import random
from typing import Any, Dict

from synergesis.cognitive_core.glyph_core import GlyphData

class SimulationEngine:
    """
    Very-first pass simulation:
    * reads a potential-action glyph
    * returns a simulated_outcome glyph with simple, probabilistic deltas
    """

    def simulate_action(
        self,
        potential_action: GlyphData,
        context: Dict[str, Any] | None = None,
    ) -> GlyphData:
        """Simulate the outcome of a potential action."""
        context = context or {}
        # naive model: entropy damping ⇒ lower entropy; resonance boost ⇒ raise res
        action = potential_action.metadata.get("action_type", "").lower()
        ent_delta = res_delta = 0.0
        if "entropy" in action:
            ent_delta = random.uniform(-0.08, -0.03)
            res_delta = random.uniform(-2, 0)
        elif "resonance" in action:
            res_delta = random.uniform(10, 20)
            ent_delta = random.uniform(-0.02, 0.05)

        return GlyphData(
            id=f"simout-{potential_action.id}",
            timestamp=context.get("now_ts", 0.0),
            source="sem-simulationengine-V01",
            concept_type="SIMULATED_OUTCOME",
            status="simulated_outcome",
            target_action_id=potential_action.id,
            result_structural={
                "local_entropy_delta": ent_delta,
                "local_resonance_delta": res_delta,
            },
            confidence=round(random.uniform(0.6, 0.9), 2),
        )
