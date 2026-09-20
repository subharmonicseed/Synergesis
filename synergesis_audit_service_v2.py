"""Extended Glyph Protocol audit queries for beliefs, plans and world states."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from synergesis_audit_service import (
    DecisionAuditReport,
    EvidenceImpactReport,
    SynAuditService,
)
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph, GlyphEdge


@dataclass(frozen=True)
class BeliefAuditReport:
    fact: Glyph
    provenance_glyphs: Tuple[Glyph, ...]
    provenance_edges: Tuple[GlyphEdge, ...]
    evidence: Tuple[Glyph, ...]
    inferences: Tuple[Glyph, ...]
    premise_facts: Tuple[Glyph, ...]


@dataclass(frozen=True)
class PlanAuditReport:
    plan: Glyph
    provenance_glyphs: Tuple[Glyph, ...]
    previous_plans: Tuple[Glyph, ...]
    assessments: Tuple[Glyph, ...]
    goals: Tuple[Glyph, ...]
    steps: Tuple[Glyph, ...]


@dataclass(frozen=True)
class WorldStateAuditReport:
    world_state: Glyph
    facts: Tuple[Glyph, ...]
    inferences: Tuple[Glyph, ...]
    previous_world_states: Tuple[Glyph, ...]


class SynAuditServiceV2(SynAuditService):
    def why_fact(
        self,
        *,
        fact_glyph_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
    ) -> BeliefAuditReport:
        if (fact_glyph_id is None) == (evidence_id is None):
            raise ValueError("provide exactly one of fact_glyph_id or evidence_id")

        if evidence_id is not None:
            matches = self.graph.ledger.find_by_external_ref(
                evidence_id,
                glyph_type="fact",
            )
            if not matches:
                raise KeyError(f"unknown fact evidence id: {evidence_id}")
            fact = matches[-1]
        else:
            fact = self.graph.ledger.get(str(fact_glyph_id))
            if fact.glyph_type != "fact":
                raise ValueError("why_fact requires a fact glyph")

        trace = self.graph.upstream(fact.glyph_id, max_depth=32)
        others = tuple(g for g in trace.glyphs if g.glyph_id != fact.glyph_id)
        return BeliefAuditReport(
            fact=fact,
            provenance_glyphs=others,
            provenance_edges=trace.edges,
            evidence=tuple(g for g in others if g.glyph_type == "evidence"),
            inferences=tuple(g for g in others if g.glyph_type == "inference"),
            premise_facts=tuple(g for g in others if g.glyph_type == "fact"),
        )

    def why_plan(self, plan_glyph_id: str) -> PlanAuditReport:
        plan = self.graph.ledger.get(plan_glyph_id)
        if plan.glyph_type != "plan":
            raise ValueError("why_plan requires a plan glyph")
        trace = self.graph.upstream(plan.glyph_id, max_depth=32)
        others = tuple(g for g in trace.glyphs if g.glyph_id != plan.glyph_id)
        step_edges = [
            edge for edge in self.graph.ledger.edges()
            if edge.relation == "part_of" and edge.target == plan.glyph_id
        ]
        steps = tuple(self.graph.ledger.get(edge.source) for edge in step_edges)
        return PlanAuditReport(
            plan=plan,
            provenance_glyphs=others,
            previous_plans=tuple(g for g in others if g.glyph_type == "plan"),
            assessments=tuple(
                g for g in others
                if g.glyph_type == "decision"
                and g.content.get("kind") == "step_assessment"
            ),
            goals=tuple(g for g in others if g.glyph_type == "goal"),
            steps=steps,
        )

    def world_state(self, cognitive_cycle: int) -> WorldStateAuditReport:
        matches = self.graph.ledger.find_by_external_ref(
            f"cognitive-cycle:{cognitive_cycle}",
            glyph_type="cycle",
        )
        if not matches:
            raise KeyError(f"unknown cognitive cycle: {cognitive_cycle}")
        world = matches[-1]
        if world.content.get("kind") != "world_state":
            raise ValueError("glyph is not a world_state cycle")
        trace = self.graph.upstream(world.glyph_id, max_depth=2)
        others = tuple(g for g in trace.glyphs if g.glyph_id != world.glyph_id)
        previous = []
        for edge in self.graph.ledger.edges():
            if edge.source == world.glyph_id and edge.relation == "supersedes":
                candidate = self.graph.ledger.get(edge.target)
                if candidate.glyph_type == "cycle" and candidate.content.get("kind") == "world_state":
                    previous.append(candidate)
        return WorldStateAuditReport(
            world_state=world,
            facts=tuple(g for g in others if g.glyph_type == "fact"),
            inferences=tuple(g for g in others if g.glyph_type == "inference"),
            previous_world_states=tuple(previous),
        )
