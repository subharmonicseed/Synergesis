from functools import lru_cache
from synergesis.storage.neo4j_interface import Neo4jStorage

@lru_cache
def get_neo() -> Neo4jStorage:
    """Get Neo4j interface instance."""
    return Neo4jStorage()
