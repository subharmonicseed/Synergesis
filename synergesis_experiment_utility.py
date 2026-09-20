"""Utility-aware filtering for causal experiments.

SYN-EXPERIMENT-UTILITY ranks *registered* causal interventions by combining
expected information gain with trusted, normalized impact estimates.

The utility function is explicit:

    U(a) = IG(a)
           - risk_weight * risk(a)
           - cost_weight * cost(a)
           - irreversibility_weight * irreversibility(a)

`risk`, `cost`, and `irreversibility` are normalized to [0, 1] and MUST come
from configuration supplied outside the reasoning model. Missing profiles are
not treated as zero-cost; such candidates are ineligible.

Hard policy constraints are evaluated before utility ranking. A candidate whose
risk or irreversibility exceeds policy bounds cannot be selected even if its
information gain is high.

This module never authorizes or executes an action. Its decision Glyph carries
`authorization_effect = "none"`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_causal_experiment import CausalExperimentRecommendation
from synergesis_glyph_protocol import GlyphAuditGraph


class LearnedRiskProvider(Protocol):
    def estimate(
        self,
        *,
        action_type: str,
        strategy_key: str,
        intervention: str,
    ):
        ...


@dataclass(frozen=True)
class ExperimentImpactProfile:
    action_type: str
    strategy_key: str
    intervention: str
    risk: float
    cost: float
    irreversibility: float

    def __post_init__(self):
        for name, value in (
            ("action_type", self.action_type),
            ("strategy_key", self.strategy_key),
            ("intervention", self.intervention),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        for name, value in (
            ("risk", self.risk),
            ("cost", self.cost),
            ("irreversibility", self.irreversibility),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0,1]")


@dataclass(frozen=True)
class ExperimentUtilityPolicy:
    risk_weight: float
    cost_weight: float
    irreversibility_weight: float
    minimum_utility: float
    minimum_information_gain_bits: float
    maximum_risk: float
    maximum_irreversibility: float
    tie_tolerance: float = 1e-12

    def __post_init__(self):
        for name, value in (
            ("risk_weight", self.risk_weight),
            ("cost_weight", self.cost_weight),
            ("irreversibility_weight", self.irreversibility_weight),
            ("minimum_information_gain_bits", self.minimum_information_gain_bits),
            ("maximum_risk", self.maximum_risk),
            ("maximum_irreversibility", self.maximum_irreversibility),
            ("tie_tolerance", self.tie_tolerance),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0")
        if not math.isfinite(self.minimum_utility):
            raise ValueError("minimum_utility must be finite")
        if self.maximum_risk > 1.0:
            raise ValueError("maximum_risk must be <= 1")
        if self.maximum_irreversibility > 1.0:
            raise ValueError("maximum_irreversibility must be <= 1")


@dataclass(frozen=True)
class ExperimentUtilityCandidate:
    intervention: str
    information_gain_bits: float
    risk: Optional[float]
    cost: Optional[float]
    irreversibility: Optional[float]
    utility: Optional[float]
    eligible: bool
    block_reasons: Tuple[str, ...]
    configured_risk_floor: Optional[float] = None
    learned_conservative_risk: Optional[float] = None

    def __post_init__(self):
        if not self.intervention.strip():
            raise ValueError("intervention is required")
        if (
            not math.isfinite(self.information_gain_bits)
            or self.information_gain_bits < -1e-12
        ):
            raise ValueError("information_gain_bits must be finite and nonnegative")
        for name, value in (
            ("risk", self.risk),
            ("cost", self.cost),
            ("irreversibility", self.irreversibility),
        ):
            if value is not None and (
                not math.isfinite(value) or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{name} must be None or in [0,1]")
        if self.utility is not None and not math.isfinite(self.utility):
            raise ValueError("utility must be finite when present")
        for name, value in (
            ("configured_risk_floor", self.configured_risk_floor),
            ("learned_conservative_risk", self.learned_conservative_risk),
        ):
            if value is not None and (
                not math.isfinite(value) or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{name} must be None or in [0,1]")
        if self.eligible and self.block_reasons:
            raise ValueError("eligible candidate cannot have block reasons")


@dataclass(frozen=True)
class ExperimentUtilityDecision:
    model_id: str
    action_type: str
    strategy_key: str
    status: str
    selected_intervention: Optional[str]
    selected_utility: Optional[float]
    candidates: Tuple[ExperimentUtilityCandidate, ...]
    recommendation_glyph_id: str
    decision_glyph_id: str

    def __post_init__(self):
        statuses = {
            "approved",
            "uninformative",
            "no_safe_candidate",
            "below_minimum_utility",
            "ambiguous_best",
        }
        if self.status not in statuses:
            raise ValueError("invalid experiment utility decision status")
        if self.status == "approved":
            if self.selected_intervention is None or self.selected_utility is None:
                raise ValueError("approved decision requires selected intervention/utility")
        elif (
            self.selected_intervention is not None
            or self.selected_utility is not None
        ):
            raise ValueError("non-approved utility decision cannot select intervention")


class ExperimentUtilityGate:
    """Trusted-config utility gate over causal experiment recommendations."""

    actor = "SYN-EXPERIMENT-UTILITY"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        profiles: Sequence[ExperimentImpactProfile],
        policy: ExperimentUtilityPolicy,
        learned_risk_provider: LearnedRiskProvider | None = None,
    ):
        self.graph = graph
        self.policy = policy
        self.learned_risk_provider = learned_risk_provider
        mapping: dict[tuple[str, str, str], ExperimentImpactProfile] = {}
        for profile in profiles:
            key = (
                profile.action_type,
                profile.strategy_key,
                profile.intervention,
            )
            if key in mapping:
                raise ValueError(
                    "duplicate experiment impact profile for "
                    f"{profile.action_type}/{profile.strategy_key}/"
                    f"{profile.intervention}"
                )
            mapping[key] = profile
        if not mapping:
            raise ValueError("at least one experiment impact profile is required")
        self.profiles = mapping

    def effective_risk(
        self,
        *,
        action_type: str,
        strategy_key: str,
        intervention: str,
    ) -> float:
        profile = self.profiles.get((action_type, strategy_key, intervention))
        if profile is None:
            raise ValueError("missing trusted impact profile")
        effective_risk = profile.risk
        if self.learned_risk_provider is not None:
            estimate = self.learned_risk_provider.estimate(
                action_type=action_type,
                strategy_key=strategy_key,
                intervention=intervention,
            )
            learned_risk = getattr(estimate, "conservative_risk", None)
            if learned_risk is not None:
                effective_risk = max(profile.risk, float(learned_risk))
        return effective_risk

    def _candidate(
        self,
        *,
        recommendation: CausalExperimentRecommendation,
        intervention: str,
        information_gain_bits: float,
    ) -> ExperimentUtilityCandidate:
        profile = self.profiles.get(
            (
                recommendation.action_type,
                recommendation.strategy_key,
                intervention,
            )
        )
        if profile is None:
            return ExperimentUtilityCandidate(
                intervention=intervention,
                information_gain_bits=information_gain_bits,
                risk=None,
                cost=None,
                irreversibility=None,
                utility=None,
                eligible=False,
                block_reasons=("missing_trusted_impact_profile",),
            )

        learned_risk = None
        effective_risk = self.effective_risk(
            action_type=recommendation.action_type,
            strategy_key=recommendation.strategy_key,
            intervention=intervention,
        )
        if self.learned_risk_provider is not None:
            estimate = self.learned_risk_provider.estimate(
                action_type=recommendation.action_type,
                strategy_key=recommendation.strategy_key,
                intervention=intervention,
            )
            learned_risk = getattr(estimate, "conservative_risk", None)

        reasons = []
        if information_gain_bits < self.policy.minimum_information_gain_bits:
            reasons.append("insufficient_information_gain")
        if effective_risk > self.policy.maximum_risk:
            reasons.append("risk_above_policy_maximum")
        if profile.irreversibility > self.policy.maximum_irreversibility:
            reasons.append("irreversibility_above_policy_maximum")

        utility = (
            information_gain_bits
            - self.policy.risk_weight * effective_risk
            - self.policy.cost_weight * profile.cost
            - self.policy.irreversibility_weight * profile.irreversibility
        )
        return ExperimentUtilityCandidate(
            intervention=intervention,
            information_gain_bits=information_gain_bits,
            risk=effective_risk,
            cost=profile.cost,
            irreversibility=profile.irreversibility,
            utility=utility,
            eligible=not reasons,
            block_reasons=tuple(reasons),
            configured_risk_floor=profile.risk,
            learned_conservative_risk=learned_risk,
        )

    def evaluate(
        self,
        recommendation: CausalExperimentRecommendation,
    ) -> ExperimentUtilityDecision:
        recommendation_glyph = self.graph.ledger.get(
            recommendation.recommendation_glyph_id
        )
        rc = recommendation_glyph.content
        if (
            recommendation_glyph.glyph_type != "decision"
            or rc.get("kind") != "causal_experiment_recommendation"
            or rc.get("model_id") != recommendation.model_id
            or rc.get("action_type") != recommendation.action_type
            or rc.get("strategy_key") != recommendation.strategy_key
            or rc.get("authorization_effect") != "none"
        ):
            raise ValueError("invalid causal experiment recommendation provenance")

        candidates = tuple(
            self._candidate(
                recommendation=recommendation,
                intervention=score.intervention,
                information_gain_bits=score.information_gain_bits,
            )
            for score in recommendation.scores
        )

        if all(
            candidate.information_gain_bits
            < self.policy.minimum_information_gain_bits
            for candidate in candidates
        ):
            status = "uninformative"
            selected = None
            selected_utility = None
        else:
            eligible = tuple(c for c in candidates if c.eligible)
            if not eligible:
                status = "no_safe_candidate"
                selected = None
                selected_utility = None
            else:
                maximum = max(
                    c.utility for c in eligible
                    if c.utility is not None
                )
                if maximum < self.policy.minimum_utility:
                    status = "below_minimum_utility"
                    selected = None
                    selected_utility = None
                else:
                    best = tuple(
                        c for c in eligible
                        if c.utility is not None
                        and math.isclose(
                            c.utility,
                            maximum,
                            abs_tol=self.policy.tie_tolerance,
                            rel_tol=0.0,
                        )
                    )
                    if len(best) != 1:
                        status = "ambiguous_best"
                        selected = None
                        selected_utility = None
                    else:
                        status = "approved"
                        selected = best[0].intervention
                        selected_utility = best[0].utility

        glyph = self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "causal_experiment_utility_decision",
                "model_id": recommendation.model_id,
                "action_type": recommendation.action_type,
                "strategy_key": recommendation.strategy_key,
                "status": status,
                "selected_intervention": selected,
                "selected_utility": selected_utility,
                "candidates": [asdict(candidate) for candidate in candidates],
                "policy": asdict(self.policy),
                "impact_source": "trusted_configuration",
                "causal_validity": "conditional_on_registered_models",
                "authorization_effect": "none",
                "recommendation_glyph_id": recommendation.recommendation_glyph_id,
            },
            derived_from=(recommendation.recommendation_glyph_id,),
        )

        return ExperimentUtilityDecision(
            model_id=recommendation.model_id,
            action_type=recommendation.action_type,
            strategy_key=recommendation.strategy_key,
            status=status,
            selected_intervention=selected,
            selected_utility=selected_utility,
            candidates=candidates,
            recommendation_glyph_id=recommendation.recommendation_glyph_id,
            decision_glyph_id=glyph.glyph_id,
        )
