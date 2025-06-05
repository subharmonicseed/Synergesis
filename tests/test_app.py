from pathlib import Path
import sys

from fastapi import FastAPI

sys.path.append(str(Path(__file__).resolve().parents[1]))

from SynergesisCore_DeepSeek_Pro_Complete import create_app  # noqa: E402


def test_create_app_returns_fastapi_instance():
    app = create_app()
    assert isinstance(app, FastAPI)

