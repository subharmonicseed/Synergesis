from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - optional dependency
    GraphDatabase = None  # type: ignore

GlyphData = Dict[str, Any]


class Neo4jInterface:
    """Thin wrapper around the neo4j driver."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        driver: Any = None,
    ) -> None:
        """Initialize the interface.

        Parameters
        ----------
        uri:
            Bolt URI of the Neo4j instance.
        user:
            Username for authentication.
        password:
            Password for authentication.
        driver:
            Preconfigured driver, mainly for testing. If provided, ``uri`` and
            credentials are ignored.
        """

        if driver is not None:
            self._driver = driver
            return
        if GraphDatabase is None:
            raise ImportError("neo4j package is required when no driver is provided")
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        """Close the underlying driver."""
        self._driver.close()

    # ------------------------------------------------------------------
    def upsert_glyph_node(self, glyph: GlyphData) -> None:
        """Create or update a glyph node."""
        gid = glyph.get("id")
        if gid is None:
            raise ValueError("Glyph must have an 'id' field")
        props = {k: v for k, v in glyph.items() if k != "id"}
        query = "MERGE (g:Glyph {id:$id})\nSET g += $props"
        try:
            with self._driver.session() as session:
                session.run(query, id=gid, props=props)
        except Exception as exc:  # pragma: no cover - driver errors
            raise RuntimeError(f"Failed to upsert glyph {gid}: {exc}") from exc

    def bulk_upsert_glyphs(self, glyphs: List[GlyphData], /, batch_size: int = 100) -> None:
        """Upsert glyphs in batches."""
        for start in range(0, len(glyphs), batch_size):
            batch = glyphs[start : start + batch_size]
            for glyph in batch:
                self.upsert_glyph_node(glyph)


__all__ = ["Neo4jInterface"]
