"""Synergesis Living Kernel: persistent blackboard + episodic memory + reflexive cycle.

This module does not claim consciousness. It provides the executable machinery for
identity, state, memory, observation, validation, and deterministic self-reflection.
No missing value is fabricated.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Observation:
    kind: str
    payload: Mapping[str, Any]
    timestamp: str
    source: str
    digest: str

    @classmethod
    def create(cls, kind: str, payload: Mapping[str, Any], source: str) -> "Observation":
        if not kind.strip() or not source.strip():
            raise ValueError("kind and source are required")
        ts = datetime.now(timezone.utc).isoformat()
        body = {"kind": kind, "payload": dict(payload), "timestamp": ts, "source": source}
        return cls(kind, dict(payload), ts, source, _digest(body))


@dataclass
class MemoryRecord:
    record_id: str
    kind: str
    payload: Dict[str, Any]
    created_at: str
    source: str
    digest: str


class PersistentMemory:
    """Append-only JSONL memory with deterministic integrity digests."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, kind: str, payload: Mapping[str, Any], source: str) -> MemoryRecord:
        now = datetime.now(timezone.utc).isoformat()
        body = {"kind": kind, "payload": dict(payload), "created_at": now, "source": source}
        digest = _digest(body)
        record = MemoryRecord(digest[:16], kind, dict(payload), now, source, digest)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical_json(asdict(record)) + "\n")
        return record

    def read_all(self) -> List[MemoryRecord]:
        if not self.path.exists():
            return []
        records: List[MemoryRecord] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                data = json.loads(line)
                record = MemoryRecord(**data)
                body = {"kind": record.kind, "payload": record.payload,
                        "created_at": record.created_at, "source": record.source}
                if _digest(body) != record.digest:
                    raise ValueError(f"Memory integrity failure for {record.record_id}")
                records.append(record)
        return records


@dataclass
class Blackboard:
    """Versioned shared workspace. Writes are explicit and auditable."""
    state: Dict[str, Any] = field(default_factory=dict)
    version: int = 0

    def publish(self, key: str, value: Any) -> int:
        if not key.strip():
            raise ValueError("blackboard key is required")
        self.state[key] = value
        self.version += 1
        return self.version

    def snapshot(self) -> Dict[str, Any]:
        return json.loads(_canonical_json(self.state))


@dataclass(frozen=True)
class ReflexiveReport:
    cycle: int
    state_digest: str
    observation_count: int
    memory_count: int
    changes: List[str]
    anomalies: List[str]


class SynKernel:
    """Executable identity/state loop for Synergesis."""
    def __init__(self, identity: str, memory: PersistentMemory):
        if not identity.strip():
            raise ValueError("identity is required")
        self.identity = identity
        self.memory = memory
        self.blackboard = Blackboard()
        self.cycle = 0
        self._observations: List[Observation] = []
        self._last_snapshot: Dict[str, Any] = {}

    def observe(self, kind: str, payload: Mapping[str, Any], source: str) -> Observation:
        obs = Observation.create(kind, payload, source)
        self._observations.append(obs)
        self.memory.append("observation", asdict(obs), self.identity)
        self.blackboard.publish(f"observation:{obs.digest[:16]}", asdict(obs))
        return obs

    def reflect(self) -> ReflexiveReport:
        before = self._last_snapshot
        records = self.memory.read_all()
        anomalies: List[str] = []
        if any(not r.digest for r in records):
            anomalies.append("memory_record_without_integrity_digest")
        current = self.blackboard.snapshot()
        changes = sorted(k for k in current if before.get(k) != current.get(k))
        self._last_snapshot = current
        self.cycle += 1
        state = {"identity": self.identity, "cycle": self.cycle, "blackboard": current,
                 "memory_count": len(records)}
        digest = _digest(state)
        self.memory.append("reflexive_cycle", {"cycle": self.cycle, "state_digest": digest,
                                                "changes": changes, "anomalies": anomalies}, self.identity)
        return ReflexiveReport(self.cycle, digest, len(self._observations), len(records), changes, anomalies)
