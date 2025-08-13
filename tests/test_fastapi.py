import pytest
from fastapi.testclient import TestClient
from api.app import app

@pytest.fixture
def test_client():
    """Create a test client."""
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()

def test_root(test_client):
    """Test the root endpoint."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "Synergesis AI Pipeline API is running",
        "version": "1.0.0"
    }
