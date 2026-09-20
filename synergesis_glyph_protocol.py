"""Synergesis Glyph Protocol v1.

Purpose
-------
Glyphs are immutable, typed, machine-readable audit objects for consequential
state transitions in Synergesis. They are not a reconstruction of a model's
private chain-of-thought. They record observable system-level artifacts:
observations, evidence, hypotheses, decisions, policy checks, actions, outcomes,
learning signals, goals, plans, and related concepts.

Core invariant:
    No consequential state transition without an auditable trace.

The ledger is append-only and hash-chained. Relationships are explicit graph
edges. Missing information is omitted rather than fabricated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = "synergesis.glyph.v1"

GLYPH_TYPES = frozenset({
    "observation",
    "evidence",
    "fact",
    "hypothesis",
    "decision",
    "policy",
    "action",
    "outcome",
    "learning",
    "goal",
    "plan",
    "step",
    "concept",
    "critique",
    "inference",
    "cycle",
})

RELATION_TYPES = frozenset({
    "observes",
    "derived_from",
    "supports",
    "contradicts",
    "motivates",
    "proposes",
    "authorizes",
    "denies",
    "produces",
    "evaluates",
    "updates",
    "supersedes",
    "critiques",
    "part_of",
    "targets",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def to_wire(value: Any) -> Any:
    """Convert nested protocol values into canonical JSON-native values.

    Python may use dataclasses and tuples internally for immutability. The wire
    protocol contains only JSON-native objects, arrays, strings, numbers,
    booleans and null.
    """
    def convert(item: Any) -> Any:
        if is_dataclass(item):
            return {k: convert(v) for k, v in asdict(item).items()}
        if isinstance(item, Mapping):
            return {str(k): convert(v) for k, v in item.items()}
        if isinstance(item, (tuple, list)):
            return [convert(v) for v in item]
        if isinstance(item, (str, int, float, bool)) or item is None:
            return item
        raise TypeError(f"unsupported wire value type: {type(item).__name__}")

    return convert(value)


def _validate_confidence(value: Optional[float]) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be numeric or None")
    if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")


@dataclass(frozen=True)
class Glyph:
    glyph_id: str
    glyph_type: str
    schema_version: str
    created_at: str
    actor: str
    content: Mapping[str, Any]
    external_refs: Tuple[str, ...]
    confidence: Optional[float]
    metadata: Mapping[str, Any]

    def __post_init__(self):
        if self.glyph_type not in GLYPH_TYPES:
            raise ValueError(f"unsupported glyph_type: {self.glyph_type}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported glyph schema version")
        if not self.actor.strip():
            raise ValueError("glyph actor is required")
        if any(not ref.strip() for ref in self.external_refs):
            raise ValueError("external refs must be non-empty")
        _validate_confidence(self.confidence)


@dataclass(frozen=True)
class GlyphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    created_at: str
    actor: str
    metadata: Mapping[str, Any]

    def __post_init__(self):
        if self.relation not in RELATION_TYPES:
            raise ValueError(f"unsupported relation: {self.relation}")
        if not self.source.strip() or not self.target.strip():
            raise ValueError("edge source and target are required")
        if self.source == self.target:
            raise ValueError("self-edges are not allowed")
        if not self.actor.strip():
            raise ValueError("edge actor is required")


@dataclass(frozen=True)
class LedgerEvent:
    sequence: int
    event_id: str
    event_type: str
    created_at: str
    previous_digest: Optional[str]
    payload: Mapping[str, Any]
    digest: str

    def __post_init__(self):
        if self.event_type not in {"glyph", "edge"}:
            raise ValueError("event_type must be glyph or edge")
        if self.sequence < 1:
            raise ValueError("sequence must be >= 1")


@dataclass(frozen=True)
class IntegrityCheckpoint:
    event_count: int
    chain_head: Optional[str]
    merkle_root: Optional[str]


@dataclass(frozen=True)
class AuditTrace:
    focal_glyph: Glyph
    glyphs: Tuple[Glyph, ...]
    edges: Tuple[GlyphEdge, ...]


class GlyphLedger:
    """Append-only, hash-chained graph ledger with verified incremental indexes.

    Earlier versions re-read and re-verified the entire JSONL ledger on nearly
    every graph operation. That was correct but scaled poorly under sustained
    roaming because edge dedupe and glyph lookup became effectively quadratic.

    This implementation keeps verified in-memory indexes and invalidates them
    whenever the backing file changes externally. ``verify()`` always forces a
    fresh full-chain verification from disk.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_size: Optional[int] = None
        self._events_cache: list[LedgerEvent] = []
        self._glyphs_cache: list[Glyph] = []
        self._edges_cache: list[GlyphEdge] = []
        self._glyph_by_id: dict[str, Glyph] = {}
        self._external_ref_index: dict[str, list[Glyph]] = {}
        self._edge_key_index: dict[tuple[str, str, str], GlyphEdge] = {}
        self._edges_from_index: dict[str, list[GlyphEdge]] = {}
        self._edges_to_index: dict[str, list[GlyphEdge]] = {}

    def _file_size(self) -> Optional[int]:
        if not self.path.exists():
            return None
        return int(self.path.stat().st_size)

    def _raw_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def _decode_glyph(self, payload: Mapping[str, Any]) -> Glyph:
        p = dict(payload)
        p["external_refs"] = tuple(p.get("external_refs", ()))
        return Glyph(**p)

    def _decode_edge(self, payload: Mapping[str, Any]) -> GlyphEdge:
        return GlyphEdge(**dict(payload))

    def _install_cache(self, events: Sequence[LedgerEvent]) -> None:
        glyphs: list[Glyph] = []
        edges: list[GlyphEdge] = []
        glyph_by_id: dict[str, Glyph] = {}
        external_ref_index: dict[str, list[Glyph]] = {}
        edge_key_index: dict[tuple[str, str, str], GlyphEdge] = {}
        edges_from_index: dict[str, list[GlyphEdge]] = {}
        edges_to_index: dict[str, list[GlyphEdge]] = {}

        for event in events:
            if event.event_type == "glyph":
                glyph = self._decode_glyph(event.payload)
                glyphs.append(glyph)
                glyph_by_id[glyph.glyph_id] = glyph
                for ref in glyph.external_refs:
                    external_ref_index.setdefault(ref, []).append(glyph)
            elif event.event_type == "edge":
                edge = self._decode_edge(event.payload)
                edges.append(edge)
                edge_key_index.setdefault(
                    (edge.source, edge.target, edge.relation),
                    edge,
                )
                edges_from_index.setdefault(edge.source, []).append(edge)
                edges_to_index.setdefault(edge.target, []).append(edge)
            else:
                raise ValueError(
                    f"unsupported glyph ledger event type: {event.event_type}"
                )

        self._events_cache = list(events)
        self._glyphs_cache = glyphs
        self._edges_cache = edges
        self._glyph_by_id = glyph_by_id
        self._external_ref_index = external_ref_index
        self._edge_key_index = edge_key_index
        self._edges_from_index = edges_from_index
        self._edges_to_index = edges_to_index
        self._cache_size = self._file_size()

    def _load_verified(self, *, force: bool = False) -> None:
        size = self._file_size()
        if not force and size == self._cache_size:
            return

        raw = self._raw_events()
        out: list[LedgerEvent] = []
        previous: Optional[str] = None
        for index, item in enumerate(raw, start=1):
            event = LedgerEvent(**item)
            if event.sequence != index:
                raise ValueError(
                    f"glyph ledger sequence failure: expected {index}, got {event.sequence}"
                )
            if event.previous_digest != previous:
                raise ValueError(
                    f"glyph ledger chain failure at sequence {event.sequence}"
                )
            body = {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "created_at": event.created_at,
                "previous_digest": event.previous_digest,
                "payload": dict(event.payload),
            }
            expected = _digest(body)
            if expected != event.digest or event.event_id != expected[:24]:
                raise ValueError(
                    f"glyph ledger integrity failure at sequence {event.sequence}"
                )
            out.append(event)
            previous = event.digest

        self._install_cache(out)

    def events(self) -> Tuple[LedgerEvent, ...]:
        self._load_verified()
        return tuple(self._events_cache)

    def _append(self, event_type: str, payload: Mapping[str, Any]) -> LedgerEvent:
        self._load_verified()
        events = self._events_cache
        sequence = len(events) + 1
        previous = events[-1].digest if events else None
        created_at = _now()
        body = {
            "sequence": sequence,
            "event_type": event_type,
            "created_at": created_at,
            "previous_digest": previous,
            "payload": dict(payload),
        }
        digest = _digest(body)
        event = LedgerEvent(
            sequence=sequence,
            event_id=digest[:24],
            event_type=event_type,
            created_at=created_at,
            previous_digest=previous,
            payload=dict(payload),
            digest=digest,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(asdict(event)) + "\n")

        # Incremental cache update; no full ledger re-read on normal appends.
        self._events_cache.append(event)
        if event_type == "glyph":
            glyph = self._decode_glyph(event.payload)
            self._glyphs_cache.append(glyph)
            self._glyph_by_id[glyph.glyph_id] = glyph
            for ref in glyph.external_refs:
                self._external_ref_index.setdefault(ref, []).append(glyph)
        elif event_type == "edge":
            edge = self._decode_edge(event.payload)
            self._edges_cache.append(edge)
            self._edge_key_index.setdefault(
                (edge.source, edge.target, edge.relation),
                edge,
            )
            self._edges_from_index.setdefault(edge.source, []).append(edge)
            self._edges_to_index.setdefault(edge.target, []).append(edge)
        else:
            raise ValueError(f"unsupported glyph ledger event type: {event_type}")

        self._cache_size = self._file_size()
        return event

    def glyphs(self) -> Tuple[Glyph, ...]:
        self._load_verified()
        return tuple(self._glyphs_cache)

    def edges(self) -> Tuple[GlyphEdge, ...]:
        self._load_verified()
        return tuple(self._edges_cache)

    def edges_from(
        self,
        source: str,
        *,
        relation: Optional[str] = None,
    ) -> Tuple[GlyphEdge, ...]:
        self._load_verified()
        values = tuple(self._edges_from_index.get(source, ()))
        if relation is None:
            return values
        return tuple(edge for edge in values if edge.relation == relation)

    def edges_to(
        self,
        target: str,
        *,
        relation: Optional[str] = None,
    ) -> Tuple[GlyphEdge, ...]:
        self._load_verified()
        values = tuple(self._edges_to_index.get(target, ()))
        if relation is None:
            return values
        return tuple(edge for edge in values if edge.relation == relation)

    def get(self, glyph_id: str) -> Glyph:
        self._load_verified()
        try:
            return self._glyph_by_id[glyph_id]
        except KeyError as exc:
            raise KeyError(f"unknown glyph: {glyph_id}") from exc

    def find_by_external_ref(
        self,
        external_ref: str,
        *,
        glyph_type: Optional[str] = None,
    ) -> Tuple[Glyph, ...]:
        self._load_verified()
        matches = tuple(self._external_ref_index.get(external_ref, ()))
        if glyph_type is None:
            return matches
        return tuple(g for g in matches if g.glyph_type == glyph_type)

    def append_glyph(
        self,
        *,
        glyph_type: str,
        actor: str,
        content: Mapping[str, Any],
        external_refs: Sequence[str] = (),
        confidence: Optional[float] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        dedupe_external_ref: Optional[str] = None,
    ) -> Glyph:
        if glyph_type not in GLYPH_TYPES:
            raise ValueError(f"unsupported glyph_type: {glyph_type}")
        if not actor.strip():
            raise ValueError("actor is required")
        _validate_confidence(confidence)

        refs = tuple(dict.fromkeys(str(x) for x in external_refs))
        if any(not x.strip() for x in refs):
            raise ValueError("external refs must be non-empty")
        if dedupe_external_ref is not None:
            existing = self.find_by_external_ref(
                dedupe_external_ref,
                glyph_type=glyph_type,
            )
            if existing:
                return existing[-1]

        created_at = _now()
        identity = {
            "glyph_type": glyph_type,
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
            "actor": actor,
            "content": dict(content),
            "external_refs": refs,
            "confidence": confidence,
            "metadata": dict(metadata or {}),
        }
        glyph_id = f"g:{_digest(identity)[:32]}"
        glyph = Glyph(
            glyph_id=glyph_id,
            glyph_type=glyph_type,
            schema_version=SCHEMA_VERSION,
            created_at=created_at,
            actor=actor,
            content=dict(content),
            external_refs=refs,
            confidence=float(confidence) if confidence is not None else None,
            metadata=dict(metadata or {}),
        )
        self._append("glyph", asdict(glyph))
        return glyph

    def append_edge(
        self,
        *,
        source: str,
        target: str,
        relation: str,
        actor: str,
        metadata: Optional[Mapping[str, Any]] = None,
        dedupe: bool = True,
    ) -> GlyphEdge:
        if relation not in RELATION_TYPES:
            raise ValueError(f"unsupported relation: {relation}")
        self.get(source)
        self.get(target)
        if source == target:
            raise ValueError("self-edges are not allowed")

        if dedupe:
            existing = self._edge_key_index.get((source, target, relation))
            if existing is not None:
                return existing

        created_at = _now()
        body = {
            "source": source,
            "target": target,
            "relation": relation,
            "created_at": created_at,
            "actor": actor,
            "metadata": dict(metadata or {}),
        }
        edge = GlyphEdge(
            edge_id=f"e:{_digest(body)[:32]}",
            source=source,
            target=target,
            relation=relation,
            created_at=created_at,
            actor=actor,
            metadata=dict(metadata or {}),
        )
        self._append("edge", asdict(edge))
        return edge

    def verify(self) -> IntegrityCheckpoint:
        # Always re-read and re-hash from disk here, even if in-memory indexes
        # appear current. This preserves the explicit integrity-check boundary.
        self._load_verified(force=True)
        glyph_ids = set(self._glyph_by_id)
        for edge in self._edges_cache:
            if edge.source not in glyph_ids or edge.target not in glyph_ids:
                raise ValueError(f"dangling glyph edge: {edge.edge_id}")
        digests = [event.digest for event in self._events_cache]
        return IntegrityCheckpoint(
            event_count=len(self._events_cache),
            chain_head=digests[-1] if digests else None,
            merkle_root=_merkle_root(digests),
        )

