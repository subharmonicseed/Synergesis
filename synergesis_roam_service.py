"""Finite service runner for continuous SYN-ROAM deployments.

This module is intentionally process-manager friendly: it offers one tick and a
finite batch, never an unbounded ``while True``. A systemd timer, Kubernetes
CronJob, supervisor, or another authorized scheduler can invoke finite batches
continuously while retaining an external kill switch.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import os
from typing import Any, Mapping, Optional, Tuple

from synergesis_roam_attention import RoamAttentionController, RoamTick
from synergesis_storage_lock import PathTransaction


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RoamServiceLimits:
    max_ticks_per_batch: int
    stop_when_idle: bool

    def __post_init__(self):
        if self.max_ticks_per_batch < 1:
            raise ValueError("max_ticks_per_batch must be >= 1")


@dataclass(frozen=True)
class ServiceTickRecord:
    sequence: int
    status: str
    need_id: Optional[str]
    session_id: Optional[str]
    previous_digest: Optional[str]
    digest: str


def _validate_record(record: ServiceTickRecord) -> None:
    body = asdict(record)
    digest = body.pop("digest")
    if digest != _hash(body):
        raise ValueError("roam service ledger integrity failure")
    if type(record.sequence) is not int or record.sequence < 1:
        raise ValueError("roam service ledger sequence failure")
    if record.previous_digest is not None and (
        not isinstance(record.previous_digest, str)
        or len(record.previous_digest) != 64
        or any(c not in "0123456789abcdef" for c in record.previous_digest)
    ):
        raise ValueError("roam service ledger chain failure")
    if record.status not in {"idle", "cancelled", "researched"}:
        raise ValueError("invalid roam service tick status")
    if record.status == "idle":
        valid = record.need_id is None and record.session_id is None
    elif record.status == "cancelled":
        valid = isinstance(record.need_id, str) and bool(record.need_id) and record.session_id is None
    else:
        valid = all(isinstance(value, str) and bool(value)
                    for value in (record.need_id, record.session_id))
    if not valid:
        raise ValueError("invalid roam service tick identity")


class RoamServiceLedger:
    """Tamper-evident record of service ticks."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = PathTransaction(self.path, label="roam service ledger")

    def transaction(self):
        """Return the ledger's reentrant process and thread transaction."""
        return self._lock

    def _raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def records(self) -> Tuple[ServiceTickRecord, ...]:
        with self.transaction():
            previous = None
            out = []
            for index, raw in enumerate(self._raw(), start=1):
                record = ServiceTickRecord(**raw)
                if record.sequence != index:
                    raise ValueError("roam service ledger sequence failure")
                if record.previous_digest != previous:
                    raise ValueError("roam service ledger chain failure")
                body = {
                    "sequence": record.sequence,
                    "status": record.status,
                    "need_id": record.need_id,
                    "session_id": record.session_id,
                    "previous_digest": record.previous_digest,
                }
                if _hash(body) != record.digest:
                    raise ValueError("roam service ledger integrity failure")
                _validate_record(record)
                out.append(record)
                previous = record.digest
            return tuple(out)

    def append(self, tick: RoamTick) -> ServiceTickRecord:
        with self.transaction():
            records = self.records()
            body = {
                "sequence": len(records) + 1,
                "status": tick.status,
                "need_id": tick.need_id,
                "session_id": tick.session.session_id if tick.session else None,
                "previous_digest": records[-1].digest if records else None,
            }
            record = ServiceTickRecord(**body, digest=_hash(body))
            return self.append_record(record)

    def append_record(self, record: ServiceTickRecord) -> ServiceTickRecord:
        with self.transaction():
            _validate_record(record)
            records = self.records()
            if record.sequence <= len(records):
                if records[record.sequence - 1] != record:
                    raise ValueError("conflicting roam service receipt")
                return record
            if record.sequence != len(records) + 1:
                raise ValueError("roam service ledger sequence failure")
            if record.previous_digest != (records[-1].digest if records else None):
                raise ValueError("roam service ledger chain failure")
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(_canon(asdict(record)) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return record


class SynRoamService:
    def __init__(
        self,
        *,
        controller: RoamAttentionController,
        ledger: RoamServiceLedger,
        limits: RoamServiceLimits,
    ):
        self.controller = controller
        self.ledger = ledger
        self.limits = limits
        self._attempt_path = self.ledger.path.with_name(self.ledger.path.name + ".roam-attempt.json").resolve()
        # Recovery runs at the operation boundary, before hooks or a new tick.

    def _write_attempt(self, payload: Mapping[str, Any]) -> None:
        body = dict(payload)
        body["schema"] = "syn-roam-service-attempt-v1"
        body["digest"] = _hash(body)
        temporary = self._attempt_path.with_suffix(self._attempt_path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as fh:
            fh.write(_canon(body))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, self._attempt_path)

    def _read_attempt(self) -> Optional[ServiceTickRecord]:
        if not self._attempt_path.exists():
            return None
        try:
            raw = json.loads(self._attempt_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise RuntimeError("ROAM service receipt requires operator review") from exc
        if not isinstance(raw, dict) or raw.get("schema") != "syn-roam-service-attempt-v1":
            raise RuntimeError("ROAM service receipt requires operator review")
        if raw.get("digest") != _hash({k: v for k, v in raw.items() if k != "digest"}):
            raise RuntimeError("ROAM service receipt requires operator review")
        if raw.get("phase") == "started":
            raise RuntimeError("ROAM service tick outcome is unknown; operator review required")
        if raw.get("phase") != "completed" or not isinstance(raw.get("record"), dict):
            raise RuntimeError("ROAM service receipt requires operator review")
        try:
            record = ServiceTickRecord(**raw["record"])
            _validate_record(record)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("ROAM service receipt requires operator review") from exc
        return record

    def _reconcile_attempt(self) -> None:
        record = self._read_attempt()
        if record is None:
            return
        self.ledger.append_record(record)
        self._attempt_path.unlink(missing_ok=True)

    def tick_once(self) -> RoamTick:
        # Keep the receipt, controller, and ledger append in one service
        # transaction. The controller acquires the agenda transaction inside
        # this block, preserving service -> agenda lock ordering.
        with self.ledger.transaction():
            self._reconcile_attempt()
            records = self.ledger.records()
            sequence = len(records) + 1
            previous = records[-1].digest if records else None
            self._write_attempt({"phase": "started", "sequence": sequence,
                                 "previous_digest": previous})
            tick = self.controller.tick_once()
            body = {"sequence": sequence, "status": tick.status,
                    "need_id": tick.need_id,
                    "session_id": tick.session.session_id if tick.session else None,
                    "previous_digest": previous}
            record = ServiceTickRecord(**body, digest=_hash(body))
            _validate_record(record)
            self._write_attempt({"phase": "completed", "record": asdict(record)})
            # The completed receipt can replay this local append without calling
            # the controller again. Cooperating writers wait for this transaction.
            if self.ledger.records() != records:
                raise RuntimeError("ROAM service ledger changed during tick; operator review required")
            if self.ledger.append(tick) != record:
                raise RuntimeError("conflicting ROAM service completion record")
            self._attempt_path.unlink(missing_ok=True)
            return tick

    def run_bounded(self) -> Tuple[RoamTick, ...]:
        ticks = []
        for _ in range(self.limits.max_ticks_per_batch):
            tick = self.tick_once()
            ticks.append(tick)
            if self.limits.stop_when_idle and tick.status == "idle":
                break
        return tuple(ticks)
