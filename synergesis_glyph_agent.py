"""Glyph Protocol v1 integration for the Synergesis agent loop.

This adapter records the externally observable cognitive trace of each completed
agent cycle. It does NOT claim to expose a model's private chain-of-thought.

Recorded chain:
goal -> observation/evidence -> hypothesis -> decision -> action -> policy
-> outcome -> learning -> cycle

The graph can later answer:
- Why was this decision taken?
- Which evidence supported it?
- What happened after the action?
- Which later decisions are impacted if an evidence glyph is invalidated?
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from synergesis_agent_loop_v2 import AgentCycle, AgentObservation, Goal, SynAgentLoop
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph


@dataclass(frozen=True)
class RecordedAgentCycle:
    cycle: AgentCycle
    goal_glyph_id: str
    observation_glyph_id: str
    evidence_glyph_ids: Tuple[str, ...]
    hypothesis_glyph_ids: Tuple[str, ...]
    decision_glyph_id: str
    action_glyph_id: Optional[str]
    policy_glyph_id: Optional[str]
    outcome_glyph_id: Optional[str]
    learning_glyph_id: Optional[str]
    cycle_glyph_id: str


class SynGlyphAuditAdapter:
    def __init__(self, *, agent: SynAgentLoop, graph: GlyphAuditGraph):
        self.agent = agent
        self.graph = graph

    def _evidence_for_ids(self, ids: Sequence[str]) -> tuple[Any, ...]:
        wanted = set(ids)
        return tuple(
            e for e in self.agent.aura.research.store.all()
            if e.evidence_id in wanted
        )

    def _ensure_evidence_glyph(self, evidence: Any) -> Glyph:
        return self.graph.create(
            "evidence",
            actor=f"source:{evidence.source_type}",
            content={
                "title": evidence.title,
                "source": evidence.source,
                "source_type": evidence.source_type,
                "retrieved_at": evidence.retrieved_at,
                "content_digest_only": True,
            },
            external_refs=(evidence.evidence_id,),
            metadata={
                "content_sha256": __import__("hashlib").sha256(
                    evidence.content.encode("utf-8")
                ).hexdigest()
            },
            dedupe_external_ref=evidence.evidence_id,
        )

    def run_cycle(
        self,
        *,
        goal: Goal,
        observation: AgentObservation,
        required_predicates: Sequence[str] = (),
        rules: Sequence[Any] = (),
        action_scope: Optional[frozenset[str]] = None,
    ) -> RecordedAgentCycle:
        cycle = self.agent.run_cycle(
            goal=goal,
            observation=observation,
            required_predicates=required_predicates,
            rules=rules,
            action_scope=action_scope,
        )

        goal_glyph = self.graph.create(
            "goal",
            actor=self.agent.kernel.identity,
            content={"description": goal.description},
            external_refs=(goal.goal_id,),
            dedupe_external_ref=goal.goal_id,
        )

        observation_glyph = self.graph.create(
            "observation",
            actor=f"source:{observation.source}",
            content={
                "kind": observation.kind,
                "payload": dict(observation.payload),
                "source": observation.source,
                "observation_digest": cycle.observation_digest,
            },
            external_refs=(cycle.observation_digest,),
            dedupe_external_ref=cycle.observation_digest,
        )
        self.graph.relate(
            observation_glyph.glyph_id,
            goal_glyph.glyph_id,
            "targets",
            actor=self.agent.kernel.identity,
        )

        referenced_evidence_ids = sorted({
            evidence_id
            for hypothesis in cycle.hypotheses
            for evidence_id in hypothesis.evidence_ids
        } | (
            set(cycle.proposal.evidence_ids) if cycle.proposal else set()
        ))
        evidence_glyphs = tuple(
            self._ensure_evidence_glyph(e)
            for e in self._evidence_for_ids(referenced_evidence_ids)
        )
        evidence_by_external = {
            g.external_refs[0]: g for g in evidence_glyphs if g.external_refs
        }

        hypothesis_glyphs = []
        for hypothesis in cycle.hypotheses:
            parents = [observation_glyph.glyph_id]
            parents.extend(
                evidence_by_external[eid].glyph_id
                for eid in hypothesis.evidence_ids
                if eid in evidence_by_external
            )
            hg = self.graph.create(
                "hypothesis",
                actor=self.agent.kernel.identity,
                content={
                    "statement": hypothesis.statement,
                    "rationale": hypothesis.rationale,
                },
                external_refs=(hypothesis.hypothesis_id,),
                derived_from=parents,
                dedupe_external_ref=hypothesis.hypothesis_id,
            )
            for eid in hypothesis.evidence_ids:
                if eid in evidence_by_external:
                    self.graph.relate(
                        evidence_by_external[eid].glyph_id,
                        hg.glyph_id,
                        "supports",
                        actor=self.agent.kernel.identity,
                    )
            hypothesis_glyphs.append(hg)

        decision_content: dict[str, Any] = {
            "decision": "propose_action" if cycle.proposal else "no_action",
            "goal_id": goal.goal_id,
        }
        if cycle.proposal:
            decision_content.update({
                "proposal_id": cycle.proposal.proposal_id,
                "rationale": cycle.proposal.rationale,
                "expected_outcome": cycle.proposal.expected_outcome,
            })

        decision = self.graph.create(
            "decision",
            actor=self.agent.kernel.identity,
            content=decision_content,
            external_refs=(f"decision:{cycle.cycle_id}",),
            derived_from=(
                [goal_glyph.glyph_id, observation_glyph.glyph_id]
                + [h.glyph_id for h in hypothesis_glyphs]
            ),
            dedupe_external_ref=f"decision:{cycle.cycle_id}",
        )
        for h in hypothesis_glyphs:
            self.graph.relate(
                h.glyph_id,
                decision.glyph_id,
                "motivates",
                actor=self.agent.kernel.identity,
            )

        action_glyph = None
        policy_glyph = None
        outcome_glyph = None
        learning_glyph = None

        if cycle.proposal is not None:
            action_glyph = self.graph.create(
                "action",
                actor=self.agent.kernel.identity,
                content={
                    "action_type": cycle.proposal.action_type,
                    "parameters": dict(cycle.proposal.parameters),
                    "expected_outcome": cycle.proposal.expected_outcome,
                    "strategy_key": cycle.proposal.strategy_key,
                },
                external_refs=(cycle.proposal.proposal_id,),
                derived_from=(decision.glyph_id,),
                dedupe_external_ref=cycle.proposal.proposal_id,
            )
            self.graph.relate(
                decision.glyph_id,
                action_glyph.glyph_id,
                "proposes",
                actor=self.agent.kernel.identity,
            )

        if cycle.policy is not None and action_glyph is not None:
            policy_glyph = self.graph.create(
                "policy",
                actor="PermissionPolicy",
                content={
                    "allowed": cycle.policy.allowed,
                    "reason": cycle.policy.reason,
                },
                external_refs=(f"policy:{cycle.cycle_id}",),
                derived_from=(action_glyph.glyph_id,),
                dedupe_external_ref=f"policy:{cycle.cycle_id}",
            )
            self.graph.relate(
                policy_glyph.glyph_id,
                action_glyph.glyph_id,
                "authorizes" if cycle.policy.allowed else "denies",
                actor="PermissionPolicy",
            )

        if cycle.action_result is not None and action_glyph is not None:
            outcome_glyph = self.graph.create(
                "outcome",
                actor=f"executor:{cycle.action_result.action_type}",
                content={
                    "action_type": cycle.action_result.action_type,
                    "success": cycle.action_result.success,
                    "output": dict(cycle.action_result.output),
                    "error": cycle.action_result.error,
                },
                external_refs=(f"outcome:{cycle.cycle_id}",),
                derived_from=(action_glyph.glyph_id,),
                dedupe_external_ref=f"outcome:{cycle.cycle_id}",
            )
            self.graph.relate(
                action_glyph.glyph_id,
                outcome_glyph.glyph_id,
                "produces",
                actor=self.agent.kernel.identity,
            )

        if cycle.learning is not None and outcome_glyph is not None:
            learning_glyph = self.graph.create(
                "learning",
                actor=self.agent.kernel.identity,
                content={
                    "score": cycle.learning.score,
                    "lesson": cycle.learning.lesson,
                    "strategy_stats": (
                        asdict(cycle.strategy_stats)
                        if cycle.strategy_stats is not None else None
                    ),
                },
                external_refs=(f"learning:{cycle.cycle_id}",),
                derived_from=(outcome_glyph.glyph_id,),
                dedupe_external_ref=f"learning:{cycle.cycle_id}",
            )
            self.graph.relate(
                learning_glyph.glyph_id,
                outcome_glyph.glyph_id,
                "evaluates",
                actor=self.agent.kernel.identity,
            )

        component_ids = [
            goal_glyph.glyph_id,
            observation_glyph.glyph_id,
            decision.glyph_id,
        ]
        component_ids.extend(g.glyph_id for g in evidence_glyphs)
        component_ids.extend(g.glyph_id for g in hypothesis_glyphs)
        for item in (action_glyph, policy_glyph, outcome_glyph, learning_glyph):
            if item is not None:
                component_ids.append(item.glyph_id)

        cycle_glyph = self.graph.create(
            "cycle",
            actor=self.agent.kernel.identity,
            content={
                "cycle_id": cycle.cycle_id,
                "cognitive_cycle": cycle.cognitive_cycle,
                "reflexive_cycle": cycle.reflexive_cycle,
                "memory_count": cycle.memory_count,
                "drift": asdict(cycle.drift),
            },
            external_refs=(cycle.cycle_id,),
            derived_from=component_ids,
            dedupe_external_ref=cycle.cycle_id,
        )

        return RecordedAgentCycle(
            cycle=cycle,
            goal_glyph_id=goal_glyph.glyph_id,
            observation_glyph_id=observation_glyph.glyph_id,
            evidence_glyph_ids=tuple(g.glyph_id for g in evidence_glyphs),
            hypothesis_glyph_ids=tuple(g.glyph_id for g in hypothesis_glyphs),
            decision_glyph_id=decision.glyph_id,
            action_glyph_id=action_glyph.glyph_id if action_glyph else None,
            policy_glyph_id=policy_glyph.glyph_id if policy_glyph else None,
            outcome_glyph_id=outcome_glyph.glyph_id if outcome_glyph else None,
            learning_glyph_id=learning_glyph.glyph_id if learning_glyph else None,
            cycle_glyph_id=cycle_glyph.glyph_id,
        )
