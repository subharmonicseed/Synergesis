import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from SynergesisCore_DeepSeek_Pro_Complete import create_app
from fastapi import FastAPI


def test_create_app_returns_fastapi_instance():
    app = create_app()
    assert isinstance(app, FastAPI)
