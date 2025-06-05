from fastapi import FastAPI
import sys, pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from SynergesisCore_DeepSeek_Pro_Complete import create_app


def test_create_app_returns_fastapi_instance():
    app = create_app()
    assert isinstance(app, FastAPI)
