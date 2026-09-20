"""Explicit current-head view over append-only semantic memory.

Synergesis keeps immutable belief history for auditability. Long-running
consumers must nevertheless be able to distinguish historical versions from
the currently active version.

This module does not delete or rewrite semantic memory. It applies head
semantics only to predicates explicitly declared versioned. All other facts
remain multi-valued and untouched.

For a versioned predicate, the current head is the last append-order fact for
the `(subject, predicate)` key. Append order is persistent because
`SemanticMemory` reloads its JSONL in file order and Python dictionaries retain
insertion order.

This is a view, not a causal or epistemic claim: "current" means latest recorded
version, not "true".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Optional, Sequence, Tuple

from synergesis_cognitive_core import Fact, SemanticMemory


def _canon(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _hash(value) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BeliefHead:
    subject: str
    predicate: str
    current: Fact
    history: Tuple[Fact, ...]

    def __post_init__(self):
        if not self.history:
            raise ValueError("belief head history cannot be empty")
        if self.current != self.history[-1]:
            raise ValueError("current belief head must be final history entry")
        if any(
            fact.subject != self.subject or fact.predicate != self.predicate
            for fact in self.history
        ):
            raise ValueError("belief head history key mismatch")


@dataclass(frozen=True)
class CurrentBeliefSnapshot:
    facts: Tuple[Fact, ...]
    versioned_predicates: Tuple[str, ...]
    history_fact_count: int
    current_fact_count: int
    digest: str


class VersionedBeliefView:
    """Read-only head projection over explicit versioned predicates."""

    def __init__(
        self,
        memory: SemanticMemory,
        *,
        versioned_predicates: Sequence[str],
    ):
        predicates = tuple(dict.fromkeys(versioned_predicates))
        if not predicates:
            raise ValueError("at least one versioned predicate is required")
        if any(
            not isinstance(predicate, str) or not predicate.strip()
            for predicate in predicates
        ):
            raise ValueError("versioned predicates must be non-empty strings")
        self.memory = memory
        self.versioned_predicates = predicates
        self._versioned = frozenset(predicates)

    def history(
        self,
        *,
        subject: str,
        predicate: str,
    ) -> Tuple[Fact, ...]:
        if predicate not in self._versioned:
            raise ValueError("predicate is not declared versioned")
        return tuple(
            self.memory.query(
                subject=subject,
                predicate=predicate,
            )
        )

    def head(
        self,
        *,
        subject: str,
        predicate: str,
    ) -> Optional[BeliefHead]:
        history = self.history(subject=subject, predicate=predicate)
        if not history:
            return None
        return BeliefHead(
            subject=subject,
            predicate=predicate,
            current=history[-1],
            history=history,
        )

    def current(
        self,
        *,
        subject: str,
        predicate: str,
    ) -> Optional[Fact]:
        head = self.head(subject=subject, predicate=predicate)
        return head.current if head is not None else None

    def current_facts(
        self,
        *,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
    ) -> Tuple[Fact, ...]:
        if predicate is not None and predicate not in self._versioned:
            raise ValueError("predicate is not declared versioned")
        facts = self.memory.query(subject=subject, predicate=predicate)
        latest: dict[tuple[str, str], Fact] = {}
        for fact in facts:
            if fact.predicate in self._versioned:
                latest[(fact.subject, fact.predicate)] = fact
        return tuple(latest.values())

    def materialized_facts(
        self,
        *,
        subject: Optional[str] = None,
    ) -> Tuple[Fact, ...]:
        """Return full non-versioned memory plus only heads of versioned keys."""
        facts = self.memory.query(subject=subject)
        latest: dict[tuple[str, str], Fact] = {}
        non_versioned: list[Fact] = []
        for fact in facts:
            if fact.predicate in self._versioned:
                latest[(fact.subject, fact.predicate)] = fact
            else:
                non_versioned.append(fact)
        projected = non_versioned + list(latest.values())
        # Stable deterministic ordering without pretending evidence IDs encode
        # chronology.
        return tuple(
            sorted(
                projected,
                key=lambda f: (f.subject, f.predicate, f.evidence_id),
            )
        )

    def snapshot(self) -> CurrentBeliefSnapshot:
        facts = self.materialized_facts()
        payload = {
            "versioned_predicates": self.versioned_predicates,
            "history_fact_count": self.memory.count(),
            "facts": [asdict(fact) for fact in facts],
        }
        return CurrentBeliefSnapshot(
            facts=facts,
            versioned_predicates=self.versioned_predicates,
            history_fact_count=self.memory.count(),
            current_fact_count=len(facts),
            digest=_hash(payload),
        )
