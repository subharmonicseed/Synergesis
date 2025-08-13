"""API endpoints for execution history."""

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from typing import List, Optional
from ..storage.neo4j_interface import Neo4jStorage
from ..cognitive_core.glyph_core import GlyphData
from synergesis.api.dependencies import get_neo

router = APIRouter(tags=["Execution history"])

@router.get("/executions")
def list_executions(
    limit: int | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    neo = Depends(get_neo)
):
    return neo.list_executions(limit, start_time, end_time)

@router.get("/executions/stats")
def list_stats(neo = Depends(get_neo)):
    return neo.list_executions_stats()

@router.get("/executions/{execution_id}")
def get_execution(execution_id: str, neo = Depends(get_neo)):
    res = neo.get_execution(execution_id)
    if res is None:
        raise HTTPException(404, "Not found")
    return res
