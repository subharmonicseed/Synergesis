"""Configuration for pytest."""

import pytest
from types import SimpleNamespace

class FakeNeo(SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.calls = []

    def list_executions(self, *a, **k):
        return []

    def list_executions_stats(self):
        return {"count": 0, "success": 0, "failure": 0}

    def get_execution(self, _id):
        return None

@pytest.fixture(autouse=True)
def override_neo(mocker):
    mocker.patch(
        "synergesis.api.dependencies.get_neo",  # chemin ABSOLU
        return_value=FakeNeo(),
    )

@pytest.fixture
def test_client():
    from synergesis.api.app import app
    return TestClient(app)
