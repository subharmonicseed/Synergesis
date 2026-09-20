"""Planner bridge for bounded, verified causal experiments.

SYN-CAUSAL-PLANNING connects an *advisory* information-gain recommendation to
the existing bounded Planner without converting information value into
authority.

Security / epistemic boundary
-----------------------------
1. CausalExperimentSelector may recommend only.
2. A prepared directive grants no permission or capability.
3. The wrapped reasoner must propose exactly the directive's action type,
   strategy key and intervention value. A mismatch is removed before AEGIS.
4. The ordinary Agent Loop still sends any matching proposal through immutable
   PermissionPolicy + SYN-AEGIS.
5. The Planner considers an experiment completed only after SYN-REALITY has
   produced a scored settlement and SYN-CAUSAL-CREDIT has emitted a receipt
   showing that the requested intervention was independently verified.
6. A directive is single-use and durably marked consumed to reject replay.

A failed *effect* can still be a successful experiment: observing failure is
valid evidence when the intervention itself was independently verified.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Optional

from synergesis_agent_loop_v2 import (
    AgentContext,
    AgentObservation,
    Goal,
    LearningSignal,
    ReasoningOutput,
    ReasoningProvider,
)
from synergesis_causal_credit import CausalCreditBridge
from synergesis_causal_experiment import (
    CausalExperimentRecommendation,
    CausalExperimentSelector,
)
from synergesis_experiment_utility import (
    ExperimentUtilityDecision,
    ExperimentUtilityGate,
)
from synergesis_risk_budget import (
    RiskBudgetManager,
    RiskBudgetReservation,
)
from synergesis_glyph_planning import GlyphPlanningAudit
from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_planner import (
    MissionAdvance,
    MissionSnapshot,
    Plan,
    PlanDraft,
    PlanStep,
    PlanStepDraft,
    PlanningContext,
    PlanningProvider,
    StepAssessment,
)
from synergesis_prediction import PredictionEngine


DIRECTIVE_OBSERVATION_KIND = "causal_experiment_directive"
DIRECTIVE_SOURCE = "SYN-CAUSAL-PLANNING"


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CausalExperimentDirective:
    directive_id: str
    recommendation_glyph_id: str
    model_id: str
    action_type: str
    strategy_key: str
    intervention_parameter: str
    intervention: str
    directive_glyph_id: str


@dataclass(frozen=True)
class PreparedCausalExperiment:
    recommendation: CausalExperimentRecommendation
    directive: Optional[CausalExperimentDirective]
    mission: Optional[MissionSnapshot]
    observation: Optional[AgentObservation]
    utility_decision: Optional[ExperimentUtilityDecision] = None

    @property
    def executable(self) -> bool:
        utility_allows = (
            self.utility_decision is None
            or self.utility_decision.status == "approved"
        )
        return (
            utility_allows
            and self.directive is not None
            and self.mission is not None
            and self.observation is not None
        )


class CausalExperimentDirectiveRegistry:
    actor = "SYN-CAUSAL-PLANNING"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        causal_credit: CausalCreditBridge,
    ):
        if causal_credit.graph is not graph:
            raise ValueError("directive registry and causal credit must share graph")
        self.graph = graph
        self.causal_credit = causal_credit

    def _directive_ref(self, directive_id: str) -> str:
        return f"causal-experiment-directive:{directive_id}"

    def _consumed_ref(self, directive_id: str) -> str:
        return f"causal-experiment-consumed:{directive_id}"

    def prepare(
        self,
        recommendation: CausalExperimentRecommendation,
        *,
        utility_decision: ExperimentUtilityDecision | None = None,
    ) -> CausalExperimentDirective:
        if utility_decision is None:
            if recommendation.status != "informative":
                raise ValueError("only an informative recommendation can be prepared")
            if recommendation.selected_intervention is None:
                raise ValueError("informative recommendation has no selected intervention")
            selected_intervention = recommendation.selected_intervention
            utility_glyph_id = None
        else:
            if utility_decision.status != "approved":
                raise ValueError("utility decision must approve the experiment")
            if (
                utility_decision.model_id != recommendation.model_id
                or utility_decision.action_type != recommendation.action_type
                or utility_decision.strategy_key != recommendation.strategy_key
                or utility_decision.recommendation_glyph_id
                != recommendation.recommendation_glyph_id
            ):
                raise ValueError("utility decision does not match recommendation")
            selected_intervention = utility_decision.selected_intervention
            if selected_intervention is None:
                raise ValueError("approved utility decision has no intervention")
            if selected_intervention not in {
                score.intervention for score in recommendation.scores
            }:
                raise ValueError("utility-selected intervention is not registered")
            utility_glyph = self.graph.ledger.get(
                utility_decision.decision_glyph_id
            )
            uc = utility_glyph.content
            if (
                utility_glyph.glyph_type != "decision"
                or uc.get("kind") != "causal_experiment_utility_decision"
                or uc.get("status") != "approved"
                or uc.get("selected_intervention") != selected_intervention
                or uc.get("recommendation_glyph_id")
                != recommendation.recommendation_glyph_id
                or uc.get("authorization_effect") != "none"
            ):
                raise ValueError("invalid utility decision provenance")
            utility_glyph_id = utility_decision.decision_glyph_id

        key = (recommendation.action_type, recommendation.strategy_key)
        model = self.causal_credit.models.get(key)
        if model is None or model.model_id != recommendation.model_id:
            raise ValueError("recommendation does not match registered causal model")

        recommendation_glyph = self.graph.ledger.get(
            recommendation.recommendation_glyph_id
        )
        content = recommendation_glyph.content
        if (
            content.get("kind") != "causal_experiment_recommendation"
            or content.get("status") != recommendation.status
            or content.get("selected_intervention")
            != recommendation.selected_intervention
            or content.get("authorization_effect") != "none"
        ):
            raise ValueError("recommendation glyph does not match recommendation")

        body = {
            "recommendation_glyph_id": recommendation.recommendation_glyph_id,
            "utility_decision_glyph_id": utility_glyph_id,
            "model_id": model.model_id,
            "action_type": model.action_type,
            "strategy_key": model.strategy_key,
            "intervention_parameter": model.intervention_parameter,
            "intervention": selected_intervention,
        }
        directive_id = f"ced:{_digest(body)[:32]}"
        ref = self._directive_ref(directive_id)
        existing = self.graph.ledger.find_by_external_ref(
            ref,
            glyph_type="policy",
        )
        if existing:
            glyph = existing[-1]
        else:
            glyph = self.graph.create(
                "policy",
                actor=self.actor,
                content={
                    "kind": "causal_experiment_directive",
                    "directive_id": directive_id,
                    **body,
                    "authorization_effect": "none",
                    "single_use": True,
                    "status": "prepared",
                },
                external_refs=(ref,),
                derived_from=tuple(
                    glyph_id
                    for glyph_id in (
                        recommendation.recommendation_glyph_id,
                        utility_glyph_id,
                    )
                    if glyph_id is not None
                ),
                dedupe_external_ref=ref,
            )
        return CausalExperimentDirective(
            directive_id=directive_id,
            recommendation_glyph_id=recommendation.recommendation_glyph_id,
            model_id=model.model_id,
            action_type=model.action_type,
            strategy_key=model.strategy_key,
            intervention_parameter=model.intervention_parameter,
            intervention=selected_intervention,
            directive_glyph_id=glyph.glyph_id,
        )

    def get(self, directive_id: str) -> CausalExperimentDirective:
        if not isinstance(directive_id, str) or not directive_id.strip():
            raise ValueError("directive_id is required")
        matches = self.graph.ledger.find_by_external_ref(
            self._directive_ref(directive_id),
            glyph_type="policy",
        )
        if len(matches) != 1:
            raise ValueError("unknown or duplicated causal experiment directive")
        glyph = matches[0]
        c = glyph.content
        if (
            c.get("kind") != "causal_experiment_directive"
            or c.get("directive_id") != directive_id
            or c.get("authorization_effect") != "none"
            or c.get("single_use") is not True
        ):
            raise ValueError("invalid causal experiment directive")
        return CausalExperimentDirective(
            directive_id=directive_id,
            recommendation_glyph_id=str(c["recommendation_glyph_id"]),
            model_id=str(c["model_id"]),
            action_type=str(c["action_type"]),
            strategy_key=str(c["strategy_key"]),
            intervention_parameter=str(c["intervention_parameter"]),
            intervention=str(c["intervention"]),
            directive_glyph_id=glyph.glyph_id,
        )

    def consumed(self, directive_id: str) -> bool:
        return bool(
            self.graph.ledger.find_by_external_ref(
                self._consumed_ref(directive_id),
                glyph_type="decision",
            )
        )

    def consume(
        self,
        *,
        directive_id: str,
        proposal_id: str,
        cycle_id: str,
        causal_receipt_glyph_id: str,
    ) -> str:
        directive = self.get(directive_id)
        ref = self._consumed_ref(directive_id)
        if self.graph.ledger.find_by_external_ref(ref, glyph_type="decision"):
            raise ValueError("causal experiment directive already consumed")
        receipt = self.graph.ledger.get(causal_receipt_glyph_id)
        if receipt.content.get("kind") != "causal_credit":
            raise ValueError("directive consumption requires causal credit receipt")
        glyph = self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "causal_experiment_directive_consumed",
                "directive_id": directive_id,
                "proposal_id": proposal_id,
                "cycle_id": cycle_id,
                "causal_receipt_glyph_id": causal_receipt_glyph_id,
                "authorization_effect": "none",
            },
            external_refs=(ref,),
            derived_from=(
                directive.directive_glyph_id,
                causal_receipt_glyph_id,
            ),
            dedupe_external_ref=ref,
        )
        return glyph.glyph_id

    def observation(self, directive_id: str) -> AgentObservation:
        directive = self.get(directive_id)
        if self.consumed(directive_id):
            raise ValueError("causal experiment directive already consumed")
        # Values are supplied to the model for usability, but the reasoner gate
        # validates against the durable registry rather than trusting payload.
        return AgentObservation(
            DIRECTIVE_OBSERVATION_KIND,
            {
                "directive_id": directive.directive_id,
                "action_type": directive.action_type,
                "strategy_key": directive.strategy_key,
                "intervention_parameter": directive.intervention_parameter,
                "selected_intervention": directive.intervention,
            },
            DIRECTIVE_SOURCE,
        )


class CausalDirectiveReasoner:
    """ReasoningProvider gate that binds experiment proposals to directives."""

    actor = "SYN-CAUSAL-PLANNING"

    def __init__(
        self,
        *,
        base: ReasoningProvider,
        registry: CausalExperimentDirectiveRegistry,
    ):
        self.base = base
        self.registry = registry

    def _reject(
        self,
        *,
        context: AgentContext,
        reasoning: ReasoningOutput,
        directive: CausalExperimentDirective,
        reason: str,
    ) -> ReasoningOutput:
        self.registry.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "causal_experiment_binding_rejected",
                "directive_id": directive.directive_id,
                "reason": reason,
                "authorization_effect": "none",
            },
            derived_from=(directive.directive_glyph_id,),
        )
        return ReasoningOutput(reasoning.hypotheses, None)

    def reason(self, context: AgentContext) -> ReasoningOutput:
        reasoning = self.base.reason(context)
        if not isinstance(reasoning, ReasoningOutput):
            raise TypeError("base reasoner must return ReasoningOutput")
        if context.observation.kind != DIRECTIVE_OBSERVATION_KIND:
            return reasoning

        directive_id = context.observation.payload.get("directive_id")
        directive = self.registry.get(str(directive_id))
        if self.registry.consumed(directive.directive_id):
            return self._reject(
                context=context,
                reasoning=reasoning,
                directive=directive,
                reason="directive_already_consumed",
            )

        proposal = reasoning.action
        if proposal is None:
            return self._reject(
                context=context,
                reasoning=reasoning,
                directive=directive,
                reason="no_action_proposed",
            )
        if proposal.action_type != directive.action_type:
            return self._reject(
                context=context,
                reasoning=reasoning,
                directive=directive,
                reason="action_type_mismatch",
            )
        if proposal.strategy_key != directive.strategy_key:
            return self._reject(
                context=context,
                reasoning=reasoning,
                directive=directive,
                reason="strategy_key_mismatch",
            )
        actual = proposal.parameters.get(directive.intervention_parameter)
        if actual != directive.intervention:
            return self._reject(
                context=context,
                reasoning=reasoning,
                directive=directive,
                reason="intervention_mismatch",
            )

        self.registry.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "causal_experiment_binding_accepted",
                "directive_id": directive.directive_id,
                "proposal_id": proposal.proposal_id,
                "action_type": proposal.action_type,
                "strategy_key": proposal.strategy_key,
                "intervention": directive.intervention,
                "authorization_effect": "none",
            },
            derived_from=(directive.directive_glyph_id,),
        )
        return reasoning

    def evaluate(self, context, proposal, result) -> LearningSignal:
        return self.base.evaluate(context, proposal, result)


class CausalExperimentPlanningProvider:
    """PlanningProvider wrapper for prepared causal experiment missions."""

    def __init__(
        self,
        *,
        base: PlanningProvider,
        registry: CausalExperimentDirectiveRegistry,
        prediction: PredictionEngine,
    ):
        self.base = base
        self.registry = registry
        self.prediction = prediction

    def _directive(
        self,
        context: PlanningContext,
    ) -> Optional[CausalExperimentDirective]:
        if context.observation.kind != DIRECTIVE_OBSERVATION_KIND:
            return None
        directive_id = context.observation.payload.get("directive_id")
        return self.registry.get(str(directive_id))

    def create_plan(self, context: PlanningContext) -> PlanDraft:
        directive = self._directive(context)
        if directive is None:
            return self.base.create_plan(context)
        if directive.action_type not in context.allowed_actions:
            # Planning cannot add a capability that does not already exist.
            raise ValueError(
                "causal experiment action type is outside immutable planner permissions"
            )
        return PlanDraft(
            rationale=(
                "Execute one prepared causal experiment through the ordinary "
                "Agent Loop, AEGIS and SYN-REALITY path."
            ),
            steps=(
                PlanStepDraft(
                    description=(
                        f"Apply verified causal intervention "
                        f"{directive.intervention!r} for {directive.action_type}"
                    ),
                    success_criteria=(
                        "The intervention itself is independently observed and "
                        "SYN-CAUSAL-CREDIT emits a verified receipt."
                    ),
                    required_action_type=directive.action_type,
                ),
            ),
        )

    def _causal_receipt_for_cycle(
        self,
        cycle,
    ):
        if cycle.proposal is None:
            return None
        settlement = self.prediction.settlement_for(cycle.proposal.proposal_id)
        if settlement is None:
            return None
        receipts = self.registry.graph.ledger.find_by_external_ref(
            "causal-credit:" + settlement.prediction_id,
            glyph_type="learning",
        )
        return receipts[-1] if receipts else None

    def assess_step(
        self,
        context: PlanningContext,
        step: PlanStep,
        cycle,
    ) -> StepAssessment:
        directive = self._directive(context)
        if directive is None:
            return self.base.assess_step(context, step, cycle)

        proposal = cycle.proposal
        if proposal is None:
            return StepAssessment(
                "blocked",
                "The reasoner did not produce an action bound to the prepared experiment.",
                1.0,
            )
        if (
            proposal.action_type != directive.action_type
            or proposal.strategy_key != directive.strategy_key
            or proposal.parameters.get(directive.intervention_parameter)
            != directive.intervention
        ):
            return StepAssessment(
                "blocked",
                "The concrete proposal does not match the prepared causal directive.",
                1.0,
            )

        receipt = self._causal_receipt_for_cycle(cycle)
        if receipt is None:
            return StepAssessment(
                "blocked",
                "No verified SYN-CAUSAL-CREDIT receipt exists for this experiment.",
                1.0,
            )
        status = receipt.content.get("status")
        if status in {"unverified", "intervention_unverified"}:
            return StepAssessment(
                "blocked",
                f"Causal experiment was not independently verified ({status}).",
                1.0,
            )

        # `model_conflict`, `indeterminate`, and `conditional_update` are all
        # valid experimental outcomes once the intervention and binary effect
        # have been independently observed.
        if status not in {"model_conflict", "indeterminate", "conditional_update"}:
            return StepAssessment(
                "blocked",
                f"Unexpected causal-credit status: {status}",
                1.0,
            )

        self.registry.consume(
            directive_id=directive.directive_id,
            proposal_id=proposal.proposal_id,
            cycle_id=cycle.cycle_id,
            causal_receipt_glyph_id=receipt.glyph_id,
        )
        return StepAssessment(
            "completed",
            (
                "Prepared causal experiment completed with independently verified "
                f"intervention; causal-credit status={status}."
            ),
            1.0,
        )

    def replan(
        self,
        context: PlanningContext,
        previous_plan: Plan,
        failed_step: PlanStep,
        assessment: StepAssessment,
    ) -> PlanDraft:
        directive = self._directive(context)
        if directive is None:
            return self.base.replan(
                context,
                previous_plan,
                failed_step,
                assessment,
            )
        # A prepared experiment is single-use. A failed/blocked directive must
        # be inspected and a fresh recommendation prepared instead of silently
        # retrying or mutating the intervention.
        return PlanDraft(
            rationale=(
                "Do not silently mutate or retry a failed causal directive; "
                "prepare a fresh recommendation after inspection."
            ),
            steps=(
                PlanStepDraft(
                    description="Inspect failed causal experiment",
                    success_criteria="A new explicit causal recommendation is prepared.",
                    required_action_type=None,
                ),
            ),
        )


class CausalExperimentCoordinator:
    """Prepare, then explicitly execute, bounded causal experiment missions."""

    actor = "SYN-CAUSAL-PLANNING"

    def __init__(
        self,
        *,
        selector: CausalExperimentSelector,
        registry: CausalExperimentDirectiveRegistry,
        planner: GlyphPlanningAudit,
        utility_gate: ExperimentUtilityGate | None = None,
        risk_budget: RiskBudgetManager | None = None,
    ):
        if selector.graph is not registry.graph or planner.graph is not registry.graph:
            raise ValueError("causal experiment coordinator components must share graph")
        if utility_gate is not None and utility_gate.graph is not registry.graph:
            raise ValueError("experiment utility gate must share graph")
        if risk_budget is not None and risk_budget.graph is not registry.graph:
            raise ValueError("risk budget manager must share graph")
        if risk_budget is not None and utility_gate is None:
            raise ValueError("risk budget requires experiment utility gate")
        self.selector = selector
        self.registry = registry
        self.planner = planner
        self.utility_gate = utility_gate
        self.risk_budget = risk_budget
        self.graph = registry.graph
        self._mission_by_directive: dict[str, str] = {}

    def prepare(
        self,
        *,
        action_type: str,
        strategy_key: str,
    ) -> PreparedCausalExperiment:
        recommendation = self.selector.recommend(
            action_type=action_type,
            strategy_key=strategy_key,
        )
        utility_decision = (
            self.utility_gate.evaluate(recommendation)
            if self.utility_gate is not None
            else None
        )

        if self.utility_gate is None:
            if recommendation.status != "informative":
                return PreparedCausalExperiment(
                    recommendation=recommendation,
                    directive=None,
                    mission=None,
                    observation=None,
                    utility_decision=None,
                )
        elif utility_decision is None or utility_decision.status != "approved":
            return PreparedCausalExperiment(
                recommendation=recommendation,
                directive=None,
                mission=None,
                observation=None,
                utility_decision=utility_decision,
            )

        directive = self.registry.prepare(
            recommendation,
            utility_decision=utility_decision,
        )
        observation = self.registry.observation(directive.directive_id)
        goal = Goal.create(
            (
                "Perform the prepared causal experiment without expanding "
                f"permissions: action={directive.action_type}, "
                f"strategy={directive.strategy_key}, "
                f"{directive.intervention_parameter}={directive.intervention}."
            )
        )
        mission = self.planner.start(
            goal=goal,
            observation=observation,
        )
        self._mission_by_directive[directive.directive_id] = mission.mission_id

        plan_glyphs = self.graph.ledger.find_by_external_ref(
            mission.plan.plan_id,
            glyph_type="plan",
        )
        if plan_glyphs:
            self.graph.relate(
                plan_glyphs[-1].glyph_id,
                directive.directive_glyph_id,
                "derived_from",
                actor=self.actor,
            )

        return PreparedCausalExperiment(
            recommendation=recommendation,
            directive=directive,
            mission=mission,
            observation=observation,
            utility_decision=utility_decision,
        )

    def _revalidate_before_execution(
        self,
        directive: CausalExperimentDirective,
    ) -> None:
        current = self.selector.recommend(
            action_type=directive.action_type,
            strategy_key=directive.strategy_key,
        )
        current_utility = (
            self.utility_gate.evaluate(current)
            if self.utility_gate is not None
            else None
        )

        if current_utility is not None:
            valid = (
                current_utility.status == "approved"
                and current_utility.selected_intervention
                == directive.intervention
            )
            status = current_utility.status
            selected = current_utility.selected_intervention
            evidence_ids = (
                directive.directive_glyph_id,
                current.recommendation_glyph_id,
                current_utility.decision_glyph_id,
            )
        else:
            valid = (
                current.status == "informative"
                and current.selected_intervention == directive.intervention
            )
            status = current.status
            selected = current.selected_intervention
            evidence_ids = (
                directive.directive_glyph_id,
                current.recommendation_glyph_id,
            )

        glyph = self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "causal_experiment_freshness_check",
                "directive_id": directive.directive_id,
                "status": "fresh" if valid else "stale",
                "current_selector_status": current.status,
                "current_utility_status": (
                    current_utility.status
                    if current_utility is not None
                    else None
                ),
                "directive_intervention": directive.intervention,
                "current_selected_intervention": selected,
                "authorization_effect": "none",
            },
            derived_from=evidence_ids,
        )
        if not valid:
            raise ValueError(
                "stale causal experiment directive: current evidence/policy "
                f"no longer approves {directive.intervention!r} "
                f"(status={status}, selected={selected!r})"
            )

    def execute_prepared(
        self,
        directive_id: str,
    ) -> MissionAdvance:
        directive = self.registry.get(directive_id)
        if self.registry.consumed(directive_id):
            raise ValueError("causal experiment directive already consumed")
        self._revalidate_before_execution(directive)
        mission_id = self._mission_by_directive.get(directive_id)
        if mission_id is None:
            # Recover mission mapping after a coordinator restart from the plan
            # relation / directive description by scanning active plans.
            matches = []
            for glyph in self.graph.ledger.edges_to(
                directive.directive_glyph_id,
                relation="derived_from",
            ):
                plan = self.graph.ledger.get(glyph.source)
                if plan.glyph_type == "plan":
                    mission = plan.content.get("mission_id")
                    if isinstance(mission, str):
                        matches.append(mission)
            if len(set(matches)) != 1:
                raise ValueError("prepared causal experiment mission is unavailable")
            mission_id = matches[0]
            self._mission_by_directive[directive_id] = mission_id

        observation = self.registry.observation(directive_id)

        reservation: RiskBudgetReservation | None = None
        if self.risk_budget is not None:
            assert self.utility_gate is not None
            amount = self.utility_gate.effective_risk(
                action_type=directive.action_type,
                strategy_key=directive.strategy_key,
                intervention=directive.intervention,
            )
            reservation = self.risk_budget.reserve(
                directive_id=directive.directive_id,
                action_type=directive.action_type,
                strategy_key=directive.strategy_key,
                intervention=directive.intervention,
                amount=amount,
            )

        try:
            advance = self.planner.advance(
                mission_id=mission_id,
                observation=observation,
            )
        except Exception:
            # Deliberately keep any reservation active. We do not know whether
            # an external side effect happened before the exception.
            raise

        if reservation is not None:
            cycle = advance.cycle
            if (
                cycle is not None
                and cycle.action_result is not None
                and cycle.proposal is not None
            ):
                self.risk_budget.consume(
                    reservation,
                    cycle_id=cycle.cycle_id,
                    proposal_id=cycle.proposal.proposal_id,
                )
            else:
                self.risk_budget.release(
                    reservation,
                    cycle_id=cycle.cycle_id if cycle is not None else None,
                    proposal_id=(
                        cycle.proposal.proposal_id
                        if cycle is not None and cycle.proposal is not None
                        else None
                    ),
                )
        return advance
