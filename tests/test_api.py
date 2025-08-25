"""Tests for API endpoints."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from synergesis.api.app import app
from synergesis.api.dependencies import get_neo
from cognitive_core.glyph_core import GlyphData

@pytest.fixture
def mock_neo4j_storage(mocker):
    """Create a mock Neo4j storage instance."""
    return mocker.MagicMock()

@pytest.fixture
def test_client(mock_neo4j_storage):
    """Create a test client with mocked Neo4j dependency."""
    app.dependency_overrides[get_neo] = lambda: mock_neo4j_storage
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides = {}
        client.close()

def test_list_executions(test_client, mock_neo4j_storage):
    """Test listing executions."""
    now = int(datetime.now().timestamp())
    mock_records = [
        GlyphData(
            id=f"test-exec-{i}", timestamp=now - i * 3600, source="test",
            concept_type="EXECUTED_ACTION", status="executed", polarité="neutral",
            alignement="center", content=f"Test execution {i}",
            metadata={"parent_doc_id": "test-doc", "target_action_id": f"action-{i}"},
            result_structural={"local_entropy_delta": -0.01 * i, "local_resonance_delta": 5.0 * i},
            confidence=0.8 + i * 0.05
        ).model_dump() for i in range(5)
    ]
    mock_neo4j_storage.list_executions.side_effect = lambda limit=None, start_time=None, end_time=None: mock_records[:limit]

    response = test_client.get("/api/v1/executions?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    timestamps = [record["timestamp"] for record in data]
    assert timestamps == sorted(timestamps, reverse=True)

def test_get_execution(test_client, mock_neo4j_storage):
    """Test getting a specific execution."""
    now = int(datetime.now().timestamp())
    mock_record = GlyphData(
        id="test-exec-0", timestamp=now, source="test", concept_type="EXECUTED_ACTION",
        status="executed", content="Test execution 0"
    ).model_dump()
    mock_neo4j_storage.get_execution.return_value = mock_record

    response = test_client.get("/api/v1/executions/test-exec-0")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-exec-0"
    assert data["content"] == "Test execution 0"

def test_get_execution_not_found(test_client, mock_neo4j_storage):
    """Test getting non-existent execution."""
    mock_neo4j_storage.get_execution.return_value = None
    response = test_client.get("/api/v1/executions/nonexistent")
    assert response.status_code == 404

def test_recent_stats(test_client, mock_neo4j_storage):
    """Test getting recent stats."""
    mock_stats = {"total_executions": 5, "avg_confidence": 0.9}
    mock_neo4j_storage.list_executions_stats.return_value = mock_stats
    
    response = test_client.get("/api/v1/executions/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_executions"] == 5
    assert stats["avg_confidence"] == 0.9
