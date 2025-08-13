# synergesis/storage/neo4j_interface.py
"""
Interface for interacting with a Neo4j graph database.
Handles connection and provides methods for data persistence.
"""
from __future__ import annotations
import os
from typing import Any, List

try:
    from neo4j import GraphDatabase, Driver
except ImportError:  # pragma: no cover - optional dependency
    GraphDatabase = None
    Driver = None

from synergesis.glyph_core import Glyph
from synergesis.utils.data_conversion import pydantic_to_neo4j

class Neo4jInterface:
    """Manages the connection and data operations for the Neo4j database."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        driver: Driver | None = None,
    ) -> None:
        """
        Initializes the interface and connects to the database.
        Connection details are read from environment variables as a fallback.
        """
        if driver:
            self._driver = driver
            return

        if GraphDatabase is None:
            raise ImportError("The 'neo4j' package is required to use Neo4jInterface.")

        db_uri = uri or os.environ.get("NEO4J_URI")
        db_user = user or os.environ.get("NEO4J_USER")
        db_password = password or os.environ.get("NEO4J_PASSWORD")

        if not all([db_uri, db_user, db_password]):
            raise ValueError(
                "Database connection details are missing. "
                "Please provide them as arguments or set NEO4J_URI, "
                "NEO4J_USER, and NEO4J_PASSWORD environment variables."
            )

        self._driver = GraphDatabase.driver(db_uri, auth=(db_user, db_password))

    def close(self) -> None:
        """Closes the underlying database driver."""
        if self._driver:
            self._driver.close()

    def bulk_upsert_glyphs(self, glyphs: List[Glyph]) -> None:
        """
        Upserts a batch of glyphs into the database efficiently.
        It uses MERGE on the glyph's ID to either create a new node or update
        an existing one.

        Args:
            glyphs: A list of Glyph objects to upsert.
        """
        if not glyphs:
            return

        # Convert Pydantic models to Neo4j-compatible dictionaries
        glyph_properties = [pydantic_to_neo4j(g) for g in glyphs]

        # This query uses UNWIND to process a list of glyphs as a stream,
        # which is the most performant way to handle bulk operations in Neo4j.
        query = """
        UNWIND $glyphs AS glyph_props
        MERGE (g:Glyph {id: glyph_props.id})
        SET g = glyph_props
        """
        try:
            with self._driver.session() as session:
                session.run(query, glyphs=glyph_properties)
        except Exception as exc:  # pragma: no cover - driver errors
            raise RuntimeError(f"Failed to bulk upsert glyphs: {exc}") from exc
