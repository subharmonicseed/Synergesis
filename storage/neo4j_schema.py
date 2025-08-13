"""DDL helpers for Neo4j indexes & constraints."""

from typing import List
from .neo4j_interface import Neo4jStorage

DDL_STATEMENTS: List[str] = [
    # Unique glyph ID constraint
    """
    CREATE CONSTRAINT glyph_id IF NOT EXISTS 
    FOR (g:Glyph) REQUIRE g.id IS UNIQUE
    """,
    # Index for fast lookup by parent document
    """
    CREATE INDEX glyph_parent_doc IF NOT EXISTS 
    FOR (g:Glyph) ON (g.parent_doc_id)
    """,
    # Index for status-based queries
    """
    CREATE INDEX glyph_status IF NOT EXISTS 
    FOR (g:Glyph) ON (g.status)
    """,
    # Index for concept type queries
    """
    CREATE INDEX glyph_concept_type IF NOT EXISTS 
    FOR (g:Glyph) ON (g.concept_type)
    """,
    # Unique constraint for POTENTIAL_ACTION
    """
    CREATE CONSTRAINT potential_action_id IF NOT EXISTS 
    FOR (n:POTENTIAL_ACTION) REQUIRE n.id IS UNIQUE
    """,
    # Unique constraint for EXECUTED_ACTION
    """
    CREATE CONSTRAINT executed_action_id IF NOT EXISTS 
    FOR (n:EXECUTED_ACTION) REQUIRE n.id IS UNIQUE
    """
]

def apply_schema(storage: Neo4jStorage) -> None:
    """
    Apply all Neo4j schema definitions (constraints and indexes).
    
    Args:
        storage: Neo4jStorage instance with active connection
    """
    for stmt in DDL_STATEMENTS:
        try:
            with storage.driver.session(database=storage.database) as session:
                result = session.run(stmt)
                print(f"Applied schema: {stmt.split(' ')[0]}")
        except Exception as e:
            print(f"Warning: Failed to apply {stmt.split(' ')[0]}: {e}")
