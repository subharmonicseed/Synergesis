"""Bridge normalized perception into evidence, world state, context and ROAM.

A normalized percept is not automatically a world fact.

Pipeline
--------
PerceptionRecord
    -> auditable Evidence
    -> optional policy-gated Fact admission
    -> explicit temporal ordering for versioned state
    -> optional contradiction artifact
    -> optional ResearchNeed for ROAM
    -> bounded context retrieval over current World Model heads + all Evidence

No action or authorization is created by this module.

Temporal semantics are explicit:
- `state_update`: a later changed value supersedes the previous state.
- `contradiction`: a later changed value is also marked as a contradiction.
- stale observations are retained as Evidence but never replace the current head.
- simultaneous incompatible observations are retained as Evidence and conflict
  artifacts, but neither is allowed to silently become the current head.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Optional, Sequence, Tuple

from synergesis_cognitive_core import Fact
from synergesis_context import ContextSelection, LexicalContextSelector
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_perception_bus import PerceptionRecord
from synergesis_roam_attention import (
    AttentionMeasurements,
    ResearchAgenda,
    ResearchNeed,
)
from synergesis_world_belief_view import VersionedBeliefView


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


def _fact_value(value: Any) -> str:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("semantic fact value cannot be empty")
        return value
    return _canonical(value)


def _parse_time(value: str, *, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except Exception as exc:
        raise ValueError(f"{name} must be a valid ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class PerceptionKnowledgeRule:
    observation_kind: str
    domain: str
    subject_fact: str
    predicate: str
    object_fact: str
    versioned: bool
    allow_world_commit: bool
    minimum_confidence: float
    change_semantics: str = "state_update"
    research_on_contradiction: bool = False
    research_question_template: Optional[str] = None
    research_measurements: Optional[AttentionMeasurements] = None

    def __post_init__(self):
        for name, value in (
            ("observation_kind", self.observation_kind),
            ("domain", self.domain),
            ("subject_fact", self.subject_fact),
            ("predicate", self.predicate),
            ("object_fact", self.object_fact),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if (
            not math.isfinite(self.minimum_confidence)
            or not 0.0 <= self.minimum_confidence <= 1.0
        ):
            raise ValueError("minimum_confidence must be in [0,1]")
        if self.change_semantics not in {"state_update", "contradiction"}:
            raise ValueError(
                "change_semantics must be 'state_update' or 'contradiction'"
            )
        if self.research_on_contradiction:
            if (
                not isinstance(self.research_question_template, str)
                or not self.research_question_template.strip()
            ):
                raise ValueError(
                    "research_on_contradiction requires question template"
                )
            if self.research_measurements is None:
                raise ValueError(
                    "research_on_contradiction requires explicit measurements"
                )


@dataclass(frozen=True)
class PerceptionKnowledgeResult:
    normalized_glyph_id: str
    evidence_id: str
    evidence_glyph_id: str
    admission_status: str
    fact_evidence_id: Optional[str]
    contradiction_glyph_id: Optional[str]
    research_need_id: Optional[str]

    def __post_init__(self):
        allowed = {
            "evidence_only",
            "confidence_unavailable",
            "confidence_below_threshold",
            "committed",
            "committed_with_contradiction",
            "stale_observation",
            "simultaneous_duplicate",
            "simultaneous_conflict",
        }
        if self.admission_status not in allowed:
            raise ValueError("invalid perception knowledge admission status")


class PerceptionKnowledgeBridge:
    actor = "SYN-PERCEPTION-KNOWLEDGE"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        core: GlyphAuditedCognitiveCore,
        aura: GlyphAuditedAura,
        world_beliefs: VersionedBeliefView,
        agenda: ResearchAgenda,
        context_selector: LexicalContextSelector,
        rules: Sequence[PerceptionKnowledgeRule],
    ):
        if core.graph is not graph or aura.graph is not graph:
            raise ValueError("perception knowledge components must share graph")
        if agenda.graph is not graph:
            raise ValueError("research agenda must share graph")
        if world_beliefs.memory is not core.memory:
            raise ValueError("world belief view must wrap cognitive memory")

        mapping: dict[str, PerceptionKnowledgeRule] = {}
        for rule in rules:
            if rule.observation_kind in mapping:
                raise ValueError("duplicate perception knowledge observation_kind")
            mapping[rule.observation_kind] = rule
        if not mapping:
            raise ValueError("at least one perception knowledge rule is required")

        self.graph = graph
        self.core = core
        self.aura = aura
        self.world_beliefs = world_beliefs
        self.agenda = agenda
        self.context_selector = context_selector
        self.rules = mapping

    def _result(
        self,
        *,
        normalized_glyph_id: str,
        evidence_id: str,
        evidence_glyph_id: str,
        status: str,
        fact_evidence_id: Optional[str] = None,
        contradiction_glyph_id: Optional[str] = None,
        research_need_id: Optional[str] = None,
    ) -> PerceptionKnowledgeResult:
        return PerceptionKnowledgeResult(
            normalized_glyph_id=normalized_glyph_id,
            evidence_id=evidence_id,
            evidence_glyph_id=evidence_glyph_id,
            admission_status=status,
            fact_evidence_id=fact_evidence_id,
            contradiction_glyph_id=contradiction_glyph_id,
            research_need_id=research_need_id,
        )

    def _normalized(self, record: PerceptionRecord):
        glyph = self.graph.ledger.get(record.normalized_glyph_id)
        content = glyph.content
        if (
            glyph.glyph_type != "observation"
            or content.get("kind") != "normalized_perception"
            or content.get("source_id") != record.source_id
            or content.get("modality") != record.modality
            or content.get("percept_digest") != record.percept_digest
        ):
            raise ValueError("perception record does not match normalized glyph")
        facts = content.get("facts")
        if not isinstance(facts, Mapping):
            raise ValueError("normalized perception facts must be a mapping")
        return glyph, content, facts

    def _evidence(self, record: PerceptionRecord, content: Mapping[str, Any]):
        normalized = self.graph.ledger.get(record.normalized_glyph_id)
        evidence = self.aura.research.ingest(
            source=f"perception:{record.source_id}/{record.modality}",
            title=f"Normalized perception: {content['observation_kind']}",
            content=_canonical(
                {
                    "source_id": record.source_id,
                    "modality": record.modality,
                    "captured_at": content.get("captured_at"),
                    "observation_kind": content["observation_kind"],
                    "facts": content["facts"],
                    "confidence": normalized.confidence,
                    "percept_digest": record.percept_digest,
                }
            ),
            source_type="perception",
        )
        evidence_glyphs = self.graph.ledger.find_by_external_ref(
            evidence.evidence_id,
            glyph_type="evidence",
        )
        if not evidence_glyphs:
            raise ValueError("perception evidence glyph was not created")
        evidence_glyph = evidence_glyphs[-1]
        if not any(
            edge.source == evidence_glyph.glyph_id
            and edge.target == normalized.glyph_id
            and edge.relation == "derived_from"
            for edge in self.graph.ledger.edges_from(evidence_glyph.glyph_id)
        ):
            self.graph.relate(
                evidence_glyph.glyph_id,
                normalized.glyph_id,
                "derived_from",
                actor=self.actor,
            )
        return evidence, evidence_glyph

    def _prior_facts(
        self,
        *,
        rule: PerceptionKnowledgeRule,
        subject: str,
    ) -> Tuple[Fact, ...]:
        if rule.versioned:
            if rule.predicate not in self.world_beliefs.versioned_predicates:
                raise ValueError(
                    "versioned perception rule predicate is absent from world belief view"
                )
            current = self.world_beliefs.current(
                subject=subject,
                predicate=rule.predicate,
            )
            return (current,) if current is not None else ()
        return tuple(
            self.core.memory.query(
                subject=subject,
                predicate=rule.predicate,
            )
        )

    def _commit_fact(
        self,
        *,
        record: PerceptionRecord,
        rule: PerceptionKnowledgeRule,
        subject: str,
        obj: str,
        confidence: float,
        captured_at: str,
        evidence_id: str,
        evidence_glyph_id: str,
        prior: Tuple[Fact, ...],
    ) -> Fact:
        fact_id = "perception-fact:" + _digest(
            {
                "normalized_glyph_id": record.normalized_glyph_id,
                "subject": subject,
                "predicate": rule.predicate,
                "object": obj,
                "evidence_id": evidence_id,
            }
        )
        fact = Fact(
            subject=subject,
            predicate=rule.predicate,
            object=obj,
            source=f"Perception:{record.source_id}/{record.modality}",
            confidence=confidence,
            observed_at=captured_at,
            evidence_id=fact_id,
        )
        canonical = self.core.memory.add(fact)
        fact_glyph = self.core.ensure_fact_glyph(
            canonical,
            derived_from=(
                record.normalized_glyph_id,
                evidence_glyph_id,
            ),
        )
        if not any(
            edge.source == evidence_glyph_id
            and edge.target == fact_glyph.glyph_id
            and edge.relation == "supports"
            for edge in self.graph.ledger.edges_from(evidence_glyph_id)
        ):
            self.graph.relate(
                evidence_glyph_id,
                fact_glyph.glyph_id,
                "supports",
                actor=self.actor,
            )

        if rule.versioned and prior:
            prior_glyph = self.core.ensure_fact_glyph(prior[-1])
            if not any(
                edge.source == fact_glyph.glyph_id
                and edge.target == prior_glyph.glyph_id
                and edge.relation == "supersedes"
                for edge in self.graph.ledger.edges_from(fact_glyph.glyph_id)
            ):
                self.graph.relate(
                    fact_glyph.glyph_id,
                    prior_glyph.glyph_id,
                    "supersedes",
                    actor=self.actor,
                )
        return canonical

    def _emit_conflict(
        self,
        *,
        record: PerceptionRecord,
        normalized_glyph_id: str,
        evidence_id: str,
        evidence_glyph_id: str,
        rule: PerceptionKnowledgeRule,
        subject: str,
        obj: str,
        conflicting: Tuple[Fact, ...],
        kind: str,
        reason: str,
        fact_evidence_id: Optional[str],
    ) -> tuple[str, Optional[str]]:
        prior_glyph_ids = []
        for old in conflicting:
            old_glyph = self.core.ensure_fact_glyph(old)
            prior_glyph_ids.append(old_glyph.glyph_id)
            self.graph.relate(
                evidence_glyph_id,
                old_glyph.glyph_id,
                "contradicts",
                actor=self.actor,
            )

        contradiction = self.graph.create(
            "critique",
            actor=self.actor,
            content={
                "kind": kind,
                "subject": subject,
                "predicate": rule.predicate,
                "prior_objects": [old.object for old in conflicting],
                "observed_object": obj,
                "evidence_id": evidence_id,
                "fact_evidence_id": fact_evidence_id,
                "authorization_effect": "none",
            },
            derived_from=tuple(
                [normalized_glyph_id, evidence_glyph_id]
                + prior_glyph_ids
            ),
        )

        research_need_id = None
        if rule.research_on_contradiction:
            assert rule.research_question_template is not None
            assert rule.research_measurements is not None
            question = rule.research_question_template.format(
                subject=subject,
                predicate=rule.predicate,
                old=" | ".join(old.object for old in conflicting),
                new=obj,
                source_id=record.source_id,
                modality=record.modality,
            )
            need = ResearchNeed.create(
                domain=rule.domain,
                question=question,
                reason=reason,
                measurements=rule.research_measurements,
                source_glyph_ids=(
                    contradiction.glyph_id,
                    evidence_glyph_id,
                ),
            )
            state = self.agenda.add(need)
            research_need_id = state.need.need_id
        return contradiction.glyph_id, research_need_id

    def _emit_stale(
        self,
        *,
        normalized_glyph_id: str,
        evidence_glyph_id: str,
        rule: PerceptionKnowledgeRule,
        subject: str,
        obj: str,
        current: Fact,
        captured_at: str,
    ) -> str:
        current_glyph = self.core.ensure_fact_glyph(current)
        glyph = self.graph.create(
            "critique",
            actor=self.actor,
            content={
                "kind": "stale_perception_observation",
                "subject": subject,
                "predicate": rule.predicate,
                "current_object": current.object,
                "current_observed_at": current.observed_at,
                "stale_object": obj,
                "stale_observed_at": captured_at,
                "authorization_effect": "none",
            },
            derived_from=(
                normalized_glyph_id,
                evidence_glyph_id,
                current_glyph.glyph_id,
            ),
        )
        return glyph.glyph_id

    def process(
        self,
        record: PerceptionRecord,
    ) -> PerceptionKnowledgeResult:
        normalized, content, facts = self._normalized(record)
        kind = str(content["observation_kind"])
        rule = self.rules.get(kind)
        if rule is None:
            raise ValueError("no perception knowledge rule for observation kind")

        for field in (rule.subject_fact, rule.object_fact):
            if field not in facts:
                raise ValueError(
                    f"normalized perception missing required fact field: {field}"
                )

        evidence, evidence_glyph = self._evidence(record, content)

        if not rule.allow_world_commit:
            return self._result(
                normalized_glyph_id=normalized.glyph_id,
                evidence_id=evidence.evidence_id,
                evidence_glyph_id=evidence_glyph.glyph_id,
                status="evidence_only",
            )

        confidence = normalized.confidence
        if confidence is None:
            return self._result(
                normalized_glyph_id=normalized.glyph_id,
                evidence_id=evidence.evidence_id,
                evidence_glyph_id=evidence_glyph.glyph_id,
                status="confidence_unavailable",
            )
        if confidence < rule.minimum_confidence:
            return self._result(
                normalized_glyph_id=normalized.glyph_id,
                evidence_id=evidence.evidence_id,
                evidence_glyph_id=evidence_glyph.glyph_id,
                status="confidence_below_threshold",
            )

        subject = _fact_value(facts[rule.subject_fact])
        obj = _fact_value(facts[rule.object_fact])
        captured_at = str(content.get("captured_at") or "")
        captured_time = _parse_time(captured_at, name="captured_at")
        prior = self._prior_facts(rule=rule, subject=subject)

        if rule.versioned and prior:
            current = prior[-1]
            current_time = _parse_time(
                current.observed_at,
                name="current fact observed_at",
            )
            if captured_time < current_time:
                critique_id = self._emit_stale(
                    normalized_glyph_id=normalized.glyph_id,
                    evidence_glyph_id=evidence_glyph.glyph_id,
                    rule=rule,
                    subject=subject,
                    obj=obj,
                    current=current,
                    captured_at=captured_at,
                )
                return self._result(
                    normalized_glyph_id=normalized.glyph_id,
                    evidence_id=evidence.evidence_id,
                    evidence_glyph_id=evidence_glyph.glyph_id,
                    status="stale_observation",
                    contradiction_glyph_id=critique_id,
                )
            if captured_time == current_time:
                if current.object == obj:
                    return self._result(
                        normalized_glyph_id=normalized.glyph_id,
                        evidence_id=evidence.evidence_id,
                        evidence_glyph_id=evidence_glyph.glyph_id,
                        status="simultaneous_duplicate",
                    )
                conflict_id, need_id = self._emit_conflict(
                    record=record,
                    normalized_glyph_id=normalized.glyph_id,
                    evidence_id=evidence.evidence_id,
                    evidence_glyph_id=evidence_glyph.glyph_id,
                    rule=rule,
                    subject=subject,
                    obj=obj,
                    conflicting=(current,),
                    kind="simultaneous_perception_conflict",
                    reason=(
                        "Two incompatible perceptions share the same timestamp; "
                        "investigate source quality or synchronization before "
                        "choosing a world-state head."
                    ),
                    fact_evidence_id=None,
                )
                return self._result(
                    normalized_glyph_id=normalized.glyph_id,
                    evidence_id=evidence.evidence_id,
                    evidence_glyph_id=evidence_glyph.glyph_id,
                    status="simultaneous_conflict",
                    contradiction_glyph_id=conflict_id,
                    research_need_id=need_id,
                )

        conflicting = tuple(fact for fact in prior if fact.object != obj)
        fact = self._commit_fact(
            record=record,
            rule=rule,
            subject=subject,
            obj=obj,
            confidence=confidence,
            captured_at=captured_at,
            evidence_id=evidence.evidence_id,
            evidence_glyph_id=evidence_glyph.glyph_id,
            prior=prior,
        )

        contradiction_glyph_id = None
        research_need_id = None
        contradiction = (
            bool(conflicting)
            and rule.change_semantics == "contradiction"
        )
        if contradiction:
            (
                contradiction_glyph_id,
                research_need_id,
            ) = self._emit_conflict(
                record=record,
                normalized_glyph_id=normalized.glyph_id,
                evidence_id=evidence.evidence_id,
                evidence_glyph_id=evidence_glyph.glyph_id,
                rule=rule,
                subject=subject,
                obj=obj,
                conflicting=conflicting,
                kind="perception_world_contradiction",
                reason=(
                    "A policy-declared contradiction between a new verified "
                    "perception and the prior world-state value requires "
                    "investigation before interpreting cause."
                ),
                fact_evidence_id=fact.evidence_id,
            )

        return self._result(
            normalized_glyph_id=normalized.glyph_id,
            evidence_id=evidence.evidence_id,
            evidence_glyph_id=evidence_glyph.glyph_id,
            status=(
                "committed_with_contradiction"
                if contradiction
                else "committed"
            ),
            fact_evidence_id=fact.evidence_id,
            contradiction_glyph_id=contradiction_glyph_id,
            research_need_id=research_need_id,
        )

    def select_context(
        self,
        *,
        query: str,
    ) -> ContextSelection:
        return self.context_selector.select(
            query=query,
            facts=self.world_beliefs.materialized_facts(),
            evidence=self.aura.research.store.all(),
        )
