from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import os
from datetime import datetime
from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import ServiceUnavailable
from neo4j.graph import Node

from models.glyph import Glyph
from models.execution import ExecutionRecord

# Try to import neo4j package
try:
    from neo4j import GraphDatabase, basic_auth  # pragma: no cover
except ModuleNotFoundError:  # ───── stubbed in unit-tests ─────
    GraphDatabase = basic_auth = None  # type: ignore

# Try to import neo4j.exceptions
try:
    from neo4j.exceptions import ServiceUnavailable
    ServiceUnavailable = ServiceUnavailable
except ImportError:
    ServiceUnavailable = None
    GraphDatabase = None  # Allows unit-tests without Neo4j installed

# Define stub classes for testing

class _StubSession:
    """Stub session that returns empty results."""
    def run(self, *_args, **_kwargs):  # returns empty list for any cypher
        return []

class _StubDriver:
    """Stub driver that provides a stub session."""
    def session(self, database=None):  # type: ignore[override]
        return _StubSession()
    def close(self):
        pass

class _StubStorage:
    """Stub storage that provides basic functionality for testing."""
    def __init__(self, *args, **kwargs):
        """Stub initialization - ignore all args."""
        self._rows: dict[str, dict] = {}
        self.driver = _StubDriver()  # Always use stub driver in test mode

    # these three tiny helpers are all the FastAPI layer touches in tests
    def list_executions(self) -> list[dict]:
        return []
        self._check_driver()
        self._driver.close()

    def _execute_query(self, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a query with parameters."""
        self._check_driver()
        with self._driver.session(database=self.database) as session:
            result = session.run(query, parameters)
            return [record._asdict() for record in result]

class GlyphNode(BaseModel):
    id: str = Field(..., description="Unique identifier for the glyph")
    timestamp: int = Field(..., description="Unix timestamp of the glyph")
    source: str = Field(..., description="Source of the glyph")
    concept_type: str = Field(..., description="Type of concept")
    status: str = Field(..., description="Current status of the glyph")
    polarité: str = Field(..., description="Polarity indicator")
    alignement: str = Field(..., description="Alignment type")

class Neo4jStorage:
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None,
        encrypted: bool = False
    ) -> None:
        """Initialize Neo4j storage with connection parameters."""
        self.uri = uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or os.getenv('NEO4J_USER', 'neo4j')
        self.password = password or os.getenv('NEO4J_PASSWORD', '')
        self.database = database or os.getenv('NEO4J_DATABASE', 'neo4j')
        self.encrypted = encrypted
        self._initialize_driver()

    def _check_driver(self) -> None:
        """Check if Neo4j driver is available."""
        if GraphDatabase is None:
            raise RuntimeError("neo4j package not installed - running in stub mode")

    def _initialize_driver(self) -> None:
        """Initialize the Neo4j driver."""
        if GraphDatabase is None:
            self.driver = _StubDriver()
            return

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=basic_auth(self.user, self.password),
            encrypted=self.encrypted,
            max_connection_lifetime=3600,
            user_agent="synergesis-test"
        )
        print(f"Connected to Neo4j at {self.uri}")

    def _check_driver(self) -> None:
        """Check if Neo4j driver is available."""
        if GraphDatabase is None:
            raise RuntimeError("neo4j package not installed - running in stub mode")

    def close(self):
        """Close the Neo4j driver connection"""
        if not self._use_stub:
            self.driver.close()

    def _execute_query(self, query: str, params: dict) -> None:
        """Execute a Neo4j query with parameters."""
        with self.driver.session(database=self.database) as session:
            session.run(query, params)

    def upsert_glyph_node(self, glyph: GlyphNode) -> None:
        """MERGE glyph node into Neo4j (labels by concept_type)."""
        label = glyph.concept_type
        query = f"""
        MERGE (g:{label} {{id:$id}})
        SET   g += $props
        """
        props = {k: v for k, v in glyph.model_dump().items() if k != "concept_type"}
        self._execute_query(query, {"id": glyph.id, "props": props})

    def upsert_execution_record(
        self, execution_glyph: GlyphNode, original_action_id: str
    ) -> None:
        """
        Store EXECUTED_ACTION glyph and connect it to the POTENTIAL_ACTION it
        materialised from.
        """
        self.upsert_glyph_node(execution_glyph)
        rel_query = """
        MATCH (e:EXECUTED_ACTION {id:$exec_id})
        MATCH (a:POTENTIAL_ACTION {id:$action_id})
        MERGE (e)-[:EXECUTES]->(a)
        """
        self._execute_query(
            rel_query, {"exec_id": execution_glyph.id, "action_id": original_action_id}
        )
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    """
                    MERGE (g:Glyph {id: $id})
                    SET g += $properties
                    RETURN g
                    """,
                    id=glyph.id,
                    properties=glyph.dict()
                )
                return result.single() is not None
        except Exception as e:
            print(f"Error upserting glyph: {e}")
            return False

    def bulk_upsert_glyphs(self, glyphs: List[GlyphNode]) -> Dict[str, Any]:
        """
        Create or update multiple glyph nodes in Neo4j in a single transaction
        
        Args:
            glyphs: List of GlyphNode objects to upsert
            
        Returns:
            Dict: Summary of the operation containing:
                - success_count: Number of successfully upserted glyphs
                - error_count: Number of glyphs that failed to upsert
                - errors: List of error messages for failed glyphs
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    """
                    UNWIND $glyphs AS glyph
                    MERGE (g:Glyph {id: glyph.id})
                    SET g += glyph.properties
                    RETURN count(DISTINCT g) as success_count
                    """,
                    glyphs=[{
                        "id": glyph.id,
                        "properties": glyph.dict()
                    } for glyph in glyphs]
                )
                
                summary = result.single()
                return {
                    "success_count": summary["success_count"],
                    "error_count": 0,
                    "errors": []
                }
                
        except Exception as e:
            print(f"Error in bulk upsert: {e}")
            return {
                "success_count": 0,
                "error_count": len(glyphs),
                "errors": [str(e)]
            }

    def bulk_upsert_glyphs(self, glyphs: List[GlyphNode]) -> int:
        """
        Create or update multiple glyph nodes in Neo4j
        
        Args:
            glyphs: List of GlyphNode objects
            
        Returns:
            int: Number of nodes processed
        """
        try:
            with self.driver.session() as session:
                for glyph in glyphs:
                    session.run(
                        """
                        MERGE (g:Glyph {id: $id})
                        SET g += $properties
                        RETURN g
                        """,
                        id=glyph.id,
                        properties={
                            "timestamp": glyph.timestamp,
                            "source": glyph.source,
                            "concept_type": glyph.concept_type,
                            "status": glyph.status,
                            "polarité": glyph.polarité,
                            "alignement": glyph.alignement
                        }
                    )
                return len(glyphs)
        except Exception as e:
            print(f"Error bulk upserting glyphs: {e}")
            return 0

    def get_glyph_count(self) -> int:
        """
        Get the total number of glyphs in Neo4j
        
        Returns:
            int: Number of glyphs
        """
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (g:Glyph) RETURN count(g)")
                return result.single()[0]
        except Exception as e:
            print(f"Error getting glyph count: {e}")
            return 0

    def query_glyphs(self, type: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Query glyphs from Neo4j
        
        Args:
            type: Optional type filter
            limit: Maximum number of results
            
        Returns:
            List of glyph dictionaries
        """
        try:
            with self.driver.session() as session:
                if type:
                    result = session.run(
                        """
                        MATCH (g:Glyph {concept_type: $type})
                        RETURN g
                        ORDER BY g.timestamp DESC
                        LIMIT $limit
                        """,
                        type=type,
                        limit=limit
                    )
                else:
                    result = session.run(
                        """
                        MATCH (g:Glyph)
                        RETURN g
                        ORDER BY g.timestamp DESC
                        LIMIT $limit
                        """,
                        limit=limit
                    )
                
                return [{
                    'id': record['g']['id'],
                    'timestamp': record['g']['timestamp'],
                    'source': record['g']['source'],
                    'concept_type': record['g']['concept_type'],
                    'status': record['g']['status'],
                    'polarité': record['g']['polarité'],
                    'alignement': record['g']['alignement']
                } for record in result]
        except Exception as e:
            print(f"Error querying glyphs: {e}")
            return []

def main():
    # Initialize storage
    neo4j = Neo4jStorage()
    
    # Create example glyph
    example_glyph = GlyphNode(
        id="test_glyph_1",
        timestamp=int(datetime.now().timestamp()),
        source="initial_test",
        concept_type="test",
        status="generated",
        polarité="+",
        alignement="Celestial"
    )
    
    # Upsert glyph
    success = neo4j.upsert_glyph_node(example_glyph)
    print(f"Glyph upsert successful: {success}")
    
    # Get glyph count
    count = neo4j.get_glyph_count()
    print(f"Total glyphs in storage: {count}")
    
    # Query glyphs
    glyphs = neo4j.query_glyphs()
    print("\nFound glyphs:")
    for glyph in glyphs:
        print(f"- {glyph['id']}: {glyph['concept_type']}")
    
    # Close connection
    neo4j.close()

if __name__ == "__main__":
    main()
