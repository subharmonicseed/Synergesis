"""Information-gain experiment selection for registered causal models.

SYN-CAUSAL-EXPERIMENT does not authorize or execute actions.  It ranks only
intervention labels already present in a trusted :class:`CausalModel` and emits
an auditable recommendation.

For a current hypothesis distribution H and binary verified effect Y, the
expected information gain of intervention a is

    IG(a) = H(H) - E_{Y|a}[H(H | Y, a)]

with entropy measured in bits.  If no intervention has positive information
value, or if several interventions tie within policy tolerance, the selector
returns no unique intervention rather than inventing a preference.

The calculation is conditional on the registered hypotheses and likelihoods;
it is experimental-design guidance, not proof that those models are causally
valid.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Optional, Sequence, Tuple

from synergesis_causal_credit import CausalCreditBridge, CausalModel
from synergesis_glyph_protocol import GlyphAuditGraph


def _entropy_bits(probabilities: Sequence[float]) -> float:
    return -sum(p * math.log2(p) for p in probabilities if p > 0.0)


def _normalize(values: Sequence[float]) -> tuple[float, ...]:
    total = sum(values)
    if total <= 0.0:
        return tuple(0.0 for _ in values)
    return tuple(value / total for value in values)


@dataclass(frozen=True)
class CausalExperimentPolicy:
    minimum_information_gain_bits: float = 1e-9
    tie_tolerance_bits: float = 1e-12

    def __post_init__(self):
        for name, value in (
            ("minimum_information_gain_bits", self.minimum_information_gain_bits),
            ("tie_tolerance_bits", self.tie_tolerance_bits),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0")


@dataclass(frozen=True)
class InterventionScore:
    intervention: str
    predicted_success_probability: float
    predicted_failure_probability: float
    prior_entropy_bits: float
    expected_posterior_entropy_bits: float
    information_gain_bits: float
    success_posterior: Mapping[str, float]
    failure_posterior: Mapping[str, float]

    def __post_init__(self):
        for name, value in (
            ("predicted_success_probability", self.predicted_success_probability),
            ("predicted_failure_probability", self.predicted_failure_probability),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0,1]")
        for name, value in (
            ("prior_entropy_bits", self.prior_entropy_bits),
            ("expected_posterior_entropy_bits", self.expected_posterior_entropy_bits),
            ("information_gain_bits", self.information_gain_bits),
        ):
            if not math.isfinite(value) or value < -1e-12:
                raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True)
class CausalExperimentRecommendation:
    model_id: str
    action_type: str
    strategy_key: str
    status: str
    selected_intervention: Optional[str]
    tied_interventions: Tuple[str, ...]
    scores: Tuple[InterventionScore, ...]
    current_posterior: Mapping[str, float]
    recommendation_glyph_id: str

    def __post_init__(self):
        if self.status not in {
            "informative",
            "uninformative",
            "ambiguous_best",
        }:
            raise ValueError("invalid causal experiment recommendation status")
        if self.status == "informative" and self.selected_intervention is None:
            raise ValueError("informative recommendation requires an intervention")
        if self.status != "informative" and self.selected_intervention is not None:
            raise ValueError("non-unique recommendation must not select an intervention")


class CausalExperimentSelector:
    """Rank interventions already registered in SYN-CAUSAL-CREDIT.

    This object has no executor, AEGIS capability, or permission surface.  The
    recommendation is a decision Glyph for auditability only.
    """

    actor = "SYN-CAUSAL-EXPERIMENT"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        causal_credit: CausalCreditBridge,
        policy: CausalExperimentPolicy = CausalExperimentPolicy(),
    ):
        if causal_credit.graph is not graph:
            raise ValueError("causal credit and experiment selector must share graph")
        self.graph = graph
        self.causal_credit = causal_credit
        self.policy = policy

    @staticmethod
    def _interventions(model: CausalModel) -> tuple[str, ...]:
        labels = tuple(label for label, _ in model.hypotheses[0].responses)
        if not labels:
            raise ValueError("causal model has no registered interventions")
        return labels

    @staticmethod
    def _posterior_for_outcome(
        weights: Sequence[float],
        likelihoods: Sequence[float],
        *,
        observed_success: bool,
    ) -> tuple[float, ...]:
        terms = [
            weight * (p if observed_success else 1.0 - p)
            for weight, p in zip(weights, likelihoods)
        ]
        return _normalize(terms)

    def score_intervention(
        self,
        *,
        model: CausalModel,
        posterior: Mapping[str, float],
        intervention: str,
    ) -> InterventionScore:
        ids = [h.belief_evidence_id for h in model.hypotheses]
        try:
            weights = [float(posterior[evidence_id]) for evidence_id in ids]
        except KeyError as exc:
            raise ValueError("posterior is missing a registered hypothesis") from exc
        if any(not math.isfinite(w) or w < 0.0 for w in weights):
            raise ValueError("posterior weights must be finite and nonnegative")
        normalized = _normalize(weights)
        if not math.isclose(sum(normalized), 1.0, abs_tol=1e-12):
            raise ValueError("posterior must have positive total mass")

        likelihoods = []
        for hypothesis in model.hypotheses:
            responses = dict(hypothesis.responses)
            if intervention not in responses:
                raise ValueError("intervention is not registered in every hypothesis")
            likelihoods.append(float(responses[intervention]))

        p_success = sum(w * p for w, p in zip(normalized, likelihoods))
        p_failure = 1.0 - p_success
        success_posterior = self._posterior_for_outcome(
            normalized,
            likelihoods,
            observed_success=True,
        )
        failure_posterior = self._posterior_for_outcome(
            normalized,
            likelihoods,
            observed_success=False,
        )

        prior_entropy = _entropy_bits(normalized)
        expected_entropy = (
            p_success * _entropy_bits(success_posterior)
            + p_failure * _entropy_bits(failure_posterior)
        )
        information_gain = max(0.0, prior_entropy - expected_entropy)

        return InterventionScore(
            intervention=intervention,
            predicted_success_probability=p_success,
            predicted_failure_probability=p_failure,
            prior_entropy_bits=prior_entropy,
            expected_posterior_entropy_bits=expected_entropy,
            information_gain_bits=information_gain,
            success_posterior={
                evidence_id: value
                for evidence_id, value in zip(ids, success_posterior)
            },
            failure_posterior={
                evidence_id: value
                for evidence_id, value in zip(ids, failure_posterior)
            },
        )

    def recommend(
        self,
        *,
        action_type: str,
        strategy_key: str,
    ) -> CausalExperimentRecommendation:
        key = (action_type, strategy_key)
        model = self.causal_credit.models.get(key)
        if model is None:
            raise ValueError("no registered causal model for action/strategy")
        if model.model_id in self.causal_credit.pending:
            raise ValueError("settle the pending causal prediction before experiment selection")

        posterior = self.causal_credit.posterior(action_type, strategy_key)
        scores = tuple(
            self.score_intervention(
                model=model,
                posterior=posterior,
                intervention=intervention,
            )
            for intervention in self._interventions(model)
        )
        maximum = max(score.information_gain_bits for score in scores)
        best = tuple(
            score.intervention
            for score in scores
            if math.isclose(
                score.information_gain_bits,
                maximum,
                abs_tol=self.policy.tie_tolerance_bits,
                rel_tol=0.0,
            )
        )

        if maximum < self.policy.minimum_information_gain_bits:
            status = "uninformative"
            selected = None
            tied = tuple(score.intervention for score in scores)
        elif len(best) != 1:
            status = "ambiguous_best"
            selected = None
            tied = best
        else:
            status = "informative"
            selected = best[0]
            tied = best

        candidate_glyphs = []
        candidate_ids = {h.belief_evidence_id for h in model.hypotheses}
        for fact in self.causal_credit.core.memory.query():
            if fact.evidence_id in candidate_ids:
                candidate_glyphs.append(
                    self.causal_credit.core.ensure_fact_glyph(fact).glyph_id
                )

        glyph = self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "causal_experiment_recommendation",
                "model_id": model.model_id,
                "action_type": action_type,
                "strategy_key": strategy_key,
                "status": status,
                "selected_intervention": selected,
                "tied_interventions": list(tied),
                "current_posterior": dict(posterior),
                "scores": [asdict(score) for score in scores],
                "causal_validity": "conditional_on_registered_models",
                "authorization_effect": "none",
            },
            derived_from=tuple(candidate_glyphs),
        )

        return CausalExperimentRecommendation(
            model_id=model.model_id,
            action_type=action_type,
            strategy_key=strategy_key,
            status=status,
            selected_intervention=selected,
            tied_interventions=tied,
            scores=scores,
            current_posterior=dict(posterior),
            recommendation_glyph_id=glyph.glyph_id,
        )
