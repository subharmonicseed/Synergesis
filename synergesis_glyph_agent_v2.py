"""Glyph-audited Agent Loop v2.

Extends the existing Agent Loop audit adapter by linking each agent cycle to the
audited cognitive World Model snapshot created during that same cycle.
"""
from __future__ import annotations

from synergesis_glyph_agent import RecordedAgentCycle, SynGlyphAuditAdapter


class SynGlyphAuditAdapterV2(SynGlyphAuditAdapter):
    def run_cycle(self, **kwargs) -> RecordedAgentCycle:
        recorded = super().run_cycle(**kwargs)
        world_ref = f"cognitive-cycle:{recorded.cycle.cognitive_cycle}"
        worlds = self.graph.ledger.find_by_external_ref(
            world_ref,
            glyph_type="cycle",
        )
        if worlds:
            world = worlds[-1]
            self.graph.relate(
                recorded.cycle_glyph_id,
                world.glyph_id,
                "derived_from",
                actor=self.agent.kernel.identity,
                metadata={"role": "world_state"},
            )
        return recorded


class GlyphAuditedAgentProxy:
    """SynPlannerRuntime-compatible proxy around SynGlyphAuditAdapterV2.

    Planner code receives an ordinary AgentCycle while every cycle is
    automatically committed to the Glyph Graph.
    """

    def __init__(self, adapter: SynGlyphAuditAdapterV2):
        self.adapter = adapter
        self.agent = adapter.agent

    def __getattr__(self, name):
        return getattr(self.agent, name)

    def run_cycle(self, **kwargs):
        return self.adapter.run_cycle(**kwargs).cycle
