"""SYN-CURIOSITY: bounded, inspectable curiosity proposals and knowledge-gap journal.

No model, network, scheduler, or new execution permission is created here.
Proposals come from the existing, validated ResearchAgenda; research outcomes
require supplied sources and remain explicitly unverified by this component.
The JSON entry contract is shared with scheduled ChatGPT research reports.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

from synergesis_roam_attention import ResearchAgenda, score_attention
from synergesis_storage_lock import PathTransaction


SCHEMA = "syn-curiosity-v1"
MAX_ENTRY_BYTES = 16_384
MAX_JOURNAL_BYTES = 16_777_216
MAX_RECORDS = 2_048
STAGES = frozenset({"proposed", "assessed", "blocked"})
MODES = frozenset({"directed", "emergent", "adversarial", "unclassified"})
GAPS = frozenset({
    "prediction_error", "contradiction", "staleness", "missing_domain",
    "unverified", "unknown",
})
OUTCOMES = frozenset({"not_tested", "supported", "refuted", "inconclusive"})


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unit(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return number


def validate_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the public, cross-channel record; return JSON-safe canonical data."""
    if not isinstance(raw, Mapping):
        raise ValueError("entry must be a mapping")
    required = {
        "schema", "entry_id", "observed_at", "producer", "stage",
        "domain", "question", "reason", "hypothesis", "need_id",
        "research_mode", "gap_kind", "metrics", "evidence_refs",
        "outcome", "uncertainty_after", "learning",
    }
    if set(raw) != required:
        raise ValueError("curiosity entry has missing or unknown fields")
    entry = dict(raw)
    if entry["schema"] != SCHEMA:
        raise ValueError("unsupported curiosity schema")
    for key in ("entry_id", "producer", "domain", "question", "reason"):
        value = entry[key]
        if not isinstance(value, str) or not value.strip() or len(value) > 2_048:
            raise ValueError(f"invalid {key}")
    if entry["producer"] not in {"syn", "chatgpt"}:
        raise ValueError("unknown curiosity producer")
    if entry["stage"] not in STAGES or entry["research_mode"] not in MODES:
        raise ValueError("invalid curiosity stage or research mode")
    if entry["gap_kind"] not in GAPS or entry["outcome"] not in OUTCOMES:
        raise ValueError("invalid gap kind or outcome")
    for key in ("hypothesis", "need_id", "learning"):
        value = entry[key]
        if value is not None and (not isinstance(value, str) or len(value) > 4_096):
            raise ValueError(f"invalid {key}")
    try:
        parsed = datetime.fromisoformat(entry["observed_at"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive timestamp")
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("observed_at requires a timezone-aware ISO timestamp") from exc
    metrics = entry["metrics"]
    if not isinstance(metrics, Mapping) or set(metrics) != {
        "uncertainty", "expected_impact", "staleness", "novelty_gap",
        "selection_score",
    }:
        raise ValueError("invalid curiosity metrics")
    entry["metrics"] = {name: _unit(value, name) for name, value in metrics.items()}
    after = entry["uncertainty_after"]
    if after is not None:
        entry["uncertainty_after"] = _unit(after, "uncertainty_after")
    refs = entry["evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 10:
        raise ValueError("evidence_refs must be a bounded list")
    for ref in refs:
        if not isinstance(ref, str) or len(ref) > 1_024 or not ref.startswith("https://"):
            raise ValueError("evidence refs must be HTTPS URLs")
    if entry["stage"] == "proposed":
        if entry["outcome"] != "not_tested" or after is not None or refs:
            raise ValueError("unresearched proposal cannot claim an observation")
    elif entry["stage"] == "assessed":
        if not refs or entry["outcome"] == "not_tested" or after is None:
            raise ValueError("assessments require sources, outcome and uncertainty")
    elif entry["outcome"] != "not_tested":
        raise ValueError("blocked entries cannot claim a verified outcome")
    if len(_canonical(entry).encode("utf-8")) > MAX_ENTRY_BYTES:
        raise ValueError("curiosity entry too large")
    return json.loads(_canonical(entry))


class CuriosityJournal:
    """Bounded, hash-linked JSONL. Only cooperating writers are serialized."""

    def __init__(self, path: str | Path):
        self.path = Path(path).absolute()
        if self.path.is_symlink():
            raise ValueError("journal path must not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = PathTransaction(self.path, label="curiosity journal")

    def records(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            if self.path.is_symlink():
                raise ValueError("journal path must not be a symlink")
            if not self.path.exists():
                return ()
            if self.path.stat().st_size > MAX_JOURNAL_BYTES:
                raise ValueError("curiosity journal exceeds size cap")
            out = []
            previous = None
            seen = set()
            with self.path.open("r", encoding="utf-8") as stream:
                for number, line in enumerate(stream, 1):
                    if number > MAX_RECORDS or not line.endswith("\n"):
                        raise ValueError("journal is too large or has partial record")
                    envelope = json.loads(line)
                    if set(envelope) != {"sequence", "previous_hash", "entry", "sha256"}:
                        raise ValueError("invalid curiosity envelope")
                    entry = validate_entry(envelope["entry"])
                    body = {
                        "sequence": number,
                        "previous_hash": previous,
                        "entry": entry,
                    }
                    if (type(envelope["sequence"]) is not int
                            or envelope["sequence"] != number
                            or envelope["previous_hash"] != previous
                            or envelope["sha256"] != _digest(body)):
                        raise ValueError("curiosity journal integrity failure")
                    if entry["entry_id"] in seen:
                        raise ValueError("duplicate curiosity entry id")
                    seen.add(entry["entry_id"])
                    out.append(entry)
                    previous = envelope["sha256"]
            return tuple(out)

    def append(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        entry = validate_entry(raw)
        with self._lock:
            records = self.records()
            for old in records:
                if old["entry_id"] == entry["entry_id"]:
                    if old != entry:
                        raise ValueError("conflicting curiosity idempotency key")
                    return old
            if len(records) >= MAX_RECORDS:
                raise ValueError("curiosity journal full; archive manually")
            previous = None
            if self.path.exists() and self.path.stat().st_size:
                with self.path.open("rb") as stream:
                    lines = stream.readlines()
                previous = json.loads(lines[-1])["sha256"]
            body = {
                "sequence": len(records) + 1,
                "previous_hash": previous,
                "entry": entry,
            }
            envelope = {**body, "sha256": _digest(body)}
            if self.path.is_symlink():
                raise ValueError("journal path must not be a symlink")
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(_canonical(envelope) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            return entry

    def import_report(self, path: str | Path) -> dict[str, Any]:
        """Ingest one explicitly supplied, public ChatGPT JSON report. No download."""
        incoming = Path(path)
        if incoming.is_symlink() or not incoming.is_file() or incoming.stat().st_size > MAX_ENTRY_BYTES:
            raise ValueError("report file is invalid or too large")
        raw = json.loads(incoming.read_text(encoding="utf-8"))
        return self.append(raw)

    def summary(self) -> dict[str, Any]:
        records = self.records()
        assessed = [r for r in records if r["stage"] == "assessed"]
        gains = [
            r["metrics"]["uncertainty"] - r["uncertainty_after"]
            for r in assessed
        ]
        return {
            "total_events": len(records),
            "proposals": sum(r["stage"] == "proposed" for r in records),
            "assessments": len(assessed),
            "refutations": sum(r["outcome"] == "refuted" for r in assessed),
            "average_signed_uncertainty_reduction": (
                sum(gains) / len(gains) if gains else None
            ),
            "domains": dict(sorted(Counter(r["domain"] for r in records).items())),
        }


class CuriosityObserver:
    """Rank existing research needs; make auditable proposals, never run them."""

    def __init__(self, journal: CuriosityJournal):
        self.journal = journal

    def propose(self, agenda: ResearchAgenda, *, limit: int = 3,
                modes: Mapping[str, str] | None = None,
                gap_kinds: Mapping[str, str] | None = None,
                clock=None) -> tuple[dict[str, Any], ...]:
        if type(limit) is not int or not 1 <= limit <= 3:
            raise ValueError("proposal limit must be between one and three")
        modes = modes or {}
        gap_kinds = gap_kinds or {}
        existing = {row["entry_id"]: row for row in self.journal.records()}
        candidates = sorted(
            agenda.pending(),
            key=lambda state: (
                -score_attention(state.need.measurements, agenda.weights),
                state.need.need_id,
            ),
        )
        result = []
        for state in candidates[:limit]:
            need = state.need
            mode = modes.get(need.need_id, "unclassified")
            gap = gap_kinds.get(need.need_id, "unknown")
            if mode not in MODES or gap not in GAPS:
                raise ValueError("invalid external curiosity classification")
            eid = "syn-proposal:" + _digest({"need_id": need.need_id})[:24]
            if eid in existing:
                result.append(existing[eid])
                continue
            metrics = {
                "uncertainty": need.measurements.uncertainty,
                "expected_impact": need.measurements.expected_impact,
                "staleness": need.measurements.staleness,
                "novelty_gap": need.measurements.novelty_gap,
                "selection_score": score_attention(need.measurements, agenda.weights),
            }
            timestamp = clock() if clock is not None else datetime.now(timezone.utc)
            entry = {
                "schema": SCHEMA,
                "entry_id": eid,
                "observed_at": timestamp.isoformat(),
                "producer": "syn",
                "stage": "proposed",
                "domain": need.domain,
                "question": need.question,
                "reason": need.reason,
                "hypothesis": need.hypothesis,
                "need_id": need.need_id,
                "research_mode": mode,
                "gap_kind": gap,
                "metrics": metrics,
                "evidence_refs": [],
                "outcome": "not_tested",
                "uncertainty_after": None,
                "learning": None,
            }
            result.append(self.journal.append(entry))
        return tuple(result)
