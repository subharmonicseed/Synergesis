from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

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
    def _execute_query(self, query: str, params: Dict[str, Any]) -> None:
        """Execute a Cypher query using a new session."""

        with self._driver.session() as session:
            session.run(query, params)

    # ------------------------------------------------------------------
    def _prepare_params(self, glyph: GlyphData) -> Tuple[Dict[str, Any], str]:
        """Return properties and sanitized label for Cypher."""

        allowed = [
            "timestamp",
            "source",
            "concept_type",
            "status",
            "polarite",
            "alignement",
            "poids",
            "frequence",
            "entropy_score",
            "resonance",
            "tags",
        ]
        props: Dict[str, Any] = {}
        for key in allowed:
            if key not in glyph:
                continue
            val = glyph[key]
            if key != "tags" and isinstance(val, (dict, list)):
                continue
            props[key] = val
        ct = glyph.get("concept_type")
        label = re.sub(r"[^A-Za-z0-9]", "_", ct) if isinstance(ct, str) else ""
        return props, label

    def upsert_glyph_node(self, glyph: GlyphData) -> None:
        """Create or update a single glyph node."""

        gid = glyph.get("id")
        if gid is None:
            raise ValueError("Glyph must have an 'id' field")
        props, label = self._prepare_params(glyph)
        query = "MERGE (g:Glyph {id:$id})"
        if label:
            query += f"\nSET g:`{label}`"
        query += "\nSET g += $props"
        try:
            with self._driver.session() as session:
                session.run(query, id=gid, props=props)
        except Exception as exc:  # pragma: no cover - driver errors
            raise RuntimeError(f"Failed to upsert glyph {gid}: {exc}") from exc

    def bulk_upsert_glyphs(self, glyphs: List[GlyphData], /, batch_size: int = 100) -> None:
        """Upsert multiple glyphs using batched UNWIND queries."""

        for start in range(0, len(glyphs), batch_size):
            batch = glyphs[start : start + batch_size]
            prepared = []
            for g in batch:
                gid = g.get("id")
                if gid is None:
                    raise ValueError("Glyph must have an 'id' field")
                props, label = self._prepare_params(g)
                prepared.append({"id": gid, "props": props, "label": label})

            query = (
                "UNWIND $batch AS row\n"
                "MERGE (g:Glyph {id: row.id})\n"
                "SET g += row.props\n"
                "WITH g, row.label AS label\n"
                "CALL apoc.create.addLabels(g, CASE WHEN label <> '' THEN [label] ELSE [] END)"
                " YIELD node\n"
                "RETURN count(node)"
            )
            try:
                self._execute_query(query, {"batch": prepared})
            except Exception as exc:  # pragma: no cover - driver errors
                raise RuntimeError(f"Failed to bulk upsert glyphs: {exc}") from exc


__all__ = ["Neo4jInterface"]
