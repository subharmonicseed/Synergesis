"""Empirical calibration of experiment risk from independent runtime evidence.

SYN-RISK-LEARNING learns whether an intervention produced an adverse event.
It is deliberately separate from action success/failure.

Security invariant
------------------
Learning may raise the effective risk used by experiment selection, but it may
never lower the trusted configured risk floor.

    effective_risk = max(configured_risk_floor, learned_conservative_risk)

The learned estimate is therefore informative, not authoritative. Governance
thresholds and AEGIS permissions remain external and immutable to this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_prediction import PredictionSettlement


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RiskObservationContract:
    action_type: str
    strategy_key: str
    observer_id: str
    adverse_event_fact: str

    def __post_init__(self):
        for name, value in (
            ("action_type", self.action_type),
            ("strategy_key", self.strategy_key),
            ("observer_id", self.observer_id),
            ("adverse_event_fact", self.adverse_event_fact),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")


@dataclass(frozen=True)
class RiskLearningPolicy:
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    half_life_events: float = 32.0
    uncertainty_margin_weight: float = 0.5

    def __post_init__(self):
        for name, value in (
            ("prior_alpha", self.prior_alpha),
            ("prior_beta", self.prior_beta),
            ("half_life_events", self.half_life_events),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
        if (
            not math.isfinite(self.uncertainty_margin_weight)
            or self.uncertainty_margin_weight < 0
        ):
            raise ValueError(
                "uncertainty_margin_weight must be finite and >= 0"
            )


@dataclass(frozen=True)
class RiskRecord:
    sequence: int
    prediction_id: str
    proposal_id: str
    action_type: str
    strategy_key: str
    intervention: str
    adverse_event: bool
    observer_id: str
    observation_glyph_id: str
    reality_verdict_glyph_id: str
    settled_at: str
    previous_digest: Optional[str]
    digest: str


@dataclass(frozen=True)
class RiskEstimate:
    action_type: str
    strategy_key: str
    intervention: str
    observations: int
    effective_sample_size: float
    posterior_mean: Optional[float]
    conservative_risk: Optional[float]

    def __post_init__(self):
        if self.observations < 0:
            raise ValueError("observations must be >= 0")
        if self.effective_sample_size < 0:
            raise ValueError("effective_sample_size must be >= 0")
        for name, value in (
            ("posterior_mean", self.posterior_mean),
            ("conservative_risk", self.conservative_risk),
        ):
            if value is not None and (
                not math.isfinite(value) or not 0 <= value <= 1
            ):
                raise ValueError(f"{name} must be None or in [0,1]")


class RiskLedger:
    """Append-only, hash-chained record of independently observed harms."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[RiskRecord] = []
        self._loaded_size: Optional[int] = None

    def _size(self) -> Optional[int]:
        return self.path.stat().st_size if self.path.exists() else None

    def _load(self, *, force: bool = False) -> None:
        size = self._size()
        if not force and size == self._loaded_size:
            return
        records: list[RiskRecord] = []
        previous = None
        if self.path.exists():
            for index, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                raw = json.loads(line)
                record = RiskRecord(**raw)
                if record.sequence != index:
                    raise ValueError("risk ledger sequence failure")
                if record.previous_digest != previous:
                    raise ValueError("risk ledger chain failure")
                body = {
                    "sequence": record.sequence,
                    "prediction_id": record.prediction_id,
                    "proposal_id": record.proposal_id,
                    "action_type": record.action_type,
                    "strategy_key": record.strategy_key,
                    "intervention": record.intervention,
                    "adverse_event": record.adverse_event,
                    "observer_id": record.observer_id,
                    "observation_glyph_id": record.observation_glyph_id,
                    "reality_verdict_glyph_id": record.reality_verdict_glyph_id,
                    "settled_at": record.settled_at,
                    "previous_digest": record.previous_digest,
                }
                if record.digest != _digest(body):
                    raise ValueError("risk ledger integrity failure")
                records.append(record)
                previous = record.digest
        self._records = records
        self._loaded_size = self._size()

    def records(
        self,
        *,
        action_type: Optional[str] = None,
        strategy_key: Optional[str] = None,
        intervention: Optional[str] = None,
    ) -> Tuple[RiskRecord, ...]:
        self._load()
        records = self._records
        if action_type is not None:
            records = [r for r in records if r.action_type == action_type]
        if strategy_key is not None:
            records = [r for r in records if r.strategy_key == strategy_key]
        if intervention is not None:
            records = [r for r in records if r.intervention == intervention]
        return tuple(records)

    def append(
        self,
        *,
        settlement: PredictionSettlement,
        intervention: str,
        adverse_event: bool,
        observer_id: str,
        observation_glyph_id: str,
    ) -> RiskRecord:
        self._load()
        if any(r.prediction_id == settlement.prediction_id for r in self._records):
            matches = [
                r for r in self._records
                if r.prediction_id == settlement.prediction_id
            ]
            if len(matches) != 1:
                raise ValueError("duplicated prediction in risk ledger")
            return matches[0]

        previous = self._records[-1].digest if self._records else None
        body = {
            "sequence": len(self._records) + 1,
            "prediction_id": settlement.prediction_id,
            "proposal_id": settlement.proposal_id,
            "action_type": settlement.action_type,
            "strategy_key": settlement.strategy_key,
            "intervention": intervention,
            "adverse_event": bool(adverse_event),
            "observer_id": observer_id,
            "observation_glyph_id": observation_glyph_id,
            "reality_verdict_glyph_id": settlement.reality_verdict_glyph_id,
            "settled_at": settlement.settled_at,
            "previous_digest": previous,
        }
        record = RiskRecord(**body, digest=_digest(body))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(asdict(record)) + "\n")
        self._records.append(record)
        self._loaded_size = self._size()
        return record

    def verify(self) -> tuple[int, Optional[str]]:
        self._load(force=True)
        return (
            len(self._records),
            self._records[-1].digest if self._records else None,
        )


