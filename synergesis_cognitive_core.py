"""Synergesis cognitive core: semantic memory, world model, and deterministic orchestration.

No consciousness claim. This module turns the documented NOUS/SELENE/THALES/DeepResearch
architecture into explicit, auditable state transitions. Missing evidence is not fabricated.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(x: Any) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _hash(x: Any) -> str:
    return sha256(_canon(x).encode()).hexdigest()


@dataclass(frozen=True)
class Fact:
    subject: str
    predicate: str
    object: str
    source: str
    confidence: float
    observed_at: str
    evidence_id: str

    def __post_init__(self):
        if not self.subject.strip() or not self.predicate.strip() or not self.object.strip():
            raise ValueError("subject, predicate and object are required")
        if not self.source.strip():
            raise ValueError("source is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")


class SemanticMemory:
    """SQLite-free, append-only semantic memory suitable for deterministic tests."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._facts: Dict[str, Fact] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                f = Fact(**json.loads(line))
                self._facts[f.evidence_id] = f

    def add(self, fact: Fact) -> Fact:
        if fact.evidence_id in self._facts:
            existing = self._facts[fact.evidence_id]
            if existing != fact:
                raise ValueError("evidence_id collision with different fact")
            return existing
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(asdict(fact)) + "\n")
        self._facts[fact.evidence_id] = fact
        return fact

    def query(self, subject: Optional[str] = None, predicate: Optional[str] = None,
              object: Optional[str] = None) -> List[Fact]:
        vals = list(self._facts.values())
        return [f for f in vals if
                (subject is None or f.subject == subject) and
                (predicate is None or f.predicate == predicate) and
                (object is None or f.object == object)]

    def count(self) -> int:
        return len(self._facts)


@dataclass(frozen=True)
class WorldState:
    version: int
    facts: Tuple[Fact, ...]
    digest: str
    provisional_beliefs: Tuple[Any, ...] = ()


class WorldModel:
    """Materialized, immutable snapshots over semantic memory."""
    def __init__(self, memory: SemanticMemory):
        self.memory = memory
        self.version = 0
        self.provisional_beliefs = None

    def snapshot(self) -> WorldState:
        facts = tuple(sorted(self.memory.query(), key=lambda f: f.evidence_id))
        self.version += 1
        payload = {"version": self.version, "facts": [asdict(f) for f in facts]}
        provisional = self.provisional_beliefs.active() if self.provisional_beliefs is not None else ()
        if self.provisional_beliefs is not None:
            payload["provisional_beliefs"] = [asdict(belief) for belief in provisional]
        return WorldState(self.version, facts, _hash(payload), provisional)


@dataclass(frozen=True)
class IntegrityReport:
    valid: bool
    fact_count: int
    duplicate_ids: Tuple[str, ...]
    invalid_confidences: Tuple[str, ...]


class Selene:
    """Memory/monitoring layer: detects gaps and integrity problems without inventing facts."""
    def __init__(self, memory: SemanticMemory):
        self.memory = memory

    def integrity(self) -> IntegrityReport:
        duplicate_ids: List[str] = []
        invalid: List[str] = []
        seen = set()
        for f in self.memory.query():
            if f.evidence_id in seen:
                duplicate_ids.append(f.evidence_id)
            seen.add(f.evidence_id)
            if not 0.0 <= f.confidence <= 1.0:
                invalid.append(f.evidence_id)
        return IntegrityReport(not duplicate_ids and not invalid, self.memory.count(),
                               tuple(duplicate_ids), tuple(invalid))

    def gaps(self, required_predicates: Iterable[str]) -> List[str]:
        existing = {f.predicate for f in self.memory.query()}
        return sorted(set(required_predicates) - existing)


@dataclass(frozen=True)
class Rule:
    name: str
    predicate: str
    required_object: str
    conclusion_predicate: str
    conclusion_object: str


@dataclass(frozen=True)
class Inference:
    rule: str
    premise_ids: Tuple[str, ...]
    conclusion: Fact


class Thales:
    """Small explicit rule engine with auditable inference chains."""
    def infer(self, memory: SemanticMemory, rules: Iterable[Rule]) -> List[Inference]:
        out: List[Inference] = []
        for rule in rules:
            for premise in memory.query(predicate=rule.predicate, object=rule.required_object):
                body = {"rule": rule.name, "premise": premise.evidence_id,
                        "subject": premise.subject, "predicate": rule.conclusion_predicate,
                        "object": rule.conclusion_object}
                evidence_id = _hash(body)
                conclusion = Fact(premise.subject, rule.conclusion_predicate, rule.conclusion_object,
                                  source=f"THALES:{rule.name}",
                                  confidence=premise.confidence,
                                  observed_at=_now(), evidence_id=evidence_id)
                out.append(Inference(rule.name, (premise.evidence_id,), conclusion))
        return out


@dataclass(frozen=True)
class CognitiveCycle:
    cycle: int
    world_digest: str
    memory_count: int
    integrity_valid: bool
    inferred_count: int
    gaps: Tuple[str, ...]


class SynCognitiveCore:
    """Connects persistent memory, world model, SELENE monitoring and THALES inference."""
    def __init__(self, memory_path: str | Path):
        self.memory = SemanticMemory(memory_path)
        self.world = WorldModel(self.memory)
        self.selene = Selene(self.memory)
        self.thales = Thales()
        self.cycle = 0

    def remember(self, subject: str, predicate: str, object: str, source: str,
                 confidence: float, evidence_id: Optional[str] = None) -> Fact:
        if evidence_id is None:
            evidence_id = _hash({"subject": subject, "predicate": predicate,
                                 "object": object, "source": source})
        return self.memory.add(Fact(subject, predicate, object, source, confidence,
                                     _now(), evidence_id))

    def cycle_once(self, rules: Iterable[Rule] = (), required_predicates: Iterable[str] = ()) -> CognitiveCycle:
        integrity = self.selene.integrity()
        inferred = self.thales.infer(self.memory, rules)
        for item in inferred:
            self.memory.add(item.conclusion)
        world = self.world.snapshot()
        self.cycle += 1
        return CognitiveCycle(self.cycle, world.digest, self.memory.count(),
                              integrity.valid, len(inferred),
                              tuple(self.selene.gaps(required_predicates)))
