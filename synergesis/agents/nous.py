"""Synergesis – NOUS agent (shared black-board / knowledge base).

This first iteration stores concepts in a local SQLite DB using sqlmodel and
provides basic CRUD + text search. The implementation purposefully stays simple
so it can be evolved without breaking the loop.
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, List, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select, JSON

from .core_agents import AgentContext, BaseAgent, Glyph

logger = logging.getLogger(__name__)

DB_URL = "sqlite:///synergesis_nous.db"

try:
    _engine = create_engine(DB_URL, echo=False)
    
    class Concept(SQLModel, table=True):
        """Single atomic piece of knowledge stored by NOUS."""

        id: Optional[int] = Field(default=None, primary_key=True)
        label: str = Field(index=True)
        payload: str = Field(default="{}")  # Store as JSON string to avoid type issues
        created_at: _dt.datetime = Field(default_factory=_dt.datetime.utcnow, index=True)
    
    # Create tables at import time (idempotent)
    SQLModel.metadata.create_all(_engine)
    _db_available = True
    
except Exception as e:
    logger.warning(f"Database initialization failed: {e}")
    _engine = None
    _db_available = False
    
    # Fallback Concept class for when DB is unavailable
    class Concept:
        def __init__(self, label: str, payload: str = "{}", id: Optional[int] = None):
            self.id = id
            self.label = label
            self.payload = payload
            self.created_at = _dt.datetime.utcnow()


class Nous(BaseAgent):
    """Collective reasoning / blackboard agent."""

    name = "nous"

    def __init__(self, context: AgentContext):
        super().__init__(context)
        # Prom counters stored in shared_state for now
        ss = self.ctx.shared_state
        ss.setdefault("metrics", {}).setdefault("concepts_total", 0)
        ss["metrics"].setdefault("concepts_rejected_total", 0)

    # Public API --------------------------------------------------------
    def store_concept(self, label: str, payload: dict[str, Any]) -> Concept:
        """Persist a concept and return the stored row."""
        import json
        
        if _db_available and _engine:
            try:
                concept = Concept(label=label, payload=json.dumps(payload))
                with Session(_engine) as s:
                    s.add(concept)
                    s.commit()
                    s.refresh(concept)
                self.ctx.shared_state["metrics"]["concepts_total"] += 1
                self.logger.info("Stored concept %s (id=%s)", label, concept.id)
                return concept
            except Exception as e:
                self.logger.warning(f"Database store failed: {e}")
        
        # Fallback: store in memory
        concept = Concept(label=label, payload=json.dumps(payload))
        concepts_store = self.ctx.shared_state.setdefault("nous_concepts", [])
        concept.id = len(concepts_store) + 1
        concepts_store.append(concept)
        self.ctx.shared_state["metrics"]["concepts_total"] += 1
        self.logger.info("Stored concept %s in memory (id=%s)", label, concept.id)
        return concept

    def query(self, text: str) -> List[Concept]:
        """Very naive text search (LIKE) for now."""
        if _db_available and _engine:
            try:
                stmt = select(Concept).where(Concept.label.ilike(f"%{text}%"))
                with Session(_engine) as s:
                    return list(s.exec(stmt))
            except Exception as e:
                self.logger.warning(f"Database query failed: {e}")
        
        # Fallback: search in memory
        concepts_store = self.ctx.shared_state.get("nous_concepts", [])
        return [c for c in concepts_store if text.lower() in c.label.lower()]

    # Agent life-cycle --------------------------------------------------
    def perceive(self, *args: Any, **kwargs: Any):
        """NOUS is mostly event-driven; perceive returns queue of new glyphs."""
        bus: list[Glyph] = self.ctx.shared_state.get("glyph_bus", [])  # type: ignore[type-var]
        new_glyphs = [g for g in bus if g.get("meta", {}).get("agent") != self.name]
        return new_glyphs

    def decide(self, glyphs: list[Glyph]):  # type: ignore[name-defined]
        decisions: list[dict[str, Any]] = []
        for g in glyphs:
            if g["payload"].get("action") == "reduce_entropy":
                # For now just log; later could transform into concept
                decisions.append({"type": "LOG", "glyph_id": g["id"]})
        return decisions

    def act(self, decisions: list[dict[str, Any]]):  # type: ignore[override]
        for d in decisions:
            self.logger.debug("Decision taken: %s", d)
        return decisions


__all__ = ["Nous", "Concept"]
