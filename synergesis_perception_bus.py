"""Universal, provenance-first perception bus for Synergesis.

The bus normalizes caller-supplied percepts into auditable Glyph observations.
It does not pretend that cameras, microphones, sensors, or network feeds exist;
those must be provided by real adapters at runtime.

Authority is configured per source and can never be supplied by the percept
payload. Missing confidence stays `None`.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph


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
class RawPercept:
    source_id: str
    modality: str
    payload: Mapping[str, Any]
    captured_at: str
    external_id: Optional[str] = None

    def __post_init__(self):
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not self.modality.strip():
            raise ValueError("modality is required")
        if not self.captured_at.strip():
            raise ValueError("captured_at is required")
        if self.external_id is not None and not self.external_id.strip():
            raise ValueError("external_id must be non-empty when provided")


@dataclass(frozen=True)
class NormalizedPercept:
    observation_kind: str
    facts: Mapping[str, Any]
    confidence: Optional[float] = None

    def __post_init__(self):
        if not self.observation_kind.strip():
            raise ValueError("observation_kind is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be None or in [0,1]")


class DomainAdapter(Protocol):
    def normalize(self, percept: RawPercept) -> NormalizedPercept:
        ...


@dataclass(frozen=True)
class PerceptionSourcePolicy:
    source_id: str
    allowed_modalities: Tuple[str, ...]
    origin_authority_class: str
    enabled: bool = True
    taint_label: Optional[str] = None

    def __post_init__(self):
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not self.allowed_modalities:
            raise ValueError("allowed_modalities cannot be empty")
        if any(not modality.strip() for modality in self.allowed_modalities):
            raise ValueError("allowed modalities must be non-empty")
        if not self.origin_authority_class.strip():
            raise ValueError("origin_authority_class is required")
        if self.taint_label is not None and not self.taint_label.strip():
            raise ValueError("taint_label must be non-empty when provided")


@dataclass(frozen=True)
class PerceptionRecord:
    percept_digest: str
    raw_glyph_id: str
    normalized_glyph_id: str
    source_id: str
    modality: str


class PerceptionBus:
    actor = "SYN-PERCEPTION"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        security_graph: AegisSecurityGraph,
        source_policies: Sequence[PerceptionSourcePolicy],
        adapters: Mapping[tuple[str, str], DomainAdapter],
    ):
        if security_graph.graph is not graph:
            raise ValueError("perception bus security graph must share Glyph graph")
        policies: dict[str, PerceptionSourcePolicy] = {}
        for policy in source_policies:
            if policy.source_id in policies:
                raise ValueError("duplicate perception source policy")
            if policy.origin_authority_class not in security_graph.ORIGIN_CLASSES:
                raise ValueError("unsupported perception source authority class")
            policies[policy.source_id] = policy
        if not policies:
            raise ValueError("at least one perception source policy is required")
        self.graph = graph
        self.security_graph = security_graph
        self.policies = policies
        self.adapters = dict(adapters)

    def _percept_digest(self, percept: RawPercept) -> str:
        return _digest(
            {
                "source_id": percept.source_id,
                "modality": percept.modality,
                "payload": dict(percept.payload),
                "captured_at": percept.captured_at,
                "external_id": percept.external_id,
            }
        )

    def _raw_ref(self, percept: RawPercept, digest: str) -> str:
        if percept.external_id is not None:
            return f"percept:{percept.source_id}:{percept.external_id}"
        return f"percept-digest:{digest}"

    def ingest(self, percept: RawPercept) -> PerceptionRecord:
        policy = self.policies.get(percept.source_id)
        if policy is None:
            raise ValueError("unknown perception source")
        if not policy.enabled:
            raise ValueError("perception source is disabled")
        if percept.modality not in policy.allowed_modalities:
            raise ValueError("perception modality is not allowed for source")

        adapter = self.adapters.get((percept.source_id, percept.modality))
        if adapter is None:
            raise ValueError("no perception adapter configured for source/modality")

        digest = self._percept_digest(percept)
        raw_ref = self._raw_ref(percept, digest)
        existing_raw = self.graph.ledger.find_by_external_ref(
            raw_ref,
            glyph_type="observation",
        )
        if existing_raw:
            raw = existing_raw[-1]
            if (
                raw.content.get("kind") != "raw_percept"
                or raw.content.get("percept_digest") != digest
            ):
                raise ValueError("perception external_id collision with different payload")
        else:
            raw = self.graph.create(
                "observation",
                actor=self.actor,
                content={
                    "kind": "raw_percept",
                    "source_id": percept.source_id,
                    "modality": percept.modality,
                    "payload": dict(percept.payload),
                    "captured_at": percept.captured_at,
                    "external_id": percept.external_id,
                    "percept_digest": digest,
                    "authority_from_payload": False,
                    "authorization_effect": "none",
                },
                external_refs=(raw_ref,),
                metadata={"perception_stage": "raw"},
                dedupe_external_ref=raw_ref,
            )
            self.security_graph.bind_origin(
                raw.glyph_id,
                authority_class=policy.origin_authority_class,
                reason="configured perception source policy",
                metadata={
                    "perception_source_id": percept.source_id,
                    "perception_modality": percept.modality,
                },
            )
            if policy.taint_label is not None:
                self.security_graph.mark_taint(
                    raw.glyph_id,
                    label=policy.taint_label,
                    reason="configured perception source taint",
                )

        normalized_ref = f"normalized-percept:{raw.glyph_id}"
        existing_normalized = self.graph.ledger.find_by_external_ref(
            normalized_ref,
            glyph_type="observation",
        )
        if existing_normalized:
            normalized_glyph = existing_normalized[-1]
        else:
            normalized = adapter.normalize(percept)
            if not isinstance(normalized, NormalizedPercept):
                raise TypeError("perception adapter must return NormalizedPercept")
            normalized_glyph = self.graph.create(
                "observation",
                actor=self.actor,
                content={
                    "kind": "normalized_perception",
                    "observation_kind": normalized.observation_kind,
                    "facts": dict(normalized.facts),
                    "source_id": percept.source_id,
                    "modality": percept.modality,
                    "captured_at": percept.captured_at,
                    "percept_digest": digest,
                    "confidence_available": normalized.confidence is not None,
                    "authorization_effect": "none",
                },
                external_refs=(normalized_ref,),
                confidence=normalized.confidence,
                metadata={"perception_stage": "normalized"},
                derived_from=(raw.glyph_id,),
                dedupe_external_ref=normalized_ref,
            )

        return PerceptionRecord(
            percept_digest=digest,
            raw_glyph_id=raw.glyph_id,
            normalized_glyph_id=normalized_glyph.glyph_id,
            source_id=percept.source_id,
            modality=percept.modality,
        )
