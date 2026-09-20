"""Glyph-audited cognitive core for Synergesis.

This module makes NOUS / THALES / World Model transitions first-class Glyph
Protocol v1 artifacts.

It records observable, explicit state transitions only. It does not attempt to
reconstruct a model's hidden chain-of-thought.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Optional

from synergesis_cognitive_core import (
    CognitiveCycle,
    Fact,
    Inference,
    Rule,
    SynCognitiveCore,
)
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph


class GlyphAuditedCognitiveCore(SynCognitiveCore):
    """SynCognitiveCore whose semantic facts and inferences are auditable glyphs."""

    def __init__(self, memory_path, *, graph: GlyphAuditGraph, actor: str = "ZÆL-0"):
        super().__init__(memory_path)
        self.graph = graph
        self.actor = actor
        self.sync_existing_facts()

    def _latest_external(self, external_ref: str, glyph_type: Optional[str] = None):
        matches = self.graph.ledger.find_by_external_ref(
            external_ref,
            glyph_type=glyph_type,
        )
        return matches[-1] if matches else None

    def _evidence_parent(self, evidence_id: str) -> Optional[str]:
        # External evidence, if already admitted into the audit graph.
        evidence = self._latest_external(evidence_id, "evidence")
        return evidence.glyph_id if evidence else None

    def ensure_fact_glyph(
        self,
        fact: Fact,
        *,
        derived_from: Iterable[str] = (),
    ) -> Glyph:
        existing = self._latest_external(fact.evidence_id, "fact")
        if existing is not None:
            return existing

        parents = list(derived_from)
        evidence_parent = self._evidence_parent(fact.evidence_id)
        if evidence_parent is not None and evidence_parent not in parents:
            parents.append(evidence_parent)

        glyph = self.graph.create(
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
            derived_from=tuple(parents),
            dedupe_external_ref=fact.evidence_id,
        )
        return glyph

    def sync_existing_facts(self) -> tuple[Glyph, ...]:
        return tuple(self.ensure_fact_glyph(f) for f in self.memory.query())

    def remember(
        self,
        subject: str,
        predicate: str,
        object: str,
        source: str,
        confidence: float,
        evidence_id: Optional[str] = None,
    ) -> Fact:
        fact = super().remember(
            subject,
            predicate,
            object,
            source,
            confidence,
            evidence_id,
        )
        self.ensure_fact_glyph(fact)
        return fact

    def _record_inference(self, inference: Inference) -> tuple[Glyph, Glyph]:
        premise_glyphs = []
        for premise_id in inference.premise_ids:
            matches = self.memory.query()
            premise = next(
                (f for f in matches if f.evidence_id == premise_id),
                None,
            )
            if premise is None:
                raise ValueError(
                    f"THALES inference references unknown premise: {premise_id}"
                )
            premise_glyphs.append(self.ensure_fact_glyph(premise))

        inference_ref = f"inference:{inference.conclusion.evidence_id}"
        existing = self._latest_external(inference_ref, "inference")
        if existing is None:
            inf_glyph = self.graph.create(
                "inference",
                actor=f"THALES:{inference.rule}",
                content={
                    "rule": inference.rule,
                    "premise_ids": list(inference.premise_ids),
                    "conclusion_evidence_id": inference.conclusion.evidence_id,
                    "conclusion": {
                        "subject": inference.conclusion.subject,
                        "predicate": inference.conclusion.predicate,
                        "object": inference.conclusion.object,
                    },
                },
                external_refs=(inference_ref,),
                confidence=inference.conclusion.confidence,
                derived_from=tuple(g.glyph_id for g in premise_glyphs),
                dedupe_external_ref=inference_ref,
            )
            for premise_glyph in premise_glyphs:
                self.graph.relate(
                    premise_glyph.glyph_id,
                    inf_glyph.glyph_id,
                    "supports",
                    actor=f"THALES:{inference.rule}",
                )
        else:
            inf_glyph = existing

        fact_glyph = self.ensure_fact_glyph(
            inference.conclusion,
            derived_from=(inf_glyph.glyph_id,),
        )
        return inf_glyph, fact_glyph

    def cycle_once(
        self,
        rules: Iterable[Rule] = (),
        required_predicates: Iterable[str] = (),
    ) -> CognitiveCycle:
        integrity = self.selene.integrity()

        proposed = self.thales.infer(self.memory, rules)
        inferred: list[Inference] = []
        inference_glyphs: list[Glyph] = []
        for item in proposed:
            # A deterministic THALES conclusion may be rediscovered on later
            # cycles. Reuse the existing immutable fact instead of creating a
            # collision solely because observed_at differs.
            existing = next(
                (
                    fact
                    for fact in self.memory.query()
                    if fact.evidence_id == item.conclusion.evidence_id
                ),
                None,
            )
            if existing is None:
                self.memory.add(item.conclusion)
                canonical_item = item
            else:
                canonical_item = Inference(
                    item.rule,
                    item.premise_ids,
                    existing,
                )
            inf_glyph, _ = self._record_inference(canonical_item)
            inference_glyphs.append(inf_glyph)
            inferred.append(canonical_item)

        world = self.world.snapshot()
        self.cycle += 1
        cycle = CognitiveCycle(
            self.cycle,
            world.digest,
            self.memory.count(),
            integrity.valid,
            len(inferred),
            tuple(self.selene.gaps(required_predicates)),
        )

        fact_glyphs = tuple(
            self.ensure_fact_glyph(fact)
            for fact in world.facts
        )
        world_ref = f"cognitive-cycle:{cycle.cycle}"
        world_glyph = self.graph.create(
            "cycle",
            actor=self.actor,
            content={
                "kind": "world_state",
                "world_digest": world.digest,
                "world_version": world.version,
                "fact_count": len(world.facts),
                "integrity_valid": integrity.valid,
                "gaps": list(cycle.gaps),
                "inferred_count": len(inferred),
            },
            external_refs=(world_ref, f"world:{world.digest}"),
            derived_from=tuple(
                [g.glyph_id for g in fact_glyphs]
                + [g.glyph_id for g in inference_glyphs]
            ),
            dedupe_external_ref=world_ref,
        )

        # The world-state glyph is intentionally immutable. Later world states
        # supersede earlier snapshots without rewriting history.
        previous_ref = f"cognitive-cycle:{cycle.cycle - 1}"
        if cycle.cycle > 1:
            previous = self._latest_external(previous_ref, "cycle")
            if previous is not None:
                self.graph.relate(
                    world_glyph.glyph_id,
                    previous.glyph_id,
                    "supersedes",
                    actor=self.actor,
                )

        return cycle
