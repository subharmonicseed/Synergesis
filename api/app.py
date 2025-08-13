"""Main FastAPI application."""

import logging
from fastapi import FastAPI, HTTPException, Request

# --- Routers ------------------------------------------------------------
from synergesis.api.execution_history import router

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Synergesis AI Pipeline")

# ❶ mount the history router
app.include_router(router, prefix="/api/v1")

# --- Endpoints ----------------------------------------------------------

@app.get("/", tags=["Meta"])
def root(_: Request):
    """Petit health-check JSON simple."""
    return {"status": "ok", "message": "Synergesis AI Pipeline API is running", "version": "1.0.0"}
