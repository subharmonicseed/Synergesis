"""Simplified Neo4j interface wrapper."""
from __future__ import annotations

from typing import Any, Dict, List

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - optional dependency
    GraphDatabase = None

from ..glyph_core import GlyphData


class Neo4jInterface:
    """Wrapper around the Neo4j driver."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        if GraphDatabase is None:
            raise ImportError("neo4j package not available")
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def _execute_query(self, query: str, params: Dict[str, Any]) -> None:
        with self._driver.session() as session:
            session.run(query, params)

    def upsert_glyph_node(self, glyph: GlyphData) -> None:
        # Placeholder for actual Cypher query
        pass

    def bulk_upsert_glyphs(self, glyphs: List[GlyphData], batch_size: int = 100) -> None:
        for g in glyphs:
            self.upsert_glyph_node(g)
