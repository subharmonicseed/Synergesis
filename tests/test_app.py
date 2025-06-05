import pytest
from fastapi import FastAPI

from SynergesisCore_DeepSeek_Pro_Complete import create_app


def test_create_app_returns_fastapi_instance():
    app = create_app()
    assert isinstance(app, FastAPI)
