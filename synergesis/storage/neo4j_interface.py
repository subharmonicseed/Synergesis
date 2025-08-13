from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
import os
import json
import time
from datetime import datetime, timezone
import logging

# Try to load the real driver; otherwise fall back to a stub so tests run
try:
    from neo4j import GraphDatabase, basic_auth  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    GraphDatabase = None  # Allows unit-tests without Neo4j installed

logger = logging.getLogger(__name__)

class GlyphNode(BaseModel):
    id: str = Field(..., description="Unique identifier for the glyph")
    timestamp: int = Field(..., description="Unix timestamp of the glyph")
    source: str = Field(..., description="Source of the glyph")
    concept_type: str = Field(..., description="Type of concept")
    status: str = Field(..., description="Current status of the glyph")
    polarité: str = Field(..., description="Polarity indicator")
    alignement: str = Field(..., description="Alignment type")

class Neo4jStorage:
    """
    Handles interactions with a Neo4j database for storing and retrieving glyphs.
    Provides a stub mode for environments where Neo4j is not available.
    """

    def __init__(self, uri=None, user=None, password=None, database=None, use_stub=False) -> None:
        self._rows: dict[str, dict] = {}
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.encrypted = os.getenv("NEO4J_ENCRYPTED", "false").lower() == "true"
        self._driver = None
        self._use_stub = use_stub or (GraphDatabase is None)
        
        if not self._use_stub:
            self._initialize_driver()
        else:
            print("⚠️ Neo4j not installed or use_stub=True. Running in stub mode.")

    def _initialize_driver(self, max_retries: int = 3, retry_delay: float = 2.0) -> None:
        """Initialize the Neo4j driver with retry logic."""
        last_error = None
        for attempt in range(max_retries):
            try:
                if self._driver:
                    self._driver.close()
                
                self._driver = GraphDatabase.driver(
                    self.uri, auth=(self.user, self.password), encrypted=self.encrypted,
                    connection_timeout=10, max_connection_lifetime=3600
                )
                with self._driver.session() as session:
                    result = session.run("RETURN 1 AS test")
                    if result.single()["test"] == 1:
                        print(f"✅ Successfully connected to Neo4j at {self.uri}")
                        return
            except Exception as e:
                last_error = e
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
        
        error_msg = f"❌ Failed to connect to Neo4j after {max_retries} attempts. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    def _check_driver(self) -> None:
        """Ensure the driver is initialized and connection is active."""
        if self._use_stub:
            return
        try:
            with self._driver.session() as session:
                session.run("RETURN 1").single()
        except Exception as e:
            logger.warning(f"⚠️ Neo4j connection lost, attempting to reconnect: {e}")
            self._initialize_driver()

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if not self._use_stub and self._driver:
            self._driver.close()

    def _execute_query(self, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a query with parameters."""
        if self._use_stub:
            # This is a stub, so we can't really execute queries.
            # We'll return an empty list, which is the default for read queries.
            return []
        self._check_driver()
        with self._driver.session(database=self.database) as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

    def save_glyph(self, glyph_data: Dict[str, Any]) -> bool:
        """Save a single glyph to the Neo4j database."""
        if self._use_stub:
            glyph_id = str(glyph_data.get('id', f'glyph-{datetime.now().timestamp()}'))
            self._rows[glyph_id] = glyph_data
            return True

        if not isinstance(glyph_data, dict):
            logger.error("Invalid glyph data provided to save_glyph")
            return False

        self._check_driver()
        try:
            glyph_id = str(glyph_data.get('id', f'glyph-{datetime.now().timestamp()}'))
            params = {
                'id': glyph_id,
                'type': glyph_data.get('type', 'generic'),
                'timestamp': int(glyph_data.get('timestamp', time.time())),
                'agent': glyph_data.get('meta', {}).get('agent', 'unknown'),
                'content': json.dumps(glyph_data.get('payload', {})),
                'metadata': json.dumps(glyph_data.get('meta', {})),
                'created_at': int(time.time())
            }
            query = """
            MERGE (g:Glyph {id: $id})
            SET g.type = $type, g.timestamp = $timestamp, g.agent = $agent,
                g.content = $content, g.metadata = $metadata, g.created_at = $created_at,
                g.updated_at = timestamp()
            """
            with self._driver.session(database=self.database) as session:
                session.run(query, params)
            return True
        except Exception as e:
            logger.exception(f"Error saving glyph {glyph_id} to Neo4j: {e}")
            return False

    def get_all_glyphs(self) -> List[Dict[str, Any]]:
        """Retrieve all glyphs from the database."""
        if self._use_stub:
            return list(self._rows.values())

        self._check_driver()
        try:
            query = "MATCH (g:Glyph) RETURN g"
            with self._driver.session(database=self.database) as session:
                results = session.run(query)
                return [record['g']._properties for record in results]
        except Exception as e:
            logger.exception(f"Error retrieving all glyphs from Neo4j: {e}")
            return []

    # -- Methods for test compatibility -- #
    def list_executions(self) -> list[dict]:
        return self.get_all_glyphs()

    def get_execution(self, exec_id: str) -> dict | None:
        if self._use_stub:
            return self._rows.get(exec_id)
        
        self._check_driver()
        try:
            query = "MATCH (g:Glyph {id: $id}) RETURN g"
            with self._driver.session(database=self.database) as session:
                result = session.run(query, {'id': exec_id}).single()
                return result['g']._properties if result else None
        except Exception as e:
            logger.exception(f"Error retrieving execution {exec_id}: {e}")
            return None

def main():
    # Initialize storage
    logging.basicConfig(level=logging.INFO)
    # To test stub mode, set use_stub=True
    neo4j = Neo4jStorage(use_stub=False)
    
    # Create example glyph
    example_glyph_data = {
        'id': "test_glyph_main_1",
        'timestamp': int(datetime.now().timestamp()),
        'type': 'test_concept',
        'payload': {'message': 'Hello from main'},
        'meta': {'source': 'main_test', 'agent': 'test_runner'}
    }
    
    # Save glyph
    success = neo4j.save_glyph(example_glyph_data)
    print(f"Glyph save successful: {success}")
    
    # Get all glyphs
    glyphs = neo4j.get_all_glyphs()
    print(f"\nFound {len(glyphs)} glyphs:")
    for glyph in glyphs:
        print(f"- {glyph.get('id')}: {glyph.get('type')}")
    
    # Close connection
    neo4j.close()

if __name__ == "__main__":
    main()
