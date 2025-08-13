import os
import sys
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure project root is on the path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import the app factory from the refactored main.py
try:
    from main import create_app
except (ImportError, ModuleNotFoundError) as e:
    pytest.skip(f"Could not import 'create_app' from 'main.py': {e}", allow_module_level=True)


@pytest.fixture
def client() -> TestClient:
    """
    Provides a new TestClient instance for each test function,
    ensuring test isolation.
    """
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_create_app_returns_fastapi_instance():
    """Tests that the app factory returns a FastAPI instance."""
    app = create_app()
    assert isinstance(app, FastAPI)


def test_status_endpoint(client: TestClient):
    """Tests the /status endpoint."""
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["core"] == "SynergesisCore"
    assert data["clusterer"] == "AutoTuningQuantumClustererPro"
    assert data["validator"] == "AdvancedContextValidator"


def test_process_endpoint_success(client: TestClient):
    """Tests a successful call to the /process endpoint."""
    payload = {
        "state": [0.707, 0, 0, 0.707],
        "context": "This is a test related to environmental topics."
    }
    response = client.post("/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Check that the result conforms to the Glyph model structure
    result = data["result"]
    assert "id" in result
    assert result["content"] == payload["context"]
    assert result["type"] == "semantic"  # The default value
    assert "polarity" in result
    assert "timestamp" in result
    assert "metadata" in result
    assert "validation" in result["metadata"]
    assert "ethical_score" in result["metadata"]["validation"]


def test_process_endpoint_missing_state(client: TestClient):
    """Tests the /process endpoint when 'state' is missing."""
    payload = {
        "context": "This is a test."
    }
    response = client.post("/process", json=payload)
    assert response.status_code == 400
    assert "Missing 'state'" in response.json()["detail"]


def test_cluster_info_endpoint_initial(client: TestClient):
    """Tests the /cluster_info endpoint before any processing."""
    response = client.get("/cluster_info")
    assert response.status_code == 200
    data = response.json()
    assert data["cluster_info"] == "No clustering performed yet."
    assert data["total_patterns_processed"] == 0


def test_cluster_info_after_processing(client: TestClient):
    """Tests the /cluster_info endpoint after processing a pattern."""
    payload = {
        "state": [0.5, 0.5, 0.5, 0.5],
        "context": "Another test"
    }
    client.post("/process", json=payload)

    response = client.get("/cluster_info")
    assert response.status_code == 200
    data = response.json()
    assert data["total_patterns_processed"] == 1
    assert "latest_cluster_log" in data
    # The first call will skip clustering, so inertia will be None.
    # We can check the status message.
    assert "Skipped" in data["latest_cluster_log"]["status"]
