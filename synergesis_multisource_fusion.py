"""Independence-aware multisource perception fusion for Synergesis.

This module distinguishes:
- source count;
- independence groups;
- origin authority;
- configured / empirically calibrated reliability;
- evidential support;
- truth.

Authority is used only for eligibility. It never becomes truth weight.
Sources in the same independence group contribute at most one unit of support.
Empirical reliability can only be updated from separately-originated reference
adjudications that meet an explicit AEGIS origin-rank threshold.

Fusion produces an auditable support inference, not a truth probability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_perception_bus import PerceptionRecord
from synergesis_roam_attention import (
    AttentionMeasurements,
    ResearchAgenda,
    ResearchNeed,
)


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


def _value(value: Any) -> str:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("fusion claim value cannot be empty")
        return value
    return _canonical(value)


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except Exception as exc:
        raise ValueError("captured_at must be a valid ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("captured_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class FusionSourceProfile:
    source_id: str
    independence_group: str
    configured_reliability: float

    def __post_init__(self):
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not self.independence_group.strip():
            raise ValueError("independence_group is required")
        if (
            isinstance(self.configured_reliability, bool)
            or not isinstance(self.configured_reliability, (int, float))
            or not math.isfinite(float(self.configured_reliability))
            or not 0.0 <= float(self.configured_reliability) <= 1.0
        ):
            raise ValueError("configured_reliability must be in [0,1]")


@dataclass(frozen=True)
class FusionPolicy:
    observation_kind: str
    subject_fact: str
    object_fact: str
    minimum_origin_rank: int
    max_time_span_seconds: float
    minimum_independent_groups: int
    minimum_support: float
    minimum_support_margin: float
    reliability_prior_alpha: float = 1.0
    reliability_prior_beta: float = 1.0
    minimum_reliability_observations: int = 3
    minimum_adjudication_origin_rank: int = 5
    research_on_unresolved: bool = False
    research_domain: Optional[str] = None
    research_question_template: Optional[str] = None
    research_measurements: Optional[AttentionMeasurements] = None

    def __post_init__(self):
        for name, value in (
            ("observation_kind", self.observation_kind),
            ("subject_fact", self.subject_fact),
            ("object_fact", self.object_fact),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if (
            isinstance(self.minimum_origin_rank, bool)
            or not isinstance(self.minimum_origin_rank, int)
            or self.minimum_origin_rank < 0
        ):
            raise ValueError("minimum_origin_rank must be an integer >= 0")
        if (
            isinstance(self.max_time_span_seconds, bool)
            or not isinstance(self.max_time_span_seconds, (int, float))
            or not math.isfinite(float(self.max_time_span_seconds))
            or float(self.max_time_span_seconds) < 0
        ):
            raise ValueError("max_time_span_seconds must be finite and >= 0")
        if (
            isinstance(self.minimum_independent_groups, bool)
            or not isinstance(self.minimum_independent_groups, int)
            or self.minimum_independent_groups < 1
        ):
            raise ValueError("minimum_independent_groups must be an integer >= 1")
        for name, value in (
            ("minimum_support", self.minimum_support),
            ("minimum_support_margin", self.minimum_support_margin),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        for name, value in (
            ("reliability_prior_alpha", self.reliability_prior_alpha),
            ("reliability_prior_beta", self.reliability_prior_beta),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0
            ):
                raise ValueError(f"{name} must be finite and > 0")
        if (
            isinstance(self.minimum_reliability_observations, bool)
            or not isinstance(self.minimum_reliability_observations, int)
            or self.minimum_reliability_observations < 1
        ):
            raise ValueError(
                "minimum_reliability_observations must be an integer >= 1"
            )
        if (
            isinstance(self.minimum_adjudication_origin_rank, bool)
            or not isinstance(self.minimum_adjudication_origin_rank, int)
            or self.minimum_adjudication_origin_rank < 0
        ):
            raise ValueError(
                "minimum_adjudication_origin_rank must be an integer >= 0"
            )
        if self.research_on_unresolved:
            if not self.research_domain or not self.research_domain.strip():
                raise ValueError("research_on_unresolved requires research_domain")
            if not self.research_question_template or not self.research_question_template.strip():
                raise ValueError("research_on_unresolved requires question template")
            if self.research_measurements is None:
                raise ValueError("research_on_unresolved requires explicit measurements")


@dataclass(frozen=True)
class ReliabilityRecord:
    sequence: int
    source_id: str
    percept_digest: str
    normalized_glyph_id: str
    adjudication_glyph_id: str
    correct: bool
    previous_digest: Optional[str]
    digest: str


@dataclass(frozen=True)
class ReliabilityEstimate:
    source_id: str
    observations: int
    posterior_mean: Optional[float]
    configured_reliability: float
    effective_reliability: float
    source: str


class PerceptionReliabilityLedger:
    """Append-only hash chain of trusted source-correctness adjudications."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[ReliabilityRecord] = []
        self._loaded_size: Optional[int] = None

    def _size(self) -> Optional[int]:
        return self.path.stat().st_size if self.path.exists() else None

    def _load(self, *, force: bool = False) -> None:
        size = self._size()
        if not force and size == self._loaded_size:
            return
        records: list[ReliabilityRecord] = []
        previous = None
        if self.path.exists():
            for index, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                record = ReliabilityRecord(**json.loads(line))
                if record.sequence != index:
                    raise ValueError("perception reliability ledger sequence failure")
                if record.previous_digest != previous:
                    raise ValueError("perception reliability ledger chain failure")
                body = {
                    "sequence": record.sequence,
                    "source_id": record.source_id,
                    "percept_digest": record.percept_digest,
                    "normalized_glyph_id": record.normalized_glyph_id,
                    "adjudication_glyph_id": record.adjudication_glyph_id,
                    "correct": record.correct,
                    "previous_digest": record.previous_digest,
                }
                if record.digest != _digest(body):
                    raise ValueError("perception reliability ledger integrity failure")
                records.append(record)
                previous = record.digest
        self._records = records
        self._loaded_size = self._size()

    def records(self, *, source_id: Optional[str] = None) -> Tuple[ReliabilityRecord, ...]:
        self._load()
        out = self._records
        if source_id is not None:
            out = [record for record in out if record.source_id == source_id]
        return tuple(out)

    def append(
        self,
        *,
        source_id: str,
        percept_digest: str,
        normalized_glyph_id: str,
        adjudication_glyph_id: str,
        correct: bool,
    ) -> ReliabilityRecord:
        self._load()
        matches = [
            record
            for record in self._records
            if record.adjudication_glyph_id == adjudication_glyph_id
        ]
        if matches:
            if len(matches) != 1:
                raise ValueError("duplicated adjudication in reliability ledger")
            return matches[0]
        previous = self._records[-1].digest if self._records else None
        body = {
            "sequence": len(self._records) + 1,
            "source_id": source_id,
            "percept_digest": percept_digest,
            "normalized_glyph_id": normalized_glyph_id,
            "adjudication_glyph_id": adjudication_glyph_id,
            "correct": bool(correct),
            "previous_digest": previous,
        }
        record = ReliabilityRecord(**body, digest=_digest(body))
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


