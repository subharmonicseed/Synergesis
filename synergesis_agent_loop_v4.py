"""SYN Agent Loop v4: context-derived AEGIS provenance.

v3 proved that AEGIS can narrow PermissionPolicy, but accepted a caller-supplied
SecurityContext. v4 closes that gap: the security context is built *inside* the
agent cycle from the exact facts/evidence/observation/hypotheses exposed to the
reasoner.

Consequences:
- selected external evidence cannot disappear from the authorization lineage;
- untrusted observations propagate through the proposed ActionGlyph;
- model text cannot choose its own capability grants;
- model text cannot define the canonical resource being authorized;
- missing Glyph provenance fails closed before executor dispatch.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentContext,
    AgentCycle,
    AgentObservation,
    Goal,
    LearningSignal,
    PolicyDecision,
    ReasoningOutput,
    SynAgentLoop,
    _canonical,
    _hash,
)
from synergesis_aegis import AegisGuard, SecurityContext
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph


class ObservationSecurityClassifier(Protocol):
    def taints_for(self, observation: AgentObservation) -> Sequence[str]:
        ...


@dataclass(frozen=True)
class TrustedSourceObservationClassifier:
    """Secure default: anything not explicitly trusted is external_untrusted."""

    trusted_sources: frozenset[str]

    def taints_for(self, observation: AgentObservation) -> Sequence[str]:
        if observation.source in self.trusted_sources:
            return ()
        return ("external_untrusted",)


class CapabilityResolver(Protocol):
    """Trusted control-plane resolver; never implemented by the reasoner."""

    def grant_ids(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
    ) -> Sequence[str]:
        ...


class NoCapabilities:
    def grant_ids(self, *, context: AgentContext, proposal: ActionProposal) -> Sequence[str]:
        return ()


class ResourceResolver(Protocol):
    """Resolve executor resource independently from natural-language rationale."""

    def resolve(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
    ) -> str:
        ...


@dataclass(frozen=True)
class ActionTypeResourceResolver:
    """Conservative resolver for actions whose authorization scope is action-wide."""

    namespace: str = "action"

    def resolve(self, *, context: AgentContext, proposal: ActionProposal) -> str:
        return f"{self.namespace}:{proposal.action_type}"


class SynAgentLoopV4(SynAgentLoop):
    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        aegis_guard: AegisGuard,
        observation_classifier: ObservationSecurityClassifier,
        capability_resolver: CapabilityResolver,
        resource_resolver: ResourceResolver,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.graph = graph
        self.aegis_guard = aegis_guard
        self.observation_classifier = observation_classifier
        self.capability_resolver = capability_resolver
        self.resource_resolver = resource_resolver

    def _goal_glyph(self, goal: Goal) -> Glyph:
        glyph = self.graph.create(
            "goal",
            actor=self.kernel.identity,
            content={"description": goal.description},
            external_refs=(goal.goal_id,),
            dedupe_external_ref=goal.goal_id,
        )
        if self.aegis_guard.security_graph.origin_binding(glyph.glyph_id) is None:
            self.aegis_guard.security_graph.bind_origin(
                glyph.glyph_id,
                authority_class="control_plane",
                reason="goal admitted through the agent control plane",
            )
        return glyph

    def _observation_glyph(
        self,
        observation: AgentObservation,
        observation_digest: str,
    ) -> Glyph:
        glyph = self.graph.create(
            "observation",
            actor=f"source:{observation.source}",
            content={
                "kind": observation.kind,
                "payload": dict(observation.payload),
                "source": observation.source,
                "observation_digest": observation_digest,
            },
            external_refs=(observation_digest,),
            dedupe_external_ref=observation_digest,
        )
        active = self.aegis_guard.security_graph.active_taints(glyph.glyph_id)
        labels = tuple(self.observation_classifier.taints_for(observation))
        for label in labels:
            if label not in active:
                self.aegis_guard.security_graph.mark_taint(
                    glyph.glyph_id,
                    label=label,
                    reason=f"observation source is not trusted: {observation.source}",
                )

        if self.aegis_guard.security_graph.origin_binding(glyph.glyph_id) is None:
            authority_class = (
                "external_untrusted"
                if "external_untrusted" in labels
                else "trusted_observation"
            )
            self.aegis_guard.security_graph.bind_origin(
                glyph.glyph_id,
                authority_class=authority_class,
                reason=f"observation ingress classification for source {observation.source}",
            )
        return glyph

    def _fact_glyph_ids(self, context: AgentContext) -> tuple[Tuple[str, ...], Tuple[str, ...]]:
        found = []
        missing = []
        for fact in context.facts:
            matches = self.graph.ledger.find_by_external_ref(
                fact.evidence_id,
                glyph_type="fact",
            )
            if matches:
                found.append(matches[-1].glyph_id)
            else:
                missing.append(fact.evidence_id)
        return tuple(found), tuple(missing)

    def _execute_authorized_action(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
        action_glyph: Glyph,
        resource: str,
    ) -> ActionResult:
        executor = self.executors.get(proposal.action_type)
        if executor is None:
            return ActionResult(
                proposal.action_type,
                False,
                {},
                "no_executor_registered",
            )
        result = executor(dict(proposal.parameters))
        if not isinstance(result, ActionResult):
            raise TypeError("action executor must return ActionResult")
        if result.action_type != proposal.action_type:
            raise ValueError(
                "executor returned a result for a different action type"
            )
        return result

    def _evaluate_action(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
        result: ActionResult,
    ) -> LearningSignal:
        signal = self.reasoner.evaluate(context, proposal, result)
        if not isinstance(signal, LearningSignal):
            raise TypeError("reasoner.evaluate must return LearningSignal")
        return signal

    def _evidence_glyph_ids(
        self,
        context: AgentContext,
    ) -> tuple[Tuple[str, ...], Tuple[str, ...]]:
        found = []
        missing = []
        for evidence in context.evidence:
            matches = self.graph.ledger.find_by_external_ref(
                evidence.evidence_id,
                glyph_type="evidence",
            )
            if matches:
                found.append(matches[-1].glyph_id)
            else:
                missing.append(evidence.evidence_id)
        return tuple(found), tuple(missing)

    def run_cycle(
        self,
        *,
        goal: Goal,
        observation: AgentObservation,
        required_predicates: Sequence[str] = (),
        rules: Sequence[Any] = (),
        action_scope: Optional[frozenset[str]] = None,
    ) -> AgentCycle:
        before_facts = tuple(self.core.memory.query())

        obs = self.kernel.observe(
            observation.kind,
            dict(observation.payload),
            observation.source,
        )
        goal_glyph = self._goal_glyph(goal)
        observation_glyph = self._observation_glyph(observation, obs.digest)
        self.graph.relate(
            observation_glyph.glyph_id,
            goal_glyph.glyph_id,
            "targets",
            actor=self.kernel.identity,
        )

        gaps = tuple(self.core.selene.gaps(required_predicates))
        all_evidence = tuple(self.aura.research.store.all())
        query = " ".join(
            (
                goal.description,
                observation.kind,
                _canonical(dict(observation.payload)),
            )
        )
        selected = self.context_selector.select(
            query=query,
            facts=before_facts,
            evidence=all_evidence,
        )
        context = AgentContext(
            goal=goal,
            observation=observation,
            facts=selected.facts,
            gaps=gaps,
            evidence=selected.evidence,
        )

        fact_glyph_ids, missing_fact_provenance = self._fact_glyph_ids(context)
        evidence_glyph_ids, missing_evidence_provenance = self._evidence_glyph_ids(context)

        reasoning = self.reasoner.reason(context)
        if not isinstance(reasoning, ReasoningOutput):
            raise TypeError("reasoner.reason must return ReasoningOutput")

        hypothesis_glyphs = []
        for hypothesis in reasoning.hypotheses:
            self._validate_evidence_refs(hypothesis.evidence_ids)
            self.kernel.memory.append(
                "hypothesis",
                asdict(hypothesis),
                self.kernel.identity,
            )
            self.kernel.blackboard.publish(
                f"hypothesis:{hypothesis.hypothesis_id[:16]}",
                asdict(hypothesis),
            )
            explicit_evidence = []
            for evidence_id in hypothesis.evidence_ids:
                matches = self.graph.ledger.find_by_external_ref(
                    evidence_id,
                    glyph_type="evidence",
                )
                if not matches:
                    missing_evidence_provenance = tuple(
                        sorted(set(missing_evidence_provenance + (evidence_id,)))
                    )
                else:
                    explicit_evidence.append(matches[-1].glyph_id)

            h = self.graph.create(
                "hypothesis",
                actor=self.kernel.identity,
                content={
                    "statement": hypothesis.statement,
                    "rationale": hypothesis.rationale,
                },
                external_refs=(hypothesis.hypothesis_id,),
                derived_from=tuple(
                    dict.fromkeys(
                        (
                            observation_glyph.glyph_id,
                            *explicit_evidence,
                        )
                    )
                ),
                dedupe_external_ref=hypothesis.hypothesis_id,
            )
            hypothesis_glyphs.append(h)

        proposal = reasoning.action
        policy_decision: Optional[PolicyDecision] = None
        action_result: Optional[ActionResult] = None
        learning: Optional[LearningSignal] = None
        strategy_stats = None

        if proposal is not None:
            self._validate_evidence_refs(proposal.evidence_ids)
            self.kernel.memory.append(
                "action_proposal",
                asdict(proposal),
                self.kernel.identity,
            )

            proposal_evidence_glyph_ids = []
            for evidence_id in proposal.evidence_ids:
                matches = self.graph.ledger.find_by_external_ref(
                    evidence_id,
                    glyph_type="evidence",
                )
                if not matches:
                    missing_evidence_provenance = tuple(
                        sorted(set(missing_evidence_provenance + (evidence_id,)))
                    )
                else:
                    proposal_evidence_glyph_ids.append(matches[-1].glyph_id)

            action_parents = tuple(
                dict.fromkeys(
                    (
                        goal_glyph.glyph_id,
                        observation_glyph.glyph_id,
                        *fact_glyph_ids,
                        *evidence_glyph_ids,
                        *proposal_evidence_glyph_ids,
                        *(h.glyph_id for h in hypothesis_glyphs),
                    )
                )
            )
            action_glyph = self.graph.create(
                "action",
                actor=self.kernel.identity,
                content={
                    "action_type": proposal.action_type,
                    "parameters": dict(proposal.parameters),
                    "expected_outcome": proposal.expected_outcome,
                    "strategy_key": proposal.strategy_key,
                },
                external_refs=(proposal.proposal_id,),
                derived_from=action_parents,
                dedupe_external_ref=proposal.proposal_id,
            )

            policy_decision = self.policy.check(proposal)
            if (
                policy_decision.allowed
                and action_scope is not None
                and proposal.action_type not in action_scope
            ):
                policy_decision = PolicyDecision(
                    False,
                    "action_type_outside_cycle_scope",
                )

            if policy_decision.allowed and (
                missing_fact_provenance or missing_evidence_provenance
            ):
                reason_bits = []
                if missing_fact_provenance:
                    reason_bits.append("facts")
                if missing_evidence_provenance:
                    reason_bits.append("evidence")
                policy_decision = PolicyDecision(
                    False,
                    "aegis:missing_context_provenance:" + ",".join(reason_bits),
                )

            if policy_decision.allowed:
                resource = self.resource_resolver.resolve(
                    context=context,
                    proposal=proposal,
                )
                if not isinstance(resource, str) or not resource.strip():
                    raise ValueError("resource_resolver must return a non-empty string")
                grant_ids = tuple(
                    self.capability_resolver.grant_ids(
                        context=context,
                        proposal=proposal,
                    )
                )
                security_context = SecurityContext(
                    actor_id=self.kernel.identity,
                    provenance_glyph_ids=(action_glyph.glyph_id,),
                    capability_grant_ids=grant_ids,
                    resource=resource,
                )
                policy_decision = self.aegis_guard.check(
                    proposal,
                    security_context,
                )

            self.kernel.memory.append(
                "policy_decision",
                {
                    "proposal_id": proposal.proposal_id,
                    **asdict(policy_decision),
                },
                self.kernel.identity,
            )

            if policy_decision.allowed:
                action_result = self._execute_authorized_action(
                    context=context,
                    proposal=proposal,
                    action_glyph=action_glyph,
                    resource=resource,
                )

                self.kernel.observe(
                    "action_result",
                    asdict(action_result),
                    f"executor:{proposal.action_type}",
                )
                learning = self._evaluate_action(
                    context=context,
                    proposal=proposal,
                    result=action_result,
                )

                self.strategy_ledger.append(proposal, action_result, learning)
                strategy_stats = self.strategy_ledger.stats(proposal.strategy_key)
                self.kernel.memory.append(
                    "learning_signal",
                    {
                        "proposal_id": proposal.proposal_id,
                        **asdict(learning),
                        "strategy_stats": asdict(strategy_stats),
                    },
                    self.kernel.identity,
                )

        cognitive = self.core.cycle_once(
            rules=rules,
            required_predicates=required_predicates,
        )
        after_facts = tuple(self.core.memory.query())
        drift = self.aura.echo.compare(before_facts, after_facts)

        reflexive = self.kernel.reflect()
        cycle_id = _hash(
            {
                "goal_id": goal.goal_id,
                "observation_digest": obs.digest,
                "cognitive_cycle": cognitive.cycle,
                "reflexive_cycle": reflexive.cycle,
                "proposal_id": proposal.proposal_id if proposal else None,
            }
        )
        self.kernel.memory.append(
            "agent_cycle",
            {
                "cycle_id": cycle_id,
                "goal_id": goal.goal_id,
                "cognitive_cycle": cognitive.cycle,
                "reflexive_cycle": reflexive.cycle,
                "policy": asdict(policy_decision) if policy_decision else None,
            },
            self.kernel.identity,
        )

        return AgentCycle(
            cycle_id=cycle_id,
            goal_id=goal.goal_id,
            observation_digest=obs.digest,
            hypotheses=reasoning.hypotheses,
            proposal=proposal,
            policy=policy_decision,
            action_result=action_result,
            learning=learning,
            strategy_stats=strategy_stats,
            drift=drift,
            cognitive_cycle=cognitive.cycle,
            reflexive_cycle=reflexive.cycle,
            memory_count=len(self.kernel.memory.read_all()),
        )
