import pytest
from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "blackstar1989")
NEO4J_AUTH = os.getenv("NEO4J_AUTH", "true").lower() == "true"
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

def test_schema_creation():
    """Test schema creation and verification"""
    auth = None
    if NEO4J_AUTH:
        auth = (NEO4J_USER, NEO4J_PASSWORD)
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=auth, encrypted=False)
    
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            # Test constraint creation
            result = session.run(
                """
                CREATE CONSTRAINT glyph_id IF NOT EXISTS 
                FOR (g:Glyph) REQUIRE g.id IS UNIQUE
                """
            )
            
            # Test index creation
            result = session.run(
                """
                CREATE INDEX glyph_parent_doc IF NOT EXISTS 
                FOR (g:Glyph) ON (g.parent_doc_id)
                """
            )
            
            # Verify constraints
            result = session.run(
                """
                SHOW CONSTRAINTS
                """
            )
            constraints = list(result)
            assert any("glyph_id" in str(c) for c in constraints)
            
            # Verify indexes
            result = session.run(
                """
                SHOW INDEXES
                """
            )
            indexes = list(result)
            assert any("glyph_parent_doc" in str(i) for i in indexes)
            
    finally:
        driver.close()

def test_schema_query():
    """Test querying with the schema"""
    auth = None
    if NEO4J_AUTH:
        auth = (NEO4J_USER, NEO4J_PASSWORD)
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=auth, encrypted=False)
    
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            # Test unique constraint
            session.run(
                """
                CREATE (:Glyph {
                    id: "test_id",
                    timestamp: 1234567890,
                    source: "test_source",
                    concept_type: "TEST",
                    status: "test",
                    polarité: "test",
                    alignement: "test",
                    content: "Test content",
                    parent_doc_id: "test_doc"
                })
                """
            )
            
            # Try to create another with same ID - should fail
            with pytest.raises(Exception):
                session.run(
                    """
                    CREATE (:Glyph {
                        id: "test_id",
                        timestamp: 1234567890,
                        source: "test_source",
                        concept_type: "TEST",
                        status: "test",
                        polarité: "test",
                        alignement: "test",
                        content: "Test content",
                        parent_doc_id: "test_doc"
                    })
                    """
                )
                
            # Test index usage
            result = session.run(
                """
                MATCH (g:Glyph)
                WHERE g.parent_doc_id = "test_doc"
                RETURN g
                """
            )
            assert len(list(result)) == 1
            
    finally:
        driver.close()

def test_schema_cleanup():
    """Cleanup test data"""
    auth = None
    if NEO4J_AUTH:
        auth = (NEO4J_USER, NEO4J_PASSWORD)
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=auth, encrypted=False)
    
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            session.run(
                """
                MATCH (g:Glyph {id: "test_id"})
                DETACH DELETE g
                """
            )
    finally:
        driver.close()
