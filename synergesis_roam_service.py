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
from typing import Any, Mapping, Optional, Tuple

from synergesis_roam_attention import RoamAttentionController, RoamTick


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


class RoamServiceLedger:
    """Tamper-evident record of service ticks."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def records(self) -> Tuple[ServiceTickRecord, ...]:
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
            out.append(record)
            previous = record.digest
        return tuple(out)

    def append(self, tick: RoamTick) -> ServiceTickRecord:
        records = self.records()
        body = {
            "sequence": len(records) + 1,
            "status": tick.status,
            "need_id": tick.need_id,
            "session_id": tick.session.session_id if tick.session else None,
            "previous_digest": records[-1].digest if records else None,
        }
        record = ServiceTickRecord(**body, digest=_hash(body))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(asdict(record)) + "\n")
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

    def tick_once(self) -> RoamTick:
        tick = self.controller.tick_once()
        self.ledger.append(tick)
        return tick

    def run_bounded(self) -> Tuple[RoamTick, ...]:
        ticks = []
        for _ in range(self.limits.max_ticks_per_batch):
            tick = self.tick_once()
            ticks.append(tick)
            if self.limits.stop_when_idle and tick.status == "idle":
                break
        return tuple(ticks)
