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
import os
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
    """Append-only lifecycle ledger for spontaneous research needs.

    Agenda events and their graph projections are committed through a small
    per-event intent file.  The intent is durable before either projection is
    changed; a newly opened agenda replays any remaining intents.  This keeps
    the two single-writer append-only ledgers convergent after a process crash.
    """

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
        self._pending_dir = self.path.with_name(self.path.name + ".pending")
        self._recover_pending()
        self._check_legacy_phantoms()

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _need_payload(need: ResearchNeed) -> dict[str, Any]:
        return {**asdict(need), "measurements": asdict(need.measurements)}

    def _event_for(self, need: ResearchNeed, status: str, session_id: Optional[str],
                   reason: Optional[str], sequence: int) -> dict[str, Any]:
        return {
            "need": self._need_payload(need),
            "status": status,
            "session_id": session_id,
            "reason": reason,
            "sequence_for_need": sequence,
        }

    def _intent_path(self, event: Mapping[str, Any]) -> Path:
        key = _hash({"need_id": event["need"]["need_id"], "sequence": event["sequence_for_need"]})
        return self._pending_dir / f"{key}.json"

    def _write_intent(self, event: Mapping[str, Any]) -> Path:
        self._pending_dir.mkdir(parents=True, exist_ok=True)
        target = self._intent_path(event)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            existing_event = existing.get("event", existing)
            if _canon(existing_event) != _canon(event):
                raise ValueError("conflicting pending agenda intent")
            return target
        temporary = target.with_suffix(".tmp")
        payload = {"event": event, "actor": self.actor,
                   "attention_score": score_attention(self._decode_need(event["need"]).measurements, self.weights)}
        with temporary.open("w", encoding="utf-8") as fh:
            fh.write(_canon(payload))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, target)
        return target

    def _append_event_if_needed(self, event: Mapping[str, Any]) -> None:
        events = self._events()
        same = [e for e in events if e["need"]["need_id"] == event["need"]["need_id"]
                and e["sequence_for_need"] == event["sequence_for_need"]]
        if same:
            if _canon(same[-1]) != _canon(event):
                raise ValueError("conflicting agenda event payload")
            return
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(event) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _apply_intent(self, event: Mapping[str, Any]) -> None:
        need = self._decode_need(event["need"])
        public_event = {k: v for k, v in event.items() if not k.startswith("_")}
        rows = [e for e in self._events() if e['need']['need_id'] == need.need_id]
        sequence = event['sequence_for_need']
        if type(sequence) is not int or sequence < 1:
            raise ValueError("invalid agenda sequence")
        if [e['sequence_for_need'] for e in rows] != list(range(1, len(rows) + 1)):
            raise ValueError("agenda sequence is not contiguous")
        if sequence <= len(rows):
            if _canon(rows[sequence - 1]) != _canon(public_event):
                raise ValueError("conflicting agenda event payload")
        elif sequence != len(rows) + 1:
            raise ValueError("agenda intent sequence gap")
        previous_status = rows[sequence - 2]['status'] if sequence > 1 else None
        allowed = {None: {'pending'}, 'pending': {'researched', 'cancelled', 'deferred'},
                   'researched': {'evaluated'}}
        if event['status'] not in allowed.get(previous_status, set()):
            raise ValueError("invalid agenda lifecycle transition")
        # Parent validation happens before graph or agenda mutation, including
        # when this intent is replayed after a crash.
        parents = list(need.source_glyph_ids)
        for parent_id in parents:
            self.graph.ledger.get(parent_id)

        current = self.get_optional(need.need_id)
        if current is not None and _canon(self._need_payload(current.need)) != _canon(self._need_payload(need)):
            raise ValueError("conflicting research need payload")

        state_glyphs = self.graph.ledger.find_by_external_ref(
            f"need-state:{need.need_id}:{event['sequence_for_need']}",
            glyph_type="goal",
        )
        prior_glyph = None
        if event["sequence_for_need"] > 1:
            prior_ref = f"need-state:{need.need_id}:{event['sequence_for_need'] - 1}"
            prior_matches = self.graph.ledger.find_by_external_ref(prior_ref, glyph_type="goal")
            if not prior_matches:
                raise ValueError("missing prior research graph state")
            prior_glyph = prior_matches[-1]
        if prior_glyph is not None:
            parents.append(prior_glyph.glyph_id)

        # Replay uses the original scoring/actor values captured in the intent.
        intent_actor = event.get("_actor", self.actor)
        intent_score = event.get("_attention_score")
        content = {
            "kind": "research_need",
            "domain": need.domain,
            "question": need.question,
            "hypothesis": need.hypothesis,
            "reason": need.reason,
            "measurements": asdict(need.measurements),
            "attention_score": (intent_score if intent_score is not None else score_attention(need.measurements, self.weights)),
            "status": event["status"],
            "session_id": event["session_id"],
        }
        if len(state_glyphs) > 1 or (state_glyphs and dict(state_glyphs[-1].content) != content):
            raise ValueError("conflicting research graph payload")
        glyph = self.graph.create(
            "goal", actor=intent_actor, content=content,
            external_refs=(need.need_id,
                           f"need-state:{need.need_id}:{event['sequence_for_need']}"),
            derived_from=tuple(parents),
            dedupe_external_ref=f"need-state:{need.need_id}:{event['sequence_for_need']}",
        )
        if prior_glyph is not None:
            self.graph.relate(glyph.glyph_id, prior_glyph.glyph_id, "supersedes", actor=intent_actor)
        public_event = {k: v for k, v in event.items() if not k.startswith("_")}
        self._append_event_if_needed(public_event)

    def _recover_pending(self) -> None:
        if not self._pending_dir.exists():
            return
        pending = []
        for intent in self._pending_dir.glob("*.json"):
            raw = json.loads(intent.read_text(encoding="utf-8"))
            event = raw.get("event", raw)
            if "actor" in raw:
                event = {**event, "_actor": raw["actor"], "_attention_score": raw.get("attention_score")}
            pending.append((intent, event))
        for intent, event in sorted(pending, key=lambda item: (item[1]['need']['need_id'], item[1]['sequence_for_need'])):
            self._apply_intent(event)
            intent.unlink()

    def _check_legacy_phantoms(self) -> None:
        # Legacy rows are trusted only when their graph projection exists.
        counts = {}
        for event in self._events():
            nid = event['need']['need_id']
            counts[nid] = counts.get(nid, 0) + 1
            if event['sequence_for_need'] != counts[nid]:
                raise ValueError("agenda sequence is not contiguous")
            ref = f"need-state:{event['need']['need_id']}:{event['sequence_for_need']}"
            matches = self.graph.ledger.find_by_external_ref(ref, glyph_type="goal")
            if not matches:
                raise ValueError("agenda event missing graph projection; reconciliation required")
            content = matches[-1].content
            expected = {k: event['need'][k] for k in ('domain', 'question', 'hypothesis', 'reason', 'measurements')}
            expected.update(kind='research_need', status=event['status'], session_id=event['session_id'])
            if len(matches) != 1 or any(_canon(content.get(k)) != _canon(v) for k, v in expected.items()):
                raise ValueError("agenda graph projection mismatch; reconciliation required")
            parents = set(event['need'].get('source_glyph_ids', ()))
            if counts[nid] > 1:
                prior = self.graph.ledger.find_by_external_ref(
                    f"need-state:{nid}:{counts[nid] - 1}", glyph_type='goal')[0]
                parents.add(prior.glyph_id)
                supersedes = {e.target for e in self.graph.ledger.edges_from(matches[0].glyph_id, relation='supersedes')}
                if prior.glyph_id not in supersedes:
                    raise ValueError("agenda graph links incomplete; reconciliation required")
            derived = {e.target for e in self.graph.ledger.edges_from(matches[0].glyph_id, relation='derived_from')}
            if not parents <= derived:
                raise ValueError("agenda graph links incomplete; reconciliation required")

    def _append(self, *, need: ResearchNeed, status: str,
                session_id: Optional[str] = None, reason: Optional[str] = None) -> NeedState:
        self._recover_pending()
        current = self.get_optional(need.need_id)
        if current is not None:
            if _canon(self._need_payload(current.need)) != _canon(self._need_payload(need)):
                raise ValueError("conflicting research need payload")
            last = [e for e in self._events() if e['need']['need_id'] == need.need_id][-1]
            if (current.status == status and current.session_id == session_id
                    and last['reason'] == reason):
                return current
            sequence = current.event_count + 1
        else:
            sequence = 1
        allowed = {None: {'pending'}, 'pending': {'researched', 'cancelled', 'deferred'},
                   'researched': {'evaluated'}}
        if status not in allowed.get(current.status if current else None, set()):
            raise ValueError("invalid agenda lifecycle transition")
        # Reject bad provenance before even creating a durable intent.
        for parent_id in need.source_glyph_ids:
            self.graph.ledger.get(parent_id)
        event = self._event_for(need, status, session_id, reason, sequence)
        intent = self._write_intent(event)
        try:
            self._apply_intent(event)
        except Exception:
            # Leave the durable intent for a subsequent process to replay.
            raise
        intent.unlink(missing_ok=True)
        return self.get(need.need_id)

    def add(self, need: ResearchNeed) -> NeedState:
        self._recover_pending()
        current = self.get_optional(need.need_id)
        if current is not None:
            if _canon(self._need_payload(current.need)) != _canon(self._need_payload(need)):
                raise ValueError("conflicting research need payload")
            return current
        return self._append(need=need, status="pending")

    def _decode_need(self, raw: Mapping[str, Any]) -> ResearchNeed:
        item = dict(raw)
        item["measurements"] = AttentionMeasurements(**item["measurements"])
        item["source_glyph_ids"] = tuple(item.get("source_glyph_ids", ()))
        return ResearchNeed(**item)

    def get_optional(self, need_id: str) -> Optional[NeedState]:
        events = [event for event in self._events() if event["need"]["need_id"] == need_id]
        if not events:
            return None
        last = events[-1]
        return NeedState(need=self._decode_need(last["need"]), status=last["status"],
                         session_id=last["session_id"], event_count=len(events))

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
        return tuple(state for state in (self.get(nid) for nid in ids) if state.status == "pending")

    def select_next(self) -> Optional[NeedState]:
        candidates = self.pending()
        if not candidates:
            return None
        return sorted(candidates, key=lambda state: (-score_attention(state.need.measurements, self.weights), state.need.need_id))[0]

    def mark_researched(self, need_id: str, session_id: str) -> NeedState:
        current = self.get(need_id)
        if current.status != "pending":
            raise ValueError("only pending needs may be researched")
        return self._append(need=current.need, status="researched", session_id=session_id)

    def mark_evaluated(self, need_id: str) -> NeedState:
        current = self.get(need_id)
        if current.status != "researched":
            raise ValueError("only researched needs may be evaluated")
        return self._append(need=current.need, status="evaluated", session_id=current.session_id)

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
        return self._append(need=current.need, status="deferred", reason=reason)


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
        self._attempt_path = self.agenda.path.with_name(self.agenda.path.name + ".roam-attempt.json")
        # Recovery runs at the operation boundary, before hooks or a new tick.

    def _write_attempt(self, payload: Mapping[str, Any]) -> None:
        """Atomically persist the single-writer external-call receipt."""
        body = dict(payload)
        body["schema"] = "syn-roam-controller-attempt-v1"
        body["digest"] = _hash({k: v for k, v in body.items() if k != "digest"})
        temporary = self._attempt_path.with_suffix(self._attempt_path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as fh:
            fh.write(_canon(body))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, self._attempt_path)

    def _read_attempt(self) -> Optional[dict[str, Any]]:
        if not self._attempt_path.exists():
            return None
        try:
            raw = json.loads(self._attempt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError("ROAM controller attempt receipt requires operator review") from exc
        if not isinstance(raw, dict) or raw.get("schema") != "syn-roam-controller-attempt-v1":
            raise RuntimeError("ROAM controller attempt receipt requires operator review")
        digest = raw.get("digest")
        if not isinstance(digest, str) or digest != _hash({k: v for k, v in raw.items() if k != "digest"}):
            raise RuntimeError("ROAM controller attempt receipt requires operator review")
        if raw.get("phase") not in {"started", "completed"} or not isinstance(raw.get("need_id"), str):
            raise RuntimeError("ROAM controller attempt receipt requires operator review")
        if (type(raw.get("sequence")) is not int or raw["sequence"] < 1
                or not isinstance(raw.get("need_digest"), str)
                or not raw["need_id"]):
            raise RuntimeError("ROAM controller attempt receipt requires operator review")
        if raw.get("phase") == "completed" and (not isinstance(raw.get("session_id"), str) or not raw["session_id"]):
            raise RuntimeError("ROAM controller attempt receipt requires operator review")
        return raw

    def _reconcile_attempt(self) -> None:
        receipt = self._read_attempt()
        if receipt is None:
            return
        if receipt["phase"] == "started":
            raise RuntimeError("ROAM research attempt outcome is unknown; operator review required")
        state = self.agenda.get_optional(receipt["need_id"])
        if state is None or _hash(self.agenda._need_payload(state.need)) != receipt.get("need_digest"):
            raise RuntimeError("conflicting ROAM controller completion receipt")
        sid = receipt["session_id"]
        increment = {"pending": 0, "researched": 1, "evaluated": 2}.get(state.status)
        if increment is None or receipt["sequence"] + increment != state.event_count:
            raise RuntimeError("conflicting ROAM controller completion receipt")
        if state.status == "pending":
            self.agenda.mark_researched(receipt["need_id"], sid)
        elif state.status in {"researched", "evaluated"} and state.session_id == sid:
            pass
        else:
            raise RuntimeError("conflicting ROAM controller completion receipt")
        self._attempt_path.unlink(missing_ok=True)

    def add_tick_hook(self, hook):
        if hook not in self._tick_hooks:
            self._tick_hooks.append(hook)

    def add_need_guard(self, guard):
        if guard not in self._need_guards:
            self._need_guards.append(guard)

    def tick_once(self) -> RoamTick:
        self._reconcile_attempt()
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
        self._write_attempt({"phase": "started", "need_id": selected.need.need_id,
                             "need_digest": _hash(self.agenda._need_payload(selected.need)),
                             "sequence": selected.event_count})
        session = self.roam.research_once(question)
        self._write_attempt({"phase": "completed", "need_id": selected.need.need_id,
                             "need_digest": _hash(self.agenda._need_payload(selected.need)),
                             "sequence": selected.event_count,
                             "session_id": session.session_id})
        self._reconcile_attempt()
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
