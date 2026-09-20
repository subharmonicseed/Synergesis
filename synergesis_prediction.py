"""SYN-PREDICT: explicit pre-action predictions and empirical prediction error.

This module separates two questions that must not be conflated:

1. Did the action actually succeed?
2. Did Syn correctly predict what would happen?

Predictions are structured, recorded *before* executor dispatch, and scored only
against independent SYN-REALITY observations.

The primary binary proper scoring rule is the Brier score:
    BS = (p - o)^2
where p is the predicted probability of the intended effect and o is the
independently observed binary effect.

The empirical provider uses a recency-weighted Beta-Bernoulli estimator. It can
adapt its expectations from verified outcomes but has no access to permissions,
capabilities, or executor control.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_agent_loop_v2 import ActionProposal, AgentContext
from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_reality import RealityAssessment


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
class ActionPrediction:
    prediction_id: str
    proposal_id: str
    action_type: str
    strategy_key: str
    probability_effect_success: float
    basis: Mapping[str, Any]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        proposal: ActionProposal,
        probability_effect_success: float,
        basis: Mapping[str, Any],
    ) -> "ActionPrediction":
        p = float(probability_effect_success)
        if not math.isfinite(p) or not 0.0 <= p <= 1.0:
            raise ValueError("prediction probability must be finite and in [0,1]")
        created_at = _now()
        body = {
            "proposal_id": proposal.proposal_id,
            "action_type": proposal.action_type,
            "strategy_key": proposal.strategy_key,
            "probability_effect_success": p,
            "basis": dict(basis),
            "created_at": created_at,
        }
        return cls(
            prediction_id=f"pred:{_digest(body)[:32]}",
            proposal_id=proposal.proposal_id,
            action_type=proposal.action_type,
            strategy_key=proposal.strategy_key,
            probability_effect_success=p,
            basis=dict(basis),
            created_at=created_at,
        )


class PredictionProvider(Protocol):
    def predict(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
    ) -> ActionPrediction:
        ...


class PredictionSettlementSink(Protocol):
    def on_prediction_settlement(
        self,
        settlement: "PredictionSettlement",
    ) -> None:
        ...


@dataclass(frozen=True)
class PredictionSettlement:
    prediction_id: str
    proposal_id: str
    action_type: str
    strategy_key: str
    probability_effect_success: float
    observed_effect: Optional[bool]
    status: str
    brier_score: Optional[float]
    absolute_error: Optional[float]
    surprise_bits: Optional[float]
    reality_verdict_glyph_id: str
    prediction_glyph_id: str
    learning_glyph_id: str
    settled_at: str

    def __post_init__(self):
        if self.status not in {"scored", "unscored"}:
            raise ValueError("prediction settlement status must be scored or unscored")


@dataclass(frozen=True)
class PredictionRecord:
    sequence: int
    prediction_id: str
    proposal_id: str
    action_type: str
    strategy_key: str
    probability_effect_success: float
    observed_effect: bool
    brier_score: float
    absolute_error: float
    surprise_bits: float
    settled_at: str
    previous_digest: Optional[str]
    digest: str


@dataclass(frozen=True)
class PredictionStats:
    action_type: str
    strategy_key: Optional[str]
    observations: int
    empirical_success_rate: Optional[float]
    mean_predicted_probability: Optional[float]
    mean_brier_score: Optional[float]
    mean_absolute_error: Optional[float]
    calibration_gap: Optional[float]


class PredictionLedger:
    """Hash-chained append-only settlement ledger with incremental cache."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._loaded_size: Optional[int] = None
        self._records: list[PredictionRecord] = []

    def _size(self) -> Optional[int]:
        return self.path.stat().st_size if self.path.exists() else None

    def _load(self, *, force: bool = False) -> None:
        size = self._size()
        if not force and size == self._loaded_size:
            return
        records: list[PredictionRecord] = []
        previous = None
        if self.path.exists():
            for index, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                raw = json.loads(line)
                record = PredictionRecord(**raw)
                if record.sequence != index:
                    raise ValueError("prediction ledger sequence failure")
                if record.previous_digest != previous:
                    raise ValueError("prediction ledger chain failure")
                body = {
                    "sequence": record.sequence,
                    "prediction_id": record.prediction_id,
                    "proposal_id": record.proposal_id,
                    "action_type": record.action_type,
                    "strategy_key": record.strategy_key,
                    "probability_effect_success": record.probability_effect_success,
                    "observed_effect": record.observed_effect,
                    "brier_score": record.brier_score,
                    "absolute_error": record.absolute_error,
                    "surprise_bits": record.surprise_bits,
                    "settled_at": record.settled_at,
                    "previous_digest": record.previous_digest,
                }
                expected = _digest(body)
                if record.digest != expected:
                    raise ValueError("prediction ledger integrity failure")
                records.append(record)
                previous = record.digest
        self._records = records
        self._loaded_size = self._size()

    def records(
        self,
        *,
        action_type: Optional[str] = None,
        strategy_key: Optional[str] = None,
    ) -> Tuple[PredictionRecord, ...]:
        self._load()
        values = self._records
        if action_type is not None:
            values = [r for r in values if r.action_type == action_type]
        if strategy_key is not None:
            values = [r for r in values if r.strategy_key == strategy_key]
        return tuple(values)

    def append(self, settlement: PredictionSettlement) -> PredictionRecord:
        if settlement.status != "scored" or settlement.observed_effect is None:
            raise ValueError("only scored prediction settlements enter the ledger")
        assert settlement.brier_score is not None
        assert settlement.absolute_error is not None
        assert settlement.surprise_bits is not None

        self._load()
        previous = self._records[-1].digest if self._records else None
        body = {
            "sequence": len(self._records) + 1,
            "prediction_id": settlement.prediction_id,
            "proposal_id": settlement.proposal_id,
            "action_type": settlement.action_type,
            "strategy_key": settlement.strategy_key,
            "probability_effect_success": settlement.probability_effect_success,
            "observed_effect": bool(settlement.observed_effect),
            "brier_score": float(settlement.brier_score),
            "absolute_error": float(settlement.absolute_error),
            "surprise_bits": float(settlement.surprise_bits),
            "settled_at": settlement.settled_at,
            "previous_digest": previous,
        }
        record = PredictionRecord(
            **body,
            digest=_digest(body),
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(asdict(record)) + "\n")
        self._records.append(record)
        self._loaded_size = self._size()
        return record

    def verify(self) -> Tuple[int, Optional[str]]:
        self._load(force=True)
        return (
            len(self._records),
            self._records[-1].digest if self._records else None,
        )

    def stats(
        self,
        *,
        action_type: str,
        strategy_key: Optional[str] = None,
    ) -> PredictionStats:
        records = self.records(
            action_type=action_type,
            strategy_key=strategy_key,
        )
        if not records:
            return PredictionStats(
                action_type,
                strategy_key,
                0,
                None,
                None,
                None,
                None,
                None,
            )
        n = len(records)
        success_rate = sum(1.0 if r.observed_effect else 0.0 for r in records) / n
        mean_p = sum(r.probability_effect_success for r in records) / n
        mean_brier = sum(r.brier_score for r in records) / n
        mean_abs = sum(r.absolute_error for r in records) / n
        return PredictionStats(
            action_type=action_type,
            strategy_key=strategy_key,
            observations=n,
            empirical_success_rate=success_rate,
            mean_predicted_probability=mean_p,
            mean_brier_score=mean_brier,
            mean_absolute_error=mean_abs,
            calibration_gap=mean_p - success_rate,
        )


