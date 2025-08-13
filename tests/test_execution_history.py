import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from synergesis.api.app import app

class FakeNeo:
    """Minimal stub used in API unit-tests."""
    pass

@pytest.fixture(autouse=True)
def override_neo(monkeypatch):
    """Override the dependency with our in-memory stub."""
    import synergesis.api.execution_history as eh
    monkeypatch.setattr(eh, "get_neo", lambda: FakeNeo())

@pytest.fixture()
def test_client():
    return TestClient(app)

def test_root_endpoint(test_client):
    """Test the root endpoint."""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['message'] == 'Synergesis AI Pipeline API is running'
    assert data['version'] == '1.0.0'

def test_list_executions(test_client):
    """Test listing executions."""
    response = test_client.get("/api/v1/executions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_list_executions_with_limit(test_client):
    """Test listing executions with limit."""
    response = test_client.get("/api/v1/executions?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5

def test_list_executions_with_time_range(test_client):
    """Test listing executions with time range."""
    now = int(datetime.now().timestamp())
    start_time = now - 3600  # 1 hour ago
    end_time = now
    
    response = test_client.get(f"/api/v1/executions?start_time={start_time}&end_time={end_time}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_get_execution(test_client):
    """Test getting a specific execution."""
    response = test_client.get("/api/v1/executions/123")
    assert response.status_code == 404
    data = response.json()
    assert data['detail'].lower() == 'not found'

def test_get_recent_stats(test_client):
    """Test getting recent execution statistics."""
    response = test_client.get("/api/v1/executions/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert data == {"count": 0, "success": 0, "failure": 0}