@dataclass(frozen=True)
class SourceContribution:
    source_id: str
    independence_group: str
    origin_rank: int
    claim: str
    reliability: float
    reliability_source: str
    eligible: bool
    reason: str


@dataclass(frozen=True)
class IndependenceContribution:
    independence_group: str
    claim: Optional[str]
    support: float
    source_ids: Tuple[str, ...]
    status: str


@dataclass(frozen=True)
class FusionDecision:
    fusion_id: str
    observation_kind: str
    subject: str
    status: str
    reason: str
    selected_claim: Optional[str]
    winner_support: Optional[float]
    support_margin: Optional[float]
    independent_groups_supporting_winner: int
    support_by_claim: Mapping[str, float]
    source_contributions: Tuple[SourceContribution, ...]
    group_contributions: Tuple[IndependenceContribution, ...]
    inference_glyph_id: str
    research_need_id: Optional[str]
    evidence_id: Optional[str] = None
    evidence_glyph_id: Optional[str] = None

    def __post_init__(self):
        if self.status not in {"resolved", "unresolved"}:
            raise ValueError("fusion status must be resolved or unresolved")
        if self.status == "resolved" and self.selected_claim is None:
            raise ValueError("resolved fusion requires selected_claim")
        if self.status == "unresolved" and self.selected_claim is not None:
            raise ValueError("unresolved fusion cannot select claim")


