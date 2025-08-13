"""Tests for API endpoints."""

import pytest
from datetime import datetime, timedelta

from cognitive_core.glyph_core import GlyphData

@pytest.fixture
def neo4j_storage():
    """Create a Neo4j storage instance."""
    from storage.neo4j_interface import Neo4jStorage
    return Neo4jStorage()

@pytest.fixture
def test_client():
    """Create a test client."""
    from fastapi.testclient import TestClient
    from api.app import app
    
    app.dependency_overrides = {}
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides = {}
        client.close()

@pytest.fixture
def setup_test_data(neo4j_storage):
    """Set up test data in Neo4j."""
    neo = neo4j_storage
    
    # Create test execution records
    now = int(datetime.now().timestamp())
    test_records = [
        GlyphData(
            id=f"test-exec-{i}",
            timestamp=now - i * 3600,  # 1 hour apart
            source="test",
            concept_type="EXECUTED_ACTION",
            status="executed",
            polarité="neutral",
            alignement="center",
            content=f"Test execution {i}",
            metadata={
                "parent_doc_id": "test-doc",
                "target_action_id": f"action-{i}"
            },
            result_structural={
                "local_entropy_delta": -0.01 * i,
                "local_resonance_delta": 5.0 * i
            },
            confidence=0.8 + i * 0.05
        )
        for i in range(5)
    ]
    
    with neo.driver.session(database=neo.database) as session:
        for record in test_records:
            neo.upsert_glyph_node(record)
            
    yield
    
    # Clean up
    with neo.driver.session(database=neo.database) as session:
        session.run("MATCH (e:EXECUTED_ACTION) WHERE e.id STARTS WITH 'test-exec-' DELETE e")

def test_list_executions(setup_test_data, test_client):
    """Test listing executions."""
    response = test_client.get("/api/v1/executions?limit=3")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 3
    
    # Check ordering (newest first)
    timestamps = [record["timestamp"] for record in data]
    assert timestamps == sorted(timestamps, reverse=True)

def test_get_execution(setup_test_data, test_client):
    """Test getting a specific execution."""
    response = test_client.get("/api/v1/executions/test-exec-0")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == "test-exec-0"
    assert data["content"] == "Test execution 0"

def test_get_execution_not_found(test_client):
    """Test getting non-existent execution."""
    response = test_client.get("/api/v1/executions/nonexistent")
    assert response.status_code == 404

def test_recent_stats(setup_test_data, test_client):
    """Test getting recent stats."""
    response = test_client.get("/api/v1/stats/recent?window_hours=24")
    assert response.status_code == 200
    
    stats = response.json()
    assert stats["window_hours"] == 24
    assert stats["execution_count"] == 5
    assert 0.8 <= stats["avg_confidence"] <= 1.0
    assert stats["avg_entropy_delta"] < 0
    assert stats["avg_resonance_delta"] > 0
