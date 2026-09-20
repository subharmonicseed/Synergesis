"""SYN Agent Loop v5: AEGIS + independent runtime reality verification.

V5 keeps V4's context-derived security provenance and inserts SYN-REALITY after
executor dispatch but before strategy learning.

The executor's return value is a claim. The value fed into learning is the
effective result established by the configured reality verifier.
"""
from __future__ import annotations

from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentContext,
    LearningSignal,
)
from synergesis_agent_loop_v4 import SynAgentLoopV4
from synergesis_glyph_protocol import Glyph
from synergesis_reality import RealityAssessment, RealityVerifier
from synergesis_prediction import PredictionEngine, PredictionSettlement


class SynAgentLoopV5(SynAgentLoopV4):
    def __init__(
        self,
        *,
        reality_verifier: RealityVerifier,
        prediction_engine: PredictionEngine | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.reality_verifier = reality_verifier
        self.reality_verifier.require_profiles_for(self.policy.allowed_actions)
        self.prediction_engine = prediction_engine
        self._reality_by_proposal: dict[str, RealityAssessment] = {}
        self._prediction_by_proposal: dict[str, PredictionSettlement] = {}

    def _execute_authorized_action(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
        action_glyph: Glyph,
        resource: str,
    ) -> ActionResult:
        if self.prediction_engine is not None:
            self.prediction_engine.predict_before_action(
                context=context,
                proposal=proposal,
                action_glyph_id=action_glyph.glyph_id,
            )

        raw = super()._execute_authorized_action(
            context=context,
            proposal=proposal,
            action_glyph=action_glyph,
            resource=resource,
        )
        assessment = self.reality_verifier.verify(
            proposal=proposal,
            action_glyph_id=action_glyph.glyph_id,
            resource=resource,
            raw_result=raw,
        )
        self._reality_by_proposal[proposal.proposal_id] = assessment

        if self.prediction_engine is not None:
            settlement = self.prediction_engine.settle(
                proposal=proposal,
                reality=assessment,
            )
            self._prediction_by_proposal[proposal.proposal_id] = settlement

        return assessment.effective_result

    def _evaluate_action(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
        result: ActionResult,
    ) -> LearningSignal:
        signal = super()._evaluate_action(
            context=context,
            proposal=proposal,
            result=result,
        )
        assessment = self._reality_by_proposal.get(proposal.proposal_id)
        if assessment is None:
            return LearningSignal(
                0.0,
                "SYN-REALITY missing assessment; model evaluation rejected.",
            )

        if (
            assessment.executor_claim_matches_reality is False
            or assessment.status in {"unverified", "observer_conflict"}
        ):
            return LearningSignal(
                0.0,
                (
                    "SYN-REALITY invalidated executor-derived learning "
                    f"(status={assessment.status}, "
                    f"claim_match={assessment.executor_claim_matches_reality}). "
                    f"Model lesson was not trusted: {signal.lesson}"
                ),
            )

        settlement = self._prediction_by_proposal.get(proposal.proposal_id)
        if settlement is None:
            return signal
        if settlement.status != "scored":
            return LearningSignal(
                signal.score,
                (
                    f"{signal.lesson} Prediction was not scored because "
                    "SYN-REALITY had no binary observed effect."
                ),
            )
        return LearningSignal(
            signal.score,
            (
                f"{signal.lesson} Prediction calibration: "
                f"p_success={settlement.probability_effect_success:.4f}, "
                f"observed={int(bool(settlement.observed_effect))}, "
                f"brier={settlement.brier_score:.6f}, "
                f"absolute_error={settlement.absolute_error:.6f}."
            ),
        )
