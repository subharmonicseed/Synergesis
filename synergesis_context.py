"""Bounded context retrieval for Synergesis.

This module exists because persistent memory must not imply unlimited prompt
context. Retrieval is explicit, deterministic and bounded.

The current selector is lexical BM25-style retrieval. It is intentionally not
called "semantic embedding search". A future embedding retriever may implement
the same selector interface without changing the agent loop.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Sequence, Tuple

from synergesis_cognitive_core import Fact
from synergesis_research_layer import Evidence


_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(t.casefold() for t in _TOKEN.findall(text) if t)


def _fact_text(fact: Fact) -> str:
    return " ".join(
        (fact.subject, fact.predicate, fact.object, fact.source)
    )


def _evidence_text(evidence: Evidence) -> str:
    return " ".join(
        (evidence.title, evidence.content, evidence.source, evidence.source_type)
    )


@dataclass(frozen=True)
class ContextBudget:
    max_facts: int
    max_evidence: int

    def __post_init__(self):
        if self.max_facts < 0 or self.max_evidence < 0:
            raise ValueError("context limits must be non-negative")
        if self.max_facts == 0 and self.max_evidence == 0:
            raise ValueError("context budget cannot exclude both facts and evidence")


@dataclass(frozen=True)
class RankedItem:
    item_id: str
    score: float


@dataclass(frozen=True)
class ContextSelection:
    facts: Tuple[Fact, ...]
    evidence: Tuple[Evidence, ...]
    fact_ranking: Tuple[RankedItem, ...]
    evidence_ranking: Tuple[RankedItem, ...]


class LexicalContextSelector:
    """Deterministic BM25-style bounded retrieval.

    k1 and b are explicit configuration, not hidden constants.
    Only positive-score items are selected; unrelated memory is not padded into
    the context merely to fill the budget.
    """

    def __init__(self, *, budget: ContextBudget, k1: float, b: float):
        if not math.isfinite(k1) or k1 <= 0:
            raise ValueError("k1 must be finite and > 0")
        if not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("b must be finite and in [0,1]")
        self.budget = budget
        self.k1 = float(k1)
        self.b = float(b)

    def _rank(
        self,
        query: str,
        documents: Sequence[tuple[str, str]],
    ) -> tuple[RankedItem, ...]:
        q = tokenize(query)
        if not q or not documents:
            return ()

        tokenized = [(doc_id, tokenize(text)) for doc_id, text in documents]
        n_docs = len(tokenized)
        avg_len = sum(len(tokens) for _, tokens in tokenized) / n_docs
        if avg_len == 0:
            return ()

        doc_freq: dict[str, int] = {}
        for term in set(q):
            doc_freq[term] = sum(1 for _, tokens in tokenized if term in set(tokens))

        scored = []
        for doc_id, tokens in tokenized:
            if not tokens:
                continue
            frequencies: dict[str, int] = {}
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1

            score = 0.0
            length_norm = 1.0 - self.b + self.b * (len(tokens) / avg_len)
            for term in q:
                tf = frequencies.get(term, 0)
                if tf == 0:
                    continue
                df = doc_freq.get(term, 0)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                score += idf * (
                    tf * (self.k1 + 1.0)
                    / (tf + self.k1 * length_norm)
                )
            if score > 0:
                scored.append(RankedItem(doc_id, score))

        return tuple(sorted(scored, key=lambda x: (-x.score, x.item_id)))

    def select(
        self,
        *,
        query: str,
        facts: Sequence[Fact],
        evidence: Sequence[Evidence],
    ) -> ContextSelection:
        fact_docs = [(f.evidence_id, _fact_text(f)) for f in facts]
        evidence_docs = [(e.evidence_id, _evidence_text(e)) for e in evidence]

        fact_ranking = self._rank(query, fact_docs)
        evidence_ranking = self._rank(query, evidence_docs)

        fact_by_id = {f.evidence_id: f for f in facts}
        evidence_by_id = {e.evidence_id: e for e in evidence}

        selected_fact_rank = fact_ranking[: self.budget.max_facts]
        selected_evidence_rank = evidence_ranking[: self.budget.max_evidence]

        return ContextSelection(
            facts=tuple(fact_by_id[x.item_id] for x in selected_fact_rank),
            evidence=tuple(evidence_by_id[x.item_id] for x in selected_evidence_rank),
            fact_ranking=selected_fact_rank,
            evidence_ranking=selected_evidence_rank,
        )