class RiskLearningEngine:
    """Prediction settlement sink + calibrated risk estimate provider."""

    actor = "SYN-RISK-LEARNING"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        ledger: RiskLedger,
        contracts: Sequence[RiskObservationContract],
        policy: RiskLearningPolicy = RiskLearningPolicy(),
    ):
        self.graph = graph
        self.ledger = ledger
        self.policy = policy
        mapping: dict[tuple[str, str], RiskObservationContract] = {}
        for contract in contracts:
            key = (contract.action_type, contract.strategy_key)
            if key in mapping:
                raise ValueError(
                    "duplicate risk observation contract for "
                    f"{contract.action_type}/{contract.strategy_key}"
                )
            mapping[key] = contract
        if not mapping:
            raise ValueError("at least one risk observation contract is required")
        self.contracts = mapping

    def _prediction_basis(
        self,
        settlement: PredictionSettlement,
    ) -> tuple[Mapping[str, Any], str]:
        prediction = self.graph.ledger.get(settlement.prediction_glyph_id)
        if (
            prediction.glyph_type != "hypothesis"
            or prediction.content.get("kind") != "action_prediction"
            or prediction.content.get("prediction_id") != settlement.prediction_id
            or prediction.content.get("proposal_id") != settlement.proposal_id
        ):
            raise ValueError("invalid risk-learning prediction provenance")
        basis = prediction.content.get("basis", {})
        if not isinstance(basis, Mapping):
            raise ValueError("prediction basis must be a mapping")
        intervention = basis.get("intervention")
        if not isinstance(intervention, str) or not intervention.strip():
            raise ValueError(
                "risk learning requires a prediction with explicit intervention"
            )
        return basis, intervention

    def _adverse_observation(
        self,
        *,
        settlement: PredictionSettlement,
        contract: RiskObservationContract,
    ) -> Optional[tuple[bool, str]]:
        verdict = self.graph.ledger.get(settlement.reality_verdict_glyph_id)
        if (
            verdict.glyph_type != "decision"
            or verdict.content.get("kind") != "reality_verdict"
            or verdict.content.get("proposal_id") != settlement.proposal_id
        ):
            raise ValueError("invalid risk-learning reality verdict")

        prediction = self.graph.ledger.get(settlement.prediction_glyph_id)
        action_ids = {
            edge.target
            for edge in self.graph.ledger.edges_from(
                prediction.glyph_id,
                relation="derived_from",
            )
        }
        values: list[tuple[bool, str]] = []
        for edge in self.graph.ledger.edges_from(
            verdict.glyph_id,
            relation="derived_from",
        ):
            observation = self.graph.ledger.get(edge.target)
            content = observation.content
            if (
                observation.glyph_type != "observation"
                or content.get("kind") != "runtime_reality_observation"
                or content.get("observer_id") != contract.observer_id
            ):
                continue

            observed_actions = {
                e.target
                for e in self.graph.ledger.edges_from(
                    observation.glyph_id,
                    relation="observes",
                )
            }
            if not action_ids.intersection(observed_actions):
                raise ValueError("risk observation belongs to another action")

            value = content.get("facts", {}).get(contract.adverse_event_fact)
            if type(value) is not bool:
                continue
            values.append((value, observation.glyph_id))

        if not values:
            return None
        bools = {value for value, _ in values}
        if len(bools) != 1:
            return None
        # Multiple consistent observations are acceptable but one concrete glyph
        # is retained as the primary evidence pointer.
        return values[0]

    def on_prediction_settlement(
        self,
        settlement: PredictionSettlement,
    ) -> None:
        contract = self.contracts.get(
            (settlement.action_type, settlement.strategy_key)
        )
        if contract is None:
            return
        if settlement.status != "scored":
            return

        _, intervention = self._prediction_basis(settlement)
        adverse = self._adverse_observation(
            settlement=settlement,
            contract=contract,
        )
        if adverse is None:
            self.graph.create(
                "learning",
                actor=self.actor,
                content={
                    "kind": "risk_calibration_outcome",
                    "prediction_id": settlement.prediction_id,
                    "action_type": settlement.action_type,
                    "strategy_key": settlement.strategy_key,
                    "intervention": intervention,
                    "status": "unverified_risk_outcome",
                    "adverse_event": None,
                    "authorization_effect": "none",
                },
                derived_from=(
                    settlement.prediction_glyph_id,
                    settlement.reality_verdict_glyph_id,
                ),
            )
            return

        adverse_event, observation_glyph_id = adverse
        record = self.ledger.append(
            settlement=settlement,
            intervention=intervention,
            adverse_event=adverse_event,
            observer_id=contract.observer_id,
            observation_glyph_id=observation_glyph_id,
        )

        self.graph.create(
            "learning",
            actor=self.actor,
            content={
                "kind": "risk_calibration_outcome",
                "prediction_id": settlement.prediction_id,
                "proposal_id": settlement.proposal_id,
                "action_type": settlement.action_type,
                "strategy_key": settlement.strategy_key,
                "intervention": intervention,
                "status": "scored",
                "adverse_event": adverse_event,
                "risk_record_sequence": record.sequence,
                "authorization_effect": "none",
            },
            external_refs=(f"risk-outcome:{settlement.prediction_id}",),
            derived_from=(
                settlement.prediction_glyph_id,
                settlement.reality_verdict_glyph_id,
                observation_glyph_id,
            ),
            dedupe_external_ref=f"risk-outcome:{settlement.prediction_id}",
        )

    def estimate(
        self,
        *,
        action_type: str,
        strategy_key: str,
        intervention: str,
    ) -> RiskEstimate:
        records = self.ledger.records(
            action_type=action_type,
            strategy_key=strategy_key,
            intervention=intervention,
        )
        if not records:
            return RiskEstimate(
                action_type=action_type,
                strategy_key=strategy_key,
                intervention=intervention,
                observations=0,
                effective_sample_size=0.0,
                posterior_mean=None,
                conservative_risk=None,
            )

        current_sequence = self.ledger.records()[-1].sequence + 1
        adverse_weight = 0.0
        safe_weight = 0.0
        total_weight = 0.0
        for record in records:
            age = max(0, current_sequence - record.sequence)
            weight = 0.5 ** (age / self.policy.half_life_events)
            total_weight += weight
            if record.adverse_event:
                adverse_weight += weight
            else:
                safe_weight += weight

        alpha = self.policy.prior_alpha + adverse_weight
        beta = self.policy.prior_beta + safe_weight
        mean = alpha / (alpha + beta)
        # A transparent conservative margin, intentionally not presented as a
        # formal confidence/credible interval.
        margin = (
            self.policy.uncertainty_margin_weight
            / math.sqrt(alpha + beta)
        )
        conservative = min(1.0, mean + margin)
        return RiskEstimate(
            action_type=action_type,
            strategy_key=strategy_key,
            intervention=intervention,
            observations=len(records),
            effective_sample_size=total_weight,
            posterior_mean=mean,
            conservative_risk=conservative,
        )
