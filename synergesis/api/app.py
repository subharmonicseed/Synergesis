"""Main FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .execution_history import router

app = FastAPI(title="Synergesis AI Pipeline")

app.include_router(router, prefix="/api/v1")

@app.get("/", tags=["meta"])
def root(_: Request):
    """Health-check."""
    return {
        "status": "ok",
        "message": "Synergesis AI Pipeline API is running",
        "version": "1.0.0",
    }
