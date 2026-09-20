"""Auditable research, creativity, drift monitoring, and gateway orchestration for Syn.

External content is evidence, not knowledge. Nothing enters semantic memory without
explicit validation/approval. No random generation, fabricated confidence, or silent defaults.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from synergesis_cognitive_core import Fact, SemanticMemory, _canon, _hash


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    title: str
    content: str
    retrieved_at: str
    source_type: str

    def __post_init__(self):
        if not self.evidence_id.strip() or not self.source.strip() or not self.content.strip():
            raise ValueError("evidence_id, source and content are required")
        if not self.source_type.strip():
            raise ValueError("source_type is required")


@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    evidence_ids: Tuple[str, ...]
    status: str
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None

    def __post_init__(self):
        if not self.statement.strip() or not self.claim_id.strip():
            raise ValueError("claim_id and statement are required")
        if self.status not in {"candidate", "approved", "rejected"}:
            raise ValueError("invalid claim status")
        if self.status == "approved" and (not self.reviewer or not self.reviewed_at):
            raise ValueError("approved claims require reviewer and reviewed_at")


class EvidenceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, Evidence] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = Evidence(**json.loads(line))
                self._items[e.evidence_id] = e

    def add(self, evidence: Evidence) -> Evidence:
        old = self._items.get(evidence.evidence_id)
        if old is not None and old != evidence:
            raise ValueError("evidence_id collision with different evidence")
        if old is not None:
            return old
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(asdict(evidence)) + "\n")
        self._items[evidence.evidence_id] = evidence
        return evidence

    def get(self, evidence_id: str) -> Evidence:
        try:
            return self._items[evidence_id]
        except KeyError as exc:
            raise KeyError(f"unknown evidence: {evidence_id}") from exc

    def all(self) -> Tuple[Evidence, ...]:
        return tuple(self._items.values())


class DeepResearch:
    """Turns supplied external material into auditable evidence and claim candidates."""
    def __init__(self, store: EvidenceStore):
        self.store = store
        self._claims: dict[str, Claim] = {}

    def ingest(self, source: str, title: str, content: str, source_type: str) -> Evidence:
        eid = _hash({"source": source, "title": title, "content": content})
        return self.store.add(Evidence(eid, source, title, content, _now(), source_type))

    def propose_claim(self, statement: str, evidence_ids: Sequence[str]) -> Claim:
        if not evidence_ids:
            raise ValueError("claim requires at least one evidence id")
        for eid in evidence_ids:
            try:
                self.store.get(eid)
            except KeyError as exc:
                raise ValueError(f"unknown evidence: {eid}") from exc
        cid = _hash({"statement": statement, "evidence_ids": list(evidence_ids)})
        claim = Claim(cid, statement, tuple(evidence_ids), "candidate")
        self._claims[cid] = claim
        return claim

    def approve(self, claim_id: str, reviewer: str) -> Claim:
        claim = self._claims[claim_id]
        approved = Claim(claim.claim_id, claim.statement, claim.evidence_ids,
                         "approved", reviewer=reviewer, reviewed_at=_now())
        self._claims[claim_id] = approved
        return approved

    def reject(self, claim_id: str, reviewer: str) -> Claim:
        claim = self._claims[claim_id]
        rejected = Claim(claim.claim_id, claim.statement, claim.evidence_ids,
                         "rejected", reviewer=reviewer, reviewed_at=_now())
        self._claims[claim_id] = rejected
        return rejected

    def commit_approved_claim(self, claim_id: str, memory: SemanticMemory,
                              subject: str, predicate: str, object: str,
                              confidence: float) -> Fact:
        claim = self._claims[claim_id]
        if claim.status != "approved":
            raise ValueError("only approved claims may enter semantic memory")
        evidence_ref = ",".join(claim.evidence_ids)
        fid = _hash({"claim": claim.claim_id, "subject": subject,
                     "predicate": predicate, "object": object})
        return memory.add(Fact(subject, predicate, object,
                               source=f"DeepResearch:{evidence_ref}",
                               confidence=confidence, observed_at=_now(), evidence_id=fid))


@dataclass(frozen=True)
class DriftReport:
    compared: int
    changed: int
    change_rate: float
    changed_ids: Tuple[str, ...]


class SynEcho:
    """Deterministic symbolic drift detector over two snapshots."""
    def compare(self, previous: Sequence[Fact], current: Sequence[Fact]) -> DriftReport:
        old = {f.evidence_id: _canon(asdict(f)) for f in previous}
        new = {f.evidence_id: _canon(asdict(f)) for f in current}
        ids = sorted(set(old) | set(new))
        changed = tuple(i for i in ids if old.get(i) != new.get(i))
        return DriftReport(len(ids), len(changed), (len(changed) / len(ids)) if ids else 0.0, changed)


@dataclass(frozen=True)
class Idea:
    idea_id: str
    source: str
    transformation: str
    input_ids: Tuple[str, ...]
    rationale: str


class Vyra:
    """Deterministic creative transformations; novelty is not claimed without evaluation."""
    TRANSFORMATIONS = ("recombine", "invert", "generalize", "specialize", "contrast")

    def generate(self, input_ids: Sequence[str], transformation: str, rationale: str) -> Idea:
        if not input_ids:
            raise ValueError("creative generation requires inputs")
        if transformation not in self.TRANSFORMATIONS:
            raise ValueError("unknown transformation")
        iid = _hash({"source": "VYRA", "transformation": transformation,
                     "input_ids": list(input_ids), "rationale": rationale})
        return Idea(iid, "VYRA", transformation, tuple(input_ids), rationale)


@dataclass(frozen=True)
class GatewayResponse:
    request_id: str
    evidence_count: int
    memory_count: int
    drift: Optional[DriftReport]
    inferences: int


class Aura:
    """Explicit orchestration gateway for the cognitive core."""
    def __init__(self, core):
        self.core = core
        self.research = DeepResearch(EvidenceStore(Path(core.memory.path).with_suffix(".evidence.jsonl")))
        self.echo = SynEcho()
        self.vyra = Vyra()

    def research_ingest(self, source: str, title: str, content: str, source_type: str) -> Evidence:
        return self.research.ingest(source, title, content, source_type)

    def cycle(self, previous_facts: Optional[Sequence[Fact]] = None,
              rules: Iterable = (), required_predicates: Iterable[str] = ()) -> GatewayResponse:
        before = tuple(previous_facts) if previous_facts is not None else tuple(self.core.memory.query())
        result = self.core.cycle_once(rules=rules, required_predicates=required_predicates)
        after = tuple(self.core.memory.query())
        request_id = _hash({"cycle": result.cycle, "world": result.world_digest})
        return GatewayResponse(request_id, len(self.research.store.all()),
                               result.memory_count, self.echo.compare(before, after),
                               result.inferred_count)
