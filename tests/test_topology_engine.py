from synergesis.analysis.topology_engine import TopologyEngine
from synergesis.storage.neo4j_interface import Neo4jInterface


def test_topology_engine_init(monkeypatch):
    class FakeNeo4j:
        pass

    engine = TopologyEngine(FakeNeo4j())
    assert isinstance(engine, TopologyEngine)