def _merkle_root(digests: Sequence[str]) -> Optional[str]:
    if not digests:
        return None
    layer = [str(x) for x in digests]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [
            sha256((layer[i] + layer[i + 1]).encode("utf-8")).hexdigest()
            for i in range(0, len(layer), 2)
        ]
    return layer[0]


class GlyphAuditGraph:
    """Queryable graph facade over GlyphLedger."""

    def __init__(self, ledger: GlyphLedger):
        self.ledger = ledger

    def create(
        self,
        glyph_type: str,
        *,
        actor: str,
        content: Mapping[str, Any],
        external_refs: Sequence[str] = (),
        confidence: Optional[float] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        derived_from: Sequence[str] = (),
        dedupe_external_ref: Optional[str] = None,
    ) -> Glyph:
        glyph = self.ledger.append_glyph(
            glyph_type=glyph_type,
            actor=actor,
            content=content,
            external_refs=external_refs,
            confidence=confidence,
            metadata=metadata,
            dedupe_external_ref=dedupe_external_ref,
        )
        for parent in derived_from:
            if parent != glyph.glyph_id:
                self.ledger.append_edge(
                    source=glyph.glyph_id,
                    target=parent,
                    relation="derived_from",
                    actor=actor,
                )
        return glyph

    def relate(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        actor: str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> GlyphEdge:
        return self.ledger.append_edge(
            source=source,
            target=target,
            relation=relation,
            actor=actor,
            metadata=metadata,
        )

    def upstream(
        self,
        glyph_id: str,
        *,
        max_depth: int = 8,
    ) -> AuditTrace:
        return self._traverse(glyph_id, upstream=True, max_depth=max_depth)

    def downstream(
        self,
        glyph_id: str,
        *,
        max_depth: int = 8,
    ) -> AuditTrace:
        return self._traverse(glyph_id, upstream=False, max_depth=max_depth)

    def _traverse(
        self,
        glyph_id: str,
        *,
        upstream: bool,
        max_depth: int,
    ) -> AuditTrace:
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        focal = self.ledger.get(glyph_id)
        seen = {glyph_id}
        frontier = {glyph_id}
        chosen_edges: list[GlyphEdge] = []

        for _ in range(max_depth):
            next_frontier = set()
            for current in frontier:
                edges = (
                    self.ledger.edges_from(current)
                    if upstream
                    else self.ledger.edges_to(current)
                )
                for edge in edges:
                    node = edge.target if upstream else edge.source
                    chosen_edges.append(edge)
                    if node not in seen:
                        seen.add(node)
                        next_frontier.add(node)
            if not next_frontier:
                break
            frontier = next_frontier

        glyphs = tuple(
            sorted(
                (self.ledger.get(gid) for gid in seen),
                key=lambda g: (g.created_at, g.glyph_id),
            )
        )
        unique_edges = {
            edge.edge_id: edge for edge in chosen_edges
        }
        return AuditTrace(
            focal_glyph=focal,
            glyphs=glyphs,
            edges=tuple(
                sorted(
                    unique_edges.values(),
                    key=lambda e: (e.created_at, e.edge_id),
                )
            ),
        )

    def explain_decision(self, glyph_id: str) -> AuditTrace:
        glyph = self.ledger.get(glyph_id)
        if glyph.glyph_type != "decision":
            raise ValueError("explain_decision requires a decision glyph")
        return self.upstream(glyph_id)

    def impacted_by(self, glyph_id: str, *, max_depth: int = 16) -> AuditTrace:
        """Return descendants that ultimately depend on the focal glyph."""
        return self.downstream(glyph_id, max_depth=max_depth)
