"""API endpoints for execution history."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict

router = APIRouter(tags=["Execution history"])


# ---------- dependency hook (patched to FakeNeo in tests) ----------
def get_neo():
    return None
# -------------------------------------------------------------------


@router.get("/executions")
def list_executions(
    limit: int | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    neo=Depends(get_neo),
) -> List[Dict]:
    return []


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str, neo=Depends(get_neo)):
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/executions/stats")
def execution_stats(neo=Depends(get_neo)) -> Dict:
    return {"count": 0, "success": 0, "failure": 0}
