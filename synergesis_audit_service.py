"""High-level audit queries and portable snapshot export for Glyph Protocol v1."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional, Tuple

from synergesis_glyph_protocol import (
    Glyph,
    GlyphAuditGraph,
    GlyphEdge,
    IntegrityCheckpoint,
    SCHEMA_VERSION,
    to_wire,
)


@dataclass(frozen=True)
class DecisionAuditReport:
    decision: Glyph
    upstream_glyphs: Tuple[Glyph, ...]
    provenance_edges: Tuple[GlyphEdge, ...]
    evidence: Tuple[Glyph, ...]
    hypotheses: Tuple[Glyph, ...]
    goals: Tuple[Glyph, ...]
    observations: Tuple[Glyph, ...]


@dataclass(frozen=True)
class EvidenceImpactReport:
    evidence: Glyph
    impacted_glyphs: Tuple[Glyph, ...]
    decisions: Tuple[Glyph, ...]
    actions: Tuple[Glyph, ...]
    outcomes: Tuple[Glyph, ...]
    learning: Tuple[Glyph, ...]


class SynAuditService:
    def __init__(self, graph: GlyphAuditGraph):
        self.graph = graph

    def why_decision(self, decision_glyph_id: str) -> DecisionAuditReport:
        trace = self.graph.explain_decision(decision_glyph_id)
        others = tuple(
            g for g in trace.glyphs
            if g.glyph_id != decision_glyph_id
        )
        return DecisionAuditReport(
            decision=trace.focal_glyph,
            upstream_glyphs=others,
            provenance_edges=trace.edges,
            evidence=tuple(g for g in others if g.glyph_type == "evidence"),
            hypotheses=tuple(g for g in others if g.glyph_type == "hypothesis"),
            goals=tuple(g for g in others if g.glyph_type == "goal"),
            observations=tuple(g for g in others if g.glyph_type == "observation"),
        )

    def evidence_impact(
        self,
        *,
        evidence_glyph_id: Optional[str] = None,
        external_evidence_ref: Optional[str] = None,
    ) -> EvidenceImpactReport:
        if (evidence_glyph_id is None) == (external_evidence_ref is None):
            raise ValueError(
                "provide exactly one of evidence_glyph_id or external_evidence_ref"
            )
        if external_evidence_ref is not None:
            matches = self.graph.ledger.find_by_external_ref(
                external_evidence_ref,
                glyph_type="evidence",
            )
            if not matches:
                raise KeyError(f"unknown evidence ref: {external_evidence_ref}")
            evidence = matches[-1]
        else:
            evidence = self.graph.ledger.get(str(evidence_glyph_id))
            if evidence.glyph_type != "evidence":
                raise ValueError("evidence_impact requires an evidence glyph")

        trace = self.graph.impacted_by(evidence.glyph_id)
        impacted = tuple(
            g for g in trace.glyphs if g.glyph_id != evidence.glyph_id
        )
        return EvidenceImpactReport(
            evidence=evidence,
            impacted_glyphs=impacted,
            decisions=tuple(g for g in impacted if g.glyph_type == "decision"),
            actions=tuple(g for g in impacted if g.glyph_type == "action"),
            outcomes=tuple(g for g in impacted if g.glyph_type == "outcome"),
            learning=tuple(g for g in impacted if g.glyph_type == "learning"),
        )

    def portable_snapshot(self) -> Mapping[str, Any]:
        checkpoint = self.graph.ledger.verify()
        return to_wire({
            "schema_version": SCHEMA_VERSION,
            "checkpoint": checkpoint,
            "glyphs": list(self.graph.ledger.glyphs()),
            "edges": list(self.graph.ledger.edges()),
        })
