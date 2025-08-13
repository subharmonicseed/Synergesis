from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # keep type hints happy in IDEs – resolved at runtime below
    from ..storage.neo4j_interface import Neo4jStorage

def get_neo():
    """Return a storage implementation (real or stub)."""
    try:
        # running in production → import the heavy driver
        from ..storage.neo4j_interface import Neo4jStorage  # type: ignore
        return Neo4jStorage()
    except Exception:
        # unit-tests / CI → fall back to fast stub
        from ..storage.mock_neo4j import MockNeo4j  # local import to avoid cost
        return MockNeo4j()