class StaticPredictionProvider:
    def __init__(self, probability_effect_success: float):
        p = float(probability_effect_success)
        if not math.isfinite(p) or not 0.0 <= p <= 1.0:
            raise ValueError("static prediction probability must be in [0,1]")
        self.probability = p

    def predict(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
    ) -> ActionPrediction:
        return ActionPrediction.create(
            proposal=proposal,
            probability_effect_success=self.probability,
            basis={
                "kind": "static_test_prediction",
                "note": "fixed probability; no empirical adaptation",
            },
        )


class EmpiricalPredictionProvider:
    """Recency-weighted empirical estimator over verified outcomes."""

    def __init__(
        self,
        *,
        ledger: PredictionLedger,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        half_life_events: float = 16.0,
    ):
        for name, value in (
            ("prior_alpha", prior_alpha),
            ("prior_beta", prior_beta),
            ("half_life_events", half_life_events),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
        self.ledger = ledger
        self.prior_alpha = float(prior_alpha)
        self.prior_beta = float(prior_beta)
        self.half_life_events = float(half_life_events)

    def _estimate(
        self,
        records: Sequence[PredictionRecord],
        *,
        current_sequence: int,
    ) -> tuple[float, float, float]:
        weighted_success = 0.0
        weighted_failure = 0.0
        for record in records:
            age = max(0, current_sequence - record.sequence)
            weight = 0.5 ** (age / self.half_life_events)
            if record.observed_effect:
                weighted_success += weight
            else:
                weighted_failure += weight
        alpha = self.prior_alpha + weighted_success
        beta = self.prior_beta + weighted_failure
        return alpha / (alpha + beta), weighted_success, weighted_failure

    def predict(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
    ) -> ActionPrediction:
        all_records = self.ledger.records()
        strategy_records = tuple(
            r for r in all_records
            if (
                r.action_type == proposal.action_type
                and r.strategy_key == proposal.strategy_key
            )
        )
        if strategy_records:
            scope = "action_and_strategy"
            records = strategy_records
        else:
            action_records = tuple(
                r for r in all_records
                if r.action_type == proposal.action_type
            )
            scope = "action_fallback" if action_records else "prior"
            records = action_records

        p, weighted_success, weighted_failure = self._estimate(
            records,
            current_sequence=len(all_records) + 1,
        )
        return ActionPrediction.create(
            proposal=proposal,
            probability_effect_success=p,
            basis={
                "kind": "recency_weighted_beta_bernoulli",
                "scope": scope,
                "matching_observations": len(records),
                "weighted_success": weighted_success,
                "weighted_failure": weighted_failure,
                "prior_alpha": self.prior_alpha,
                "prior_beta": self.prior_beta,
                "half_life_events": self.half_life_events,
            },
        )


class PredictionEngine:
    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        provider: PredictionProvider,
        ledger: PredictionLedger,
        settlement_sinks: Sequence[PredictionSettlementSink] = (),
        actor: str = "SYN-PREDICT",
    ):
        self.graph = graph
        self.provider = provider
        self.ledger = ledger
        self.actor = actor
        self._predictions: dict[str, ActionPrediction] = {}
        self._prediction_glyph_ids: dict[str, str] = {}
        self._settlements: dict[str, PredictionSettlement] = {}
        self._settlement_sinks: list[PredictionSettlementSink] = list(
            settlement_sinks
        )

    def add_settlement_sink(
        self,
        sink: PredictionSettlementSink,
    ) -> None:
        if sink not in self._settlement_sinks:
            self._settlement_sinks.append(sink)

    def predict_before_action(
        self,
        *,
        context: AgentContext,
        proposal: ActionProposal,
        action_glyph_id: str,
    ) -> ActionPrediction:
        prediction = self.provider.predict(
            context=context,
            proposal=proposal,
        )
        if prediction.proposal_id != proposal.proposal_id:
            raise ValueError("prediction provider returned mismatched proposal_id")
        if prediction.action_type != proposal.action_type:
            raise ValueError("prediction provider returned mismatched action_type")
        if prediction.strategy_key != proposal.strategy_key:
            raise ValueError("prediction provider returned mismatched strategy_key")

        glyph = self.graph.create(
            "hypothesis",
            actor=self.actor,
            content={
                "kind": "action_prediction",
                "prediction_id": prediction.prediction_id,
                "proposal_id": prediction.proposal_id,
                "action_type": prediction.action_type,
                "strategy_key": prediction.strategy_key,
                "target": "effect_observed",
                "probability_effect_success": (
                    prediction.probability_effect_success
                ),
                "basis": dict(prediction.basis),
                "created_at": prediction.created_at,
            },
            external_refs=(prediction.prediction_id,),
            derived_from=(action_glyph_id,),
            dedupe_external_ref=prediction.prediction_id,
        )
        self._predictions[proposal.proposal_id] = prediction
        self._prediction_glyph_ids[proposal.proposal_id] = glyph.glyph_id
        return prediction

    def settle(
        self,
        *,
        proposal: ActionProposal,
        reality: RealityAssessment,
    ) -> PredictionSettlement:
        prediction = self._predictions.get(proposal.proposal_id)
        prediction_glyph_id = self._prediction_glyph_ids.get(proposal.proposal_id)
        if prediction is None or prediction_glyph_id is None:
            raise ValueError("missing pre-action prediction")

        observed = reality.effect_observed
        if observed is None:
            brier = None
            absolute = None
            surprise = None
            status = "unscored"
        else:
            outcome = 1.0 if observed else 0.0
            p = prediction.probability_effect_success
            brier = (p - outcome) ** 2
            absolute = abs(p - outcome)
            probability_of_observed = p if observed else (1.0 - p)
            surprise = -math.log2(max(probability_of_observed, 1e-12))
            status = "scored"

        settled_at = _now()
        learning = self.graph.create(
            "learning",
            actor=self.actor,
            content={
                "kind": "prediction_error",
                "prediction_id": prediction.prediction_id,
                "proposal_id": proposal.proposal_id,
                "action_type": proposal.action_type,
                "strategy_key": proposal.strategy_key,
                "probability_effect_success": (
                    prediction.probability_effect_success
                ),
                "observed_effect": observed,
                "status": status,
                "brier_score": brier,
                "absolute_error": absolute,
                "surprise_bits": surprise,
                "settled_at": settled_at,
            },
            external_refs=(f"prediction-settlement:{prediction.prediction_id}",),
            derived_from=(
                prediction_glyph_id,
                reality.verdict_glyph_id,
            ),
        )
        self.graph.relate(
            learning.glyph_id,
            prediction_glyph_id,
            "evaluates",
            actor=self.actor,
        )

        settlement = PredictionSettlement(
            prediction_id=prediction.prediction_id,
            proposal_id=proposal.proposal_id,
            action_type=proposal.action_type,
            strategy_key=proposal.strategy_key,
            probability_effect_success=prediction.probability_effect_success,
            observed_effect=observed,
            status=status,
            brier_score=brier,
            absolute_error=absolute,
            surprise_bits=surprise,
            reality_verdict_glyph_id=reality.verdict_glyph_id,
            prediction_glyph_id=prediction_glyph_id,
            learning_glyph_id=learning.glyph_id,
            settled_at=settled_at,
        )
        self._settlements[proposal.proposal_id] = settlement
        if status == "scored":
            self.ledger.append(settlement)
        for sink in tuple(self._settlement_sinks):
            sink.on_prediction_settlement(settlement)
        return settlement

    def settlement_for(self, proposal_id: str) -> Optional[PredictionSettlement]:
        return self._settlements.get(proposal_id)


class PredictionAuditService:
    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        ledger: PredictionLedger,
    ):
        self.graph = graph
        self.ledger = ledger

    def stats(
        self,
        action_type: str,
        *,
        strategy_key: Optional[str] = None,
    ) -> PredictionStats:
        return self.ledger.stats(
            action_type=action_type,
            strategy_key=strategy_key,
        )

    def prediction_glyphs(self) -> Tuple[Any, ...]:
        return tuple(
            glyph for glyph in self.graph.ledger.glyphs()
            if (
                glyph.glyph_type == "hypothesis"
                and glyph.content.get("kind") == "action_prediction"
            )
        )

    def error_glyphs(self) -> Tuple[Any, ...]:
        return tuple(
            glyph for glyph in self.graph.ledger.glyphs()
            if (
                glyph.glyph_type == "learning"
                and glyph.content.get("kind") == "prediction_error"
            )
        )
