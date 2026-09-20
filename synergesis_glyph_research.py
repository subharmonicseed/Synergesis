"""Glyph-audited DeepResearch / AURA integration for Synergesis.

External material becomes EvidenceGlyphs immediately. Claims are HypothesisGlyphs.
Approval/rejection is an explicit DecisionGlyph. Only approved claims may become
FactGlyphs in NOUS, with graph provenance back to the claim and source evidence.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Sequence

from synergesis_cognitive_core import Fact, SemanticMemory, _hash
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph
from synergesis_research_layer import (
    Aura,
    Claim,
    DeepResearch,
    Evidence,
    EvidenceStore,
    _now,
)


class GlyphAuditedDeepResearch(DeepResearch):
    def __init__(self, store: EvidenceStore, *, graph: GlyphAuditGraph, core):
        super().__init__(store)
        self.graph = graph
        self.core = core

    def _latest(self, external_ref: str, glyph_type: str):
        matches = self.graph.ledger.find_by_external_ref(
            external_ref,
            glyph_type=glyph_type,
        )
        return matches[-1] if matches else None

    def _ensure_evidence(self, evidence: Evidence) -> Glyph:
        existing = self._latest(evidence.evidence_id, "evidence")
        if existing is not None:
            return existing
        return self.graph.create(
            "evidence",
            actor=f"source:{evidence.source_type}",
            content={
                "title": evidence.title,
                "source": evidence.source,
                "source_type": evidence.source_type,
                "retrieved_at": evidence.retrieved_at,
                "content_digest_only": True,
            },
            external_refs=(evidence.evidence_id,),
            metadata={
                "content_sha256": sha256(
                    evidence.content.encode("utf-8")
                ).hexdigest()
            },
            dedupe_external_ref=evidence.evidence_id,
        )

    def ingest(
        self,
        source: str,
        title: str,
        content: str,
        source_type: str,
    ) -> Evidence:
        # DeepResearch evidence identity is content-addressed. In a continuous
        # roaming runtime the same item may be encountered repeatedly; a fresh
        # retrieved_at timestamp must not turn that into an ID collision.
        evidence_id = _hash({
            "source": source,
            "title": title,
            "content": content,
        })
        try:
            evidence = self.store.get(evidence_id)
        except KeyError:
            evidence = super().ingest(source, title, content, source_type)
        else:
            if evidence.source_type != source_type:
                raise ValueError(
                    "same evidence content encountered with conflicting source_type"
                )
        self._ensure_evidence(evidence)
        return evidence

    def propose_claim(
        self,
        statement: str,
        evidence_ids: Sequence[str],
    ) -> Claim:
        claim = super().propose_claim(statement, evidence_ids)
        evidence_glyphs = [
            self._ensure_evidence(self.store.get(eid))
            for eid in claim.evidence_ids
        ]
        hypothesis = self.graph.create(
            "hypothesis",
            actor="DeepResearch",
            content={
                "statement": claim.statement,
                "status": "candidate",
                "claim_id": claim.claim_id,
            },
            external_refs=(claim.claim_id, f"claim-state:{claim.claim_id}:candidate"),
            derived_from=tuple(g.glyph_id for g in evidence_glyphs),
            dedupe_external_ref=f"claim-state:{claim.claim_id}:candidate",
        )
        for evidence_glyph in evidence_glyphs:
            self.graph.relate(
                evidence_glyph.glyph_id,
                hypothesis.glyph_id,
                "supports",
                actor="DeepResearch",
            )
        return claim

    def _review(self, claim: Claim, *, reviewer: str, decision: str) -> Claim:
        candidate = self._latest(
            f"claim-state:{claim.claim_id}:candidate",
            "hypothesis",
        )
        evidence_glyphs = [
            self._ensure_evidence(self.store.get(eid))
            for eid in claim.evidence_ids
        ]
        parents = [g.glyph_id for g in evidence_glyphs]
        if candidate is not None:
            parents.append(candidate.glyph_id)

        decision_ref = f"claim-review:{claim.claim_id}:{decision}"
        decision_glyph = self.graph.create(
            "decision",
            actor=f"reviewer:{reviewer}",
            content={
                "kind": "claim_review",
                "claim_id": claim.claim_id,
                "decision": decision,
                "reviewer": reviewer,
                "reviewed_at": claim.reviewed_at,
            },
            external_refs=(decision_ref,),
            derived_from=tuple(parents),
            dedupe_external_ref=decision_ref,
        )

        state_ref = f"claim-state:{claim.claim_id}:{decision}"
        new_state = self.graph.create(
            "hypothesis",
            actor=f"reviewer:{reviewer}",
            content={
                "statement": claim.statement,
                "status": decision,
                "claim_id": claim.claim_id,
                "reviewer": reviewer,
                "reviewed_at": claim.reviewed_at,
            },
            external_refs=(claim.claim_id, state_ref),
            derived_from=tuple(
                [decision_glyph.glyph_id]
                + ([candidate.glyph_id] if candidate is not None else [])
            ),
            dedupe_external_ref=state_ref,
        )
        if candidate is not None:
            self.graph.relate(
                new_state.glyph_id,
                candidate.glyph_id,
                "supersedes",
                actor=f"reviewer:{reviewer}",
            )
        return claim

    def approve(self, claim_id: str, reviewer: str) -> Claim:
        claim = super().approve(claim_id, reviewer)
        return self._review(claim, reviewer=reviewer, decision="approved")

    def reject(self, claim_id: str, reviewer: str) -> Claim:
        claim = super().reject(claim_id, reviewer)
        return self._review(claim, reviewer=reviewer, decision="rejected")

    def commit_approved_claim(
        self,
        claim_id: str,
        memory: SemanticMemory,
        subject: str,
        predicate: str,
        object: str,
        confidence: float,
    ) -> Fact:
        claim = self._claims[claim_id]
        if claim.status != "approved":
            raise ValueError("only approved claims may enter semantic memory")

        fid = _hash({
            "claim": claim.claim_id,
            "subject": subject,
            "predicate": predicate,
            "object": object,
        })

        # Use the cognitive core's audited insertion path when this is its memory.
        if memory is self.core.memory and hasattr(self.core, "remember"):
            fact = self.core.remember(
                subject,
                predicate,
                object,
                source=f"DeepResearch:{','.join(claim.evidence_ids)}",
                confidence=confidence,
                evidence_id=fid,
            )
        else:
            fact = memory.add(
                Fact(
                    subject,
                    predicate,
                    object,
                    source=f"DeepResearch:{','.join(claim.evidence_ids)}",
                    confidence=confidence,
                    observed_at=_now(),
                    evidence_id=fid,
                )
            )

        fact_glyphs = self.graph.ledger.find_by_external_ref(
            fact.evidence_id,
            glyph_type="fact",
        )
        if fact_glyphs:
            fact_glyph = fact_glyphs[-1]
        else:
            fact_glyph = self.graph.create(
                "fact",
                actor=fact.source,
                content={
                    "subject": fact.subject,
                    "predicate": fact.predicate,
                    "object": fact.object,
                    "source": fact.source,
                    "observed_at": fact.observed_at,
                },
                external_refs=(fact.evidence_id,),
                confidence=fact.confidence,
                dedupe_external_ref=fact.evidence_id,
            )

        approved = self._latest(
            f"claim-state:{claim.claim_id}:approved",
            "hypothesis",
        )
        if approved is not None:
            self.graph.relate(
                fact_glyph.glyph_id,
                approved.glyph_id,
                "derived_from",
                actor="DeepResearch",
            )
        for eid in claim.evidence_ids:
            evidence_glyph = self._latest(eid, "evidence")
            if evidence_glyph is not None:
                self.graph.relate(
                    evidence_glyph.glyph_id,
                    fact_glyph.glyph_id,
                    "supports",
                    actor="DeepResearch",
                )
        return fact


class GlyphAuditedAura(Aura):
    def __init__(self, core, *, graph: GlyphAuditGraph):
        super().__init__(core)
        self.research = GlyphAuditedDeepResearch(
            self.research.store,
            graph=graph,
            core=core,
        )
        self.graph = graph
