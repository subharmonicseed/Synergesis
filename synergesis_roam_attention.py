"""SYN-ROAM attention controller.

This module turns explicit knowledge gaps into a bounded research agenda.
It does not fabricate importance. Each priority component must be supplied by an
upstream evaluator and is stored audibly.

One scheduler tick selects at most one pending need and launches at most one
bounded SYN-ROAM session.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_roam import MethodOutcome, OutcomeMetrics, ResearchQuestion, RoamSession, SynRoam


def _canon(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _hash(value: Any) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


def _unit(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0,1]")
    return value


@dataclass(frozen=True)
class AttentionMeasurements:
    uncertainty: float
    expected_impact: float
    staleness: float
    novelty_gap: float

    def __post_init__(self):
        for name, value in asdict(self).items():
            _unit(value, name)


@dataclass(frozen=True)
class AttentionWeights:
    uncertainty: float
    expected_impact: float
    staleness: float
    novelty_gap: float

    def __post_init__(self):
        values = asdict(self)
        for name, value in values.items():
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        if sum(values.values()) <= 0:
            raise ValueError("at least one attention weight must be > 0")


def score_attention(
    measurements: AttentionMeasurements,
    weights: AttentionWeights,
) -> float:
    numerator = sum(
        asdict(measurements)[name] * asdict(weights)[name]
        for name in asdict(weights)
    )
    denominator = sum(asdict(weights).values())
    return numerator / denominator


@dataclass(frozen=True)
class ResearchNeed:
    need_id: str
    domain: str
    question: str
    hypothesis: Optional[str]
    reason: str
    source_glyph_ids: Tuple[str, ...]
    measurements: AttentionMeasurements

    @classmethod
    def create(
        cls,
        *,
        domain: str,
        question: str,
        reason: str,
        measurements: AttentionMeasurements,
        hypothesis: Optional[str] = None,
        source_glyph_ids: Sequence[str] = (),
    ) -> "ResearchNeed":
        if not domain.strip() or not question.strip() or not reason.strip():
            raise ValueError("domain, question and reason are required")
        payload = {
            "domain": domain,
            "question": question,
            "hypothesis": hypothesis,
            "reason": reason,
            "source_glyph_ids": list(source_glyph_ids),
            "measurements": asdict(measurements),
        }
        return cls(
            need_id=f"need:{_hash(payload)[:32]}",
            domain=domain,
            question=question,
            hypothesis=hypothesis,
            reason=reason,
            source_glyph_ids=tuple(source_glyph_ids),
            measurements=measurements,
        )


@dataclass(frozen=True)
class NeedState:
    need: ResearchNeed
    status: str
    session_id: Optional[str]
    event_count: int

    def __post_init__(self):
        if self.status not in {
            "pending",
            "researched",
            "evaluated",
            "deferred",
            "cancelled",
        }:
            raise ValueError("invalid research need status")


class ResearchAgenda:
    """Append-only lifecycle ledger for spontaneous research needs."""

    def __init__(
        self,
        path: str | Path,
        *,
        graph: GlyphAuditGraph,
        weights: AttentionWeights,
        actor: str = "SYN-ROAM",
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = graph
        self.weights = weights
        self.actor = actor

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _append(
        self,
        *,
        need: ResearchNeed,
        status: str,
        session_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> NeedState:
        current = self.get_optional(need.need_id)
        event = {
            "need": {
                **asdict(need),
                "measurements": asdict(need.measurements),
            },
            "status": status,
            "session_id": session_id,
            "reason": reason,
            "sequence_for_need": 1 if current is None else current.event_count + 1,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(event) + "\n")

        prior_glyph = None
        matches = self.graph.ledger.find_by_external_ref(
            need.need_id,
            glyph_type="goal",
        )
        if matches:
            prior_glyph = matches[-1]

        parents = list(need.source_glyph_ids)
        # Validate provenance before appending the new immutable goal glyph, so
        # a bad reference cannot leave a partial ledger write.
        for parent_id in parents:
            self.graph.ledger.get(parent_id)
        if prior_glyph is not None:
            parents.append(prior_glyph.glyph_id)
        need_glyph = self.graph.create(
            "goal",
            actor=self.actor,
            content={
                "kind": "research_need",
                "domain": need.domain,
                "question": need.question,
                "hypothesis": need.hypothesis,
                "reason": need.reason,
                "measurements": asdict(need.measurements),
                "attention_score": score_attention(
                    need.measurements, self.weights
                ),
                "status": status,
                "session_id": session_id,
            },
            external_refs=(
                need.need_id,
                f"need-state:{need.need_id}:{event['sequence_for_need']}",
            ),
            derived_from=tuple(parents),
            dedupe_external_ref=f"need-state:{need.need_id}:{event['sequence_for_need']}",
        )
        if prior_glyph is not None:
            self.graph.relate(
                need_glyph.glyph_id,
                prior_glyph.glyph_id,
                "supersedes",
                actor=self.actor,
            )
        return self.get(need.need_id)

    def add(self, need: ResearchNeed) -> NeedState:
        current = self.get_optional(need.need_id)
        if current is not None:
            return current
        return self._append(need=need, status="pending")

    def _decode_need(self, raw: Mapping[str, Any]) -> ResearchNeed:
        item = dict(raw)
        item["measurements"] = AttentionMeasurements(**item["measurements"])
        item["source_glyph_ids"] = tuple(item.get("source_glyph_ids", ()))
        return ResearchNeed(**item)

    def get_optional(self, need_id: str) -> Optional[NeedState]:
        events = [
            event for event in self._events()
            if event["need"]["need_id"] == need_id
        ]
        if not events:
            return None
        last = events[-1]
        return NeedState(
            need=self._decode_need(last["need"]),
            status=last["status"],
            session_id=last["session_id"],
            event_count=len(events),
        )

    def get(self, need_id: str) -> NeedState:
        state = self.get_optional(need_id)
        if state is None:
            raise KeyError(f"unknown research need: {need_id}")
        return state

    def pending(self) -> Tuple[NeedState, ...]:
        ids = []
        for event in self._events():
            nid = event["need"]["need_id"]
            if nid not in ids:
                ids.append(nid)
        return tuple(
            state
            for state in (self.get(nid) for nid in ids)
            if state.status == "pending"
        )

    def select_next(self) -> Optional[NeedState]:
        candidates = self.pending()
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda state: (
                -score_attention(state.need.measurements, self.weights),
                state.need.need_id,
            ),
        )[0]

    def mark_researched(self, need_id: str, session_id: str) -> NeedState:
        current = self.get(need_id)
        if current.status != "pending":
            raise ValueError("only pending needs may be researched")
        return self._append(
            need=current.need,
            status="researched",
            session_id=session_id,
        )

    def mark_evaluated(self, need_id: str) -> NeedState:
        current = self.get(need_id)
        if current.status != "researched":
            raise ValueError("only researched needs may be evaluated")
        return self._append(
            need=current.need,
            status="evaluated",
            session_id=current.session_id,
        )

    def cancel(self, need_id: str, *, reason: str) -> NeedState:
        current = self.get(need_id)
        if current.status != "pending":
            raise ValueError("only pending needs may be cancelled")
        if not reason.strip():
            raise ValueError("cancellation reason required")
        return self._append(need=current.need, status="cancelled", reason=reason)

    def defer(self, need_id: str, *, reason: str) -> NeedState:
        current = self.get(need_id)
        if current.status != "pending":
            raise ValueError("only pending needs may be deferred")
        return self._append(
            need=current.need,
            status="deferred",
            reason=reason,
        )


@dataclass(frozen=True)
class RoamTick:
    need_id: Optional[str]
    session: Optional[RoamSession]
    status: str


class RoamAttentionController:
    """Launches at most one bounded research session per explicit tick."""

    def __init__(self, *, agenda: ResearchAgenda, roam: SynRoam):
        self.agenda = agenda
        self.roam = roam
        self._tick_hooks = []
        self._need_guards = []

    def add_tick_hook(self, hook):
        if hook not in self._tick_hooks:
            self._tick_hooks.append(hook)

    def add_need_guard(self, guard):
        if guard not in self._need_guards:
            self._need_guards.append(guard)

    def tick_once(self) -> RoamTick:
        for hook in tuple(self._tick_hooks):
            hook()
        selected = self.agenda.select_next()
        if selected is None:
            return RoamTick(None, None, "idle")

        if not all(guard(selected.need) for guard in tuple(self._need_guards)):
            self.agenda.cancel(selected.need.need_id, reason="research need failed freshness guard")
            return RoamTick(selected.need.need_id, None, "cancelled")

        question = ResearchQuestion.create(
            domain=selected.need.domain,
            question=selected.need.question,
            hypothesis=selected.need.hypothesis,
        )
        session = self.roam.research_once(question)
        self.agenda.mark_researched(selected.need.need_id, session.session_id)
        return RoamTick(selected.need.need_id, session, "researched")

    def evaluate_need(
        self,
        *,
        need_id: str,
        session: RoamSession,
        metrics: OutcomeMetrics,
    ) -> MethodOutcome:
        state = self.agenda.get(need_id)
        if state.status != "researched":
            raise ValueError("only researched needs may be evaluated")
        if state.session_id != session.session_id:
            raise ValueError("session does not belong to research need")
        outcome = self.roam.evaluate(session, metrics)
        self.agenda.mark_evaluated(need_id)
        return outcome


class GapNeedProvider(Protocol):
    """Turns an explicit SELENE predicate gap into a scored research need."""

    def build_need(self, predicate: str) -> ResearchNeed:
        ...


class SeleneRoamBridge:
    """One-shot bridge from SELENE knowledge gaps to the research agenda.

    The bridge does not invent uncertainty/impact scores. A caller-supplied
    provider must define the concrete question and measurements for each gap.
    """

    def __init__(self, *, core: Any, agenda: ResearchAgenda, provider: GapNeedProvider):
        self.core = core
        self.agenda = agenda
        self.provider = provider

    def scan_once(self, required_predicates: Iterable[str]) -> Tuple[NeedState, ...]:
        gaps = self.core.selene.gaps(required_predicates)
        states = []
        for predicate in gaps:
            need = self.provider.build_need(predicate)
            states.append(self.agenda.add(need))
        return tuple(states)
