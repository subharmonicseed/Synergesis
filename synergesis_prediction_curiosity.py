"""Prediction-error-driven curiosity bridge for Synergesis.

A large prediction error can become a bounded SYN-ROAM research need.

This bridge does not let surprise create permissions or actions. It only creates
an auditable research question in the existing ResearchAgenda.

Anti-spam controls:
- minimum verified observations;
- current-error / surprise thresholds;
- rolling Brier threshold;
- durable cooldown measured in prediction-ledger records.

All priority components are derived from explicit metrics or configured policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional, Tuple

from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_prediction import (
    PredictionLedger,
    PredictionRecord,
    PredictionSettlement,
)
from synergesis_roam_attention import (
    AttentionMeasurements,
    ResearchAgenda,
    ResearchNeed,
)


@dataclass(frozen=True)
class PredictionCuriosityPolicy:
    min_observations: int
    rolling_window: int
    minimum_absolute_error: float
    minimum_surprise_bits: float
    rolling_brier_threshold: float
    cooldown_records: int
    surprise_scale_bits: float
    default_domain: str
    default_expected_impact: float
    domain_by_action: Mapping[str, str]
    expected_impact_by_action: Mapping[str, float]

    def __post_init__(self):
        if self.min_observations < 1:
            raise ValueError("min_observations must be >= 1")
        if self.rolling_window < 1:
            raise ValueError("rolling_window must be >= 1")
        if self.cooldown_records < 0:
            raise ValueError("cooldown_records must be >= 0")
        if not self.default_domain.strip():
            raise ValueError("default_domain is required")
        for name, value in (
            ("minimum_absolute_error", self.minimum_absolute_error),
            ("rolling_brier_threshold", self.rolling_brier_threshold),
            ("default_expected_impact", self.default_expected_impact),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        if (
            not math.isfinite(self.minimum_surprise_bits)
            or self.minimum_surprise_bits < 0
        ):
            raise ValueError("minimum_surprise_bits must be finite and >= 0")
        if (
            not math.isfinite(self.surprise_scale_bits)
            or self.surprise_scale_bits <= 0
        ):
            raise ValueError("surprise_scale_bits must be finite and > 0")
        for action, domain in self.domain_by_action.items():
            if not action.strip() or not domain.strip():
                raise ValueError("domain_by_action keys/values must be non-empty")
        for action, value in self.expected_impact_by_action.items():
            if not action.strip():
                raise ValueError("expected_impact_by_action keys must be non-empty")
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("expected impact values must be in [0,1]")


@dataclass(frozen=True)
class PredictionCuriosityTrigger:
    need_id: str
    action_type: str
    strategy_key: str
    prediction_record_sequence: int
    recent_mean_brier: float
    recent_success_rate: float
    previous_success_rate: Optional[float]
    regime_shift: float


class PredictionCuriosityMonitor:
    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        prediction_ledger: PredictionLedger,
        agenda: ResearchAgenda,
        policy: PredictionCuriosityPolicy,
        actor: str = "SYN-CURIOSITY",
    ):
        self.graph = graph
        self.prediction_ledger = prediction_ledger
        self.agenda = agenda
        self.policy = policy
        self.actor = actor
        self.last_trigger: Optional[PredictionCuriosityTrigger] = None

    def _last_trigger_sequence(
        self,
        *,
        action_type: str,
        strategy_key: str,
    ) -> Optional[int]:
        sequences = []
        for glyph in self.graph.ledger.glyphs():
            if (
                glyph.glyph_type == "decision"
                and glyph.content.get("kind") == "prediction_curiosity_trigger"
                and glyph.content.get("action_type") == action_type
                and glyph.content.get("strategy_key") == strategy_key
            ):
                value = glyph.content.get("prediction_record_sequence")
                if isinstance(value, int):
                    sequences.append(value)
        return max(sequences) if sequences else None

    @staticmethod
    def _success_rate(records: Tuple[PredictionRecord, ...]) -> float:
        return (
            sum(1.0 if record.observed_effect else 0.0 for record in records)
            / len(records)
        )

    def on_prediction_settlement(
        self,
        settlement: PredictionSettlement,
    ) -> None:
        if settlement.status != "scored":
            return
        if (
            settlement.absolute_error is None
            or settlement.surprise_bits is None
        ):
            return

        records = self.prediction_ledger.records(
            action_type=settlement.action_type,
            strategy_key=settlement.strategy_key,
        )
        if len(records) < self.policy.min_observations:
            return

        recent = records[-self.policy.rolling_window:]
        recent_brier = sum(r.brier_score for r in recent) / len(recent)
        high_error = (
            settlement.absolute_error >= self.policy.minimum_absolute_error
            or settlement.surprise_bits >= self.policy.minimum_surprise_bits
            or recent_brier >= self.policy.rolling_brier_threshold
        )
        if not high_error:
            return

        sequence = records[-1].sequence
        last_sequence = self._last_trigger_sequence(
            action_type=settlement.action_type,
            strategy_key=settlement.strategy_key,
        )
        if (
            last_sequence is not None
            and sequence - last_sequence <= self.policy.cooldown_records
        ):
            return

        recent_success = self._success_rate(tuple(recent))
        previous_window = records[
            max(0, len(records) - 2 * self.policy.rolling_window):
            max(0, len(records) - self.policy.rolling_window)
        ]
        previous_success = (
            self._success_rate(tuple(previous_window))
            if previous_window
            else None
        )
        regime_shift = (
            abs(recent_success - previous_success)
            if previous_success is not None
            else 0.0
        )

        uncertainty = min(1.0, math.sqrt(max(0.0, recent_brier)))
        novelty_gap = min(
            1.0,
            settlement.surprise_bits / self.policy.surprise_scale_bits,
        )
        staleness = min(1.0, regime_shift)
        expected_impact = self.policy.expected_impact_by_action.get(
            settlement.action_type,
            self.policy.default_expected_impact,
        )
        domain = self.policy.domain_by_action.get(
            settlement.action_type,
            self.policy.default_domain,
        )

        question = (
            "What changed in the verified conditions affecting action "
            f"'{settlement.action_type}' with strategy "
            f"'{settlement.strategy_key}' such that observed outcomes are "
            "diverging from recent predictions?"
        )
        hypothesis = (
            "The operating regime changed or an unmodeled precondition is "
            "affecting the action's verified success probability."
        )
        reason = (
            "prediction_surprise: "
            f"absolute_error={settlement.absolute_error:.4f}; "
            f"surprise_bits={settlement.surprise_bits:.4f}; "
            f"recent_mean_brier={recent_brier:.4f}; "
            f"recent_success_rate={recent_success:.4f}; "
            f"regime_shift={regime_shift:.4f}"
        )

        need = ResearchNeed.create(
            domain=domain,
            question=question,
            hypothesis=hypothesis,
            reason=reason,
            source_glyph_ids=(
                settlement.learning_glyph_id,
                settlement.reality_verdict_glyph_id,
            ),
            measurements=AttentionMeasurements(
                uncertainty=uncertainty,
                expected_impact=expected_impact,
                staleness=staleness,
                novelty_gap=novelty_gap,
            ),
        )
        state = self.agenda.add(need)
        need_glyphs = self.graph.ledger.find_by_external_ref(
            need.need_id,
            glyph_type="goal",
        )
        parents = [
            settlement.learning_glyph_id,
            settlement.reality_verdict_glyph_id,
        ]
        if need_glyphs:
            parents.append(need_glyphs[-1].glyph_id)

        trigger = self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "prediction_curiosity_trigger",
                "need_id": need.need_id,
                "action_type": settlement.action_type,
                "strategy_key": settlement.strategy_key,
                "prediction_record_sequence": sequence,
                "recent_mean_brier": recent_brier,
                "recent_success_rate": recent_success,
                "previous_success_rate": previous_success,
                "regime_shift": regime_shift,
                "attention_status": state.status,
            },
            external_refs=(
                f"prediction-curiosity:{settlement.prediction_id}",
            ),
            derived_from=tuple(parents),
            dedupe_external_ref=(
                f"prediction-curiosity:{settlement.prediction_id}"
            ),
        )
        if need_glyphs:
            self.graph.relate(
                trigger.glyph_id,
                need_glyphs[-1].glyph_id,
                "motivates",
                actor=self.actor,
            )

        self.last_trigger = PredictionCuriosityTrigger(
            need_id=need.need_id,
            action_type=settlement.action_type,
            strategy_key=settlement.strategy_key,
            prediction_record_sequence=sequence,
            recent_mean_brier=recent_brier,
            recent_success_rate=recent_success,
            previous_success_rate=previous_success,
            regime_shift=regime_shift,
        )
