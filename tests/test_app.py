import os
import sys
import pytest
from fastapi import FastAPI

# Ensure project root is on the path for direct invocation of pytest
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from SynergesisCore_DeepSeek_Pro_Complete import create_app
except Exception as exc:  # pragma: no cover - skip if optional deps missing
    pytest.skip(f"SynergesisCore_DeepSeek_Pro_Complete unavailable: {exc}", allow_module_level=True)


def test_create_app_returns_fastapi_instance():
    app = create_app()
    assert isinstance(app, FastAPI)
