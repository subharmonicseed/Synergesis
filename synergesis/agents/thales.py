"""Synergesis – Thales agent (logical consistency / contradiction checker).

This first cut scans the NOUS concept table for duplicate labels whose payloads
contain conflicting key/value pairs. When contradictions are detected it emits
`CONTRADICTION_DETECTED` glyphs onto the shared glyph bus.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from sqlmodel import Session, select
    _sqlmodel_available = True
except ImportError:
    _sqlmodel_available = False
    Session = None
    select = None

from .core_agents import AgentContext, BaseAgent, Glyph
try:
    from .nous import Concept, Nous, _db_available, _engine
except ImportError:
    _db_available = False
    _engine = None
    Concept = None
    Nous = None

logger = logging.getLogger(__name__)


def _is_contradiction(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Very naïve contradiction heuristic: if the same key has different values."""
    common_keys = a.keys() & b.keys()
    for k in common_keys:
        if a[k] != b[k]:
            return True
    return False


class Thales(BaseAgent):
    """Detects logical inconsistencies across stored concepts."""

    name = "thales"

    def __init__(self, ctx: AgentContext):
        super().__init__(ctx)
        self.nous: Nous = ctx.shared_state.get("agents", {}).get("nous")  # type: ignore

    # ---------------------------------------------------------------------
    def perceive(self, data: Any = None):
        """Pull all concepts for analysis - with database fallback."""
        if _db_available and _engine and _sqlmodel_available:
            try:
                with Session(_engine) as s:
                    concepts: List[Concept] = list(s.exec(select(Concept)))
                return concepts
            except Exception as e:
                logger.warning(f"Database access failed: {e}")
        
        # Fallback: use in-memory concepts from shared_state
        concepts_store = self.ctx.shared_state.get("nous_concepts", [])
        return concepts_store

    def decide(self, concepts: List[Any]):  # type: ignore[override]
        """Detect contradictions in concepts - with fallback handling."""
        contradictions: list[tuple[int, int]] = []
        by_label: dict[str, List[Any]] = {}
        
        if not concepts:
            return contradictions
            
        for c in concepts:
            label = getattr(c, 'label', str(c)).lower()
            by_label.setdefault(label, []).append(c)
            
        for lbl, lst in by_label.items():
            if len(lst) < 2:
                continue
            for i, a in enumerate(lst):
                for b in lst[i + 1 :]:
                    try:
                        import json
                        payload_a = json.loads(getattr(a, 'payload', '{}'))
                        payload_b = json.loads(getattr(b, 'payload', '{}'))
                        if _is_contradiction(payload_a, payload_b):
                            id_a = getattr(a, 'id', i)
                            id_b = getattr(b, 'id', i+1)
                            contradictions.append((id_a, id_b))
                    except Exception as e:
                        logger.warning(f"Contradiction analysis failed: {e}")
        return contradictions

    def act(self, contradictions: list[tuple[int, int]]):
        if not contradictions:
            return None
        bus: list[Glyph] = self.ctx.shared_state.setdefault("glyph_bus", [])  # type: ignore[type-var]
        for cid_a, cid_b in contradictions:
            glyph: Glyph = {
                "id": f"contradiction:{cid_a}:{cid_b}",
                "payload": {
                    "type": "CONTRADICTION_DETECTED",
                    "concept_a": cid_a,
                    "concept_b": cid_b,
                },
                "meta": {"agent": self.name},
            }
            bus.append(glyph)
            logger.info("Thales emitted contradiction glyph %s", glyph["id"])
        # Update counter
        self.ctx.shared_state.setdefault("metrics", {}).setdefault("contradictions_total", 0)
        self.ctx.shared_state["metrics"]["contradictions_total"] += len(contradictions)
        return contradictions