class MultisourcePerceptionFusion:
    actor = "SYN-MULTISOURCE-FUSION"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        security_graph: AegisSecurityGraph,
        profiles: Sequence[FusionSourceProfile],
        policy: FusionPolicy,
        reliability_ledger: PerceptionReliabilityLedger,
        agenda: Optional[ResearchAgenda] = None,
        aura: Optional[GlyphAuditedAura] = None,
    ):
        if security_graph.graph is not graph:
            raise ValueError("fusion security graph must share Glyph graph")
        if policy.research_on_unresolved:
            if agenda is None or agenda.graph is not graph:
                raise ValueError("fusion unresolved research requires shared agenda")
        mapping: dict[str, FusionSourceProfile] = {}
        for profile in profiles:
            if profile.source_id in mapping:
                raise ValueError("duplicate fusion source profile")
            mapping[profile.source_id] = profile
        if not mapping:
            raise ValueError("at least one fusion source profile is required")
        self.graph = graph
        self.security_graph = security_graph
        self.profiles = mapping
        self.policy = policy
        self.reliability_ledger = reliability_ledger
        self.agenda = agenda
        self.aura = aura
        self._decision_sinks = []
        if aura is not None and aura.graph is not graph:
            raise ValueError("fusion aura must share Glyph graph")

    def add_decision_sink(self, sink):
        if sink.graph is not self.graph:
            raise ValueError("fusion sink must share its audit graph")
        if sink not in self._decision_sinks:
            self._decision_sinks.append(sink)

    def reliability(self, source_id: str) -> ReliabilityEstimate:
        profile = self.profiles.get(source_id)
        if profile is None:
            raise ValueError("unknown fusion source profile")
        records = self.reliability_ledger.records(source_id=source_id)
        if len(records) < self.policy.minimum_reliability_observations:
            return ReliabilityEstimate(
                source_id=source_id,
                observations=len(records),
                posterior_mean=None,
                configured_reliability=profile.configured_reliability,
                effective_reliability=profile.configured_reliability,
                source="configured",
            )
        correct = sum(1 for record in records if record.correct)
        incorrect = len(records) - correct
        alpha = self.policy.reliability_prior_alpha + correct
        beta = self.policy.reliability_prior_beta + incorrect
        mean = alpha / (alpha + beta)
        return ReliabilityEstimate(
            source_id=source_id,
            observations=len(records),
            posterior_mean=mean,
            configured_reliability=profile.configured_reliability,
            effective_reliability=mean,
            source="empirical",
        )

    def adjudicate(
        self,
        *,
        record: PerceptionRecord,
        adjudication_glyph_id: str,
    ) -> ReliabilityRecord:
        normalized = self.graph.ledger.get(record.normalized_glyph_id)
        if (
            normalized.glyph_type != "observation"
            or normalized.content.get("kind") != "normalized_perception"
            or normalized.content.get("source_id") != record.source_id
            or normalized.content.get("percept_digest") != record.percept_digest
        ):
            raise ValueError("adjudicated perception record is invalid")

        adjudication = self.graph.ledger.get(adjudication_glyph_id)
        content = adjudication.content
        if (
            adjudication.glyph_type != "observation"
            or content.get("kind") != "perception_reference_adjudication"
            or content.get("normalized_glyph_id") != record.normalized_glyph_id
            or type(content.get("correct")) is not bool
        ):
            raise ValueError("invalid perception reference adjudication")

        binding = self.security_graph.origin_binding(adjudication.glyph_id)
        if binding is None:
            raise ValueError("perception adjudication has no bound origin")
        rank = int(binding.content["rank"])
        if rank < self.policy.minimum_adjudication_origin_rank:
            raise ValueError("perception adjudication origin rank below policy minimum")

        evaluates = any(
            edge.source == adjudication.glyph_id
            and edge.target == normalized.glyph_id
            and edge.relation == "evaluates"
            for edge in self.graph.ledger.edges_from(adjudication.glyph_id)
        )
        if not evaluates:
            raise ValueError("perception adjudication is not linked to target percept")

        record_out = self.reliability_ledger.append(
            source_id=record.source_id,
            percept_digest=record.percept_digest,
            normalized_glyph_id=record.normalized_glyph_id,
            adjudication_glyph_id=adjudication.glyph_id,
            correct=bool(content["correct"]),
        )
        self.graph.create(
            "learning",
            actor=self.actor,
            content={
                "kind": "perception_source_reliability_update",
                "source_id": record.source_id,
                "correct": bool(content["correct"]),
                "sequence": record_out.sequence,
                "authorization_effect": "none",
            },
            external_refs=(f"perception-reliability:{adjudication.glyph_id}",),
            derived_from=(
                normalized.glyph_id,
                adjudication.glyph_id,
            ),
            dedupe_external_ref=f"perception-reliability:{adjudication.glyph_id}",
        )
        return record_out

    def _record_details(self, record: PerceptionRecord):
        normalized = self.graph.ledger.get(record.normalized_glyph_id)
        raw = self.graph.ledger.get(record.raw_glyph_id)
        content = normalized.content
        if (
            normalized.glyph_type != "observation"
            or content.get("kind") != "normalized_perception"
            or content.get("source_id") != record.source_id
            or content.get("modality") != record.modality
            or content.get("percept_digest") != record.percept_digest
        ):
            raise ValueError("fusion perception record does not match normalized glyph")
        if raw.content.get("kind") != "raw_percept":
            raise ValueError("fusion perception record raw glyph is invalid")
        if not any(
            edge.source == normalized.glyph_id
            and edge.target == raw.glyph_id
            and edge.relation == "derived_from"
            for edge in self.graph.ledger.edges_from(normalized.glyph_id)
        ):
            raise ValueError("normalized percept is not derived from supplied raw percept")
        if content.get("observation_kind") != self.policy.observation_kind:
            raise ValueError("fusion observations must share configured observation kind")
        facts = content.get("facts")
        if not isinstance(facts, Mapping):
            raise ValueError("fusion normalized facts must be a mapping")
        for key in (self.policy.subject_fact, self.policy.object_fact):
            if key not in facts:
                raise ValueError(f"fusion percept missing required fact: {key}")

        binding = self.security_graph.origin_binding(raw.glyph_id)
        rank = (
            int(binding.content["rank"])
            if binding is not None
            else 0
        )
        profile = self.profiles.get(record.source_id)
        if profile is None:
            return normalized, content, facts, rank, None
        return normalized, content, facts, rank, profile

    def fuse(self, records: Sequence[PerceptionRecord]) -> FusionDecision:
        if not records:
            raise ValueError("fusion requires at least one perception record")

        subjects = set()
        times = []
        contributions: list[SourceContribution] = []
        for record in records:
            normalized, content, facts, rank, profile = self._record_details(record)
            subject = _value(facts[self.policy.subject_fact])
            claim = _value(facts[self.policy.object_fact])
            subjects.add(subject)
            captured = _time(str(content["captured_at"]))
            times.append(captured)

            if profile is None:
                contributions.append(
                    SourceContribution(
                        source_id=record.source_id,
                        independence_group="<unprofiled>",
                        origin_rank=rank,
                        claim=claim,
                        reliability=0.0,
                        reliability_source="unavailable",
                        eligible=False,
                        reason="missing_source_profile",
                    )
                )
                continue

            estimate = self.reliability(record.source_id)
            eligible = rank >= self.policy.minimum_origin_rank
            reason = "eligible" if eligible else "origin_rank_below_minimum"
            contribution = SourceContribution(
                source_id=record.source_id,
                independence_group=profile.independence_group,
                origin_rank=rank,
                claim=claim,
                reliability=estimate.effective_reliability,
                reliability_source=estimate.source,
                eligible=eligible,
                reason=reason,
            )
            contributions.append(contribution)

        if len(subjects) != 1:
            raise ValueError("fusion records must refer to the same subject")
        subject = next(iter(subjects))
        time_span_exceeded = (
            max(times) - min(times)
            > timedelta(seconds=self.policy.max_time_span_seconds)
        )

        eligible_by_group: dict[str, list[SourceContribution]] = {}
        for contribution in contributions:
            if contribution.eligible:
                eligible_by_group.setdefault(
                    contribution.independence_group,
                    [],
                ).append(contribution)

        group_contributions: list[IndependenceContribution] = []
        for group, items in sorted(eligible_by_group.items()):
            claims = {item.claim for item in items}
            if len(claims) != 1:
                group_contributions.append(
                    IndependenceContribution(
                        independence_group=group,
                        claim=None,
                        support=0.0,
                        source_ids=tuple(sorted(item.source_id for item in items)),
                        status="internal_conflict",
                    )
                )
                continue
            claim = next(iter(claims))
            group_contributions.append(
                IndependenceContribution(
                    independence_group=group,
                    claim=claim,
                    support=max(item.reliability for item in items),
                    source_ids=tuple(sorted(item.source_id for item in items)),
                    status="supporting",
                )
            )

        support_by_claim: dict[str, float] = {}
        groups_by_claim: dict[str, int] = {}
        for group in group_contributions:
            if group.status != "supporting" or group.claim is None:
                continue
            support_by_claim[group.claim] = (
                support_by_claim.get(group.claim, 0.0) + group.support
            )
            groups_by_claim[group.claim] = groups_by_claim.get(group.claim, 0) + 1

        selected = None
        status = "unresolved"
        winner_support = None
        margin = None
        winner_groups = 0

        if time_span_exceeded:
            resolution_reason = "time_span_exceeds_policy"
        elif not support_by_claim:
            resolution_reason = "no_eligible_independent_support"
        else:
            ordered = sorted(
                support_by_claim.items(),
                key=lambda item: (-item[1], item[0]),
            )
            winner, top = ordered[0]
            second = ordered[1][1] if len(ordered) > 1 else 0.0
            winner_support = top
            margin = top - second
            winner_groups = groups_by_claim[winner]

            tied = (
                len(ordered) > 1
                and math.isclose(top, second, abs_tol=1e-12, rel_tol=0.0)
            )
            if tied:
                resolution_reason = "support_tie"
            elif winner_groups < self.policy.minimum_independent_groups:
                resolution_reason = "insufficient_independent_groups"
            elif top < self.policy.minimum_support:
                resolution_reason = "insufficient_support"
            elif margin < self.policy.minimum_support_margin:
                resolution_reason = "insufficient_support_margin"
            else:
                status = "resolved"
                selected = winner
                resolution_reason = "support_thresholds_satisfied"

        parents = tuple(
            record.normalized_glyph_id
            for record in records
        )
        fusion_payload = {
            "kind": "multisource_perception_fusion",
            "observation_kind": self.policy.observation_kind,
            "subject": subject,
            "status": status,
            "reason": resolution_reason,
            "selected_claim": selected,
            "winner_support": winner_support,
            "support_margin": margin,
            "independent_groups_supporting_winner": winner_groups,
            "support_by_claim": dict(sorted(support_by_claim.items())),
            "source_contributions": [asdict(item) for item in contributions],
            "group_contributions": [asdict(item) for item in group_contributions],
            "authority_semantics": "eligibility_only",
            "support_semantics": "weighted_independent_support_not_truth_probability",
            "source_count_is_not_independence": True,
            "authorization_effect": "none",
        }
        fusion_id = "fusion:" + _digest(
            {
                "parents": list(parents),
                "payload": fusion_payload,
            }
        )[:32]
        inference = self.graph.create(
            "inference",
            actor=self.actor,
            content={
                **fusion_payload,
                "fusion_id": fusion_id,
            },
            external_refs=(fusion_id,),
            derived_from=parents,
            dedupe_external_ref=fusion_id,
        )

        evidence_id = None
        evidence_glyph_id = None
        if self.aura is not None:
            evidence = self.aura.research.ingest(
                source="multisource-perception-fusion",
                title=(
                    f"Multisource fusion: {self.policy.observation_kind} "
                    f"for {subject}"
                ),
                content=_canonical(
                    {
                        "fusion_id": fusion_id,
                        "status": status,
                        "reason": resolution_reason,
                        "subject": subject,
                        "selected_claim": selected,
                        "support_by_claim": dict(sorted(support_by_claim.items())),
                        "winner_support": winner_support,
                        "support_margin": margin,
                        "support_semantics": (
                            "weighted_independent_support_not_truth_probability"
                        ),
                    }
                ),
                source_type="perception_fusion",
            )
            matches = self.graph.ledger.find_by_external_ref(
                evidence.evidence_id,
                glyph_type="evidence",
            )
            if not matches:
                raise ValueError("fusion evidence glyph was not created")
            evidence_glyph = matches[-1]
            if not any(
                edge.source == evidence_glyph.glyph_id
                and edge.target == inference.glyph_id
                and edge.relation == "derived_from"
                for edge in self.graph.ledger.edges_from(evidence_glyph.glyph_id)
            ):
                self.graph.relate(
                    evidence_glyph.glyph_id,
                    inference.glyph_id,
                    "derived_from",
                    actor=self.actor,
                )
            evidence_id = evidence.evidence_id
            evidence_glyph_id = evidence_glyph.glyph_id

        need_id = None
        if status == "unresolved" and self.policy.research_on_unresolved:
            assert self.agenda is not None
            assert self.policy.research_domain is not None
            assert self.policy.research_question_template is not None
            assert self.policy.research_measurements is not None
            need = ResearchNeed.create(
                domain=self.policy.research_domain,
                question=self.policy.research_question_template.format(
                    subject=subject,
                    claims=" | ".join(sorted(support_by_claim)) or "none",
                    reason=resolution_reason,
                ),
                reason=(
                    "Independent-source fusion could not resolve the claim "
                    f"without exceeding configured epistemic assumptions: "
                    f"{resolution_reason}."
                ),
                measurements=self.policy.research_measurements,
                source_glyph_ids=(inference.glyph_id,),
            )
            need_id = self.agenda.add(need).need.need_id

        decision = FusionDecision(
            fusion_id=fusion_id,
            observation_kind=self.policy.observation_kind,
            subject=subject,
            status=status,
            reason=resolution_reason,
            selected_claim=selected,
            winner_support=winner_support,
            support_margin=margin,
            independent_groups_supporting_winner=winner_groups,
            support_by_claim=dict(sorted(support_by_claim.items())),
            source_contributions=tuple(contributions),
            group_contributions=tuple(group_contributions),
            inference_glyph_id=inference.glyph_id,
            research_need_id=need_id,
            evidence_id=evidence_id,
            evidence_glyph_id=evidence_glyph_id,
        )

        for sink in tuple(self._decision_sinks):
            sink.on_fusion(decision)
        return decision
