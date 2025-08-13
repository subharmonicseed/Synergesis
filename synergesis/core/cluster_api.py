# cluster_api.py
"""
Top-level FastAPI endpoints for cluster_info and metrics, using a global in-memory log and counters.
This file is meant to be imported and included in your main FastAPI app.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import time

router = APIRouter()

from synergesis.core.cluster_state import performance_log, patterns_seen, engine_start_ts, ensure_log

@router.get("/cluster_info")
async def cluster_info():
    if not performance_log:
        raise HTTPException(status_code=404, detail="No clustering data available.")
    return performance_log[-1]

@router.get("/metrics")
async def metrics():
    uptime = int(time.time() - engine_start_ts)
    latest = performance_log[-1] if performance_log else {}
    return {
        "patterns_total": patterns_seen,
        "clusters_total": latest.get("clusters_total", 0),
        "last_cluster_update_ts": latest.get("ts"),
        "avg_cluster_size": latest.get("avg_cluster_size", 0),
        "engine_uptime_s": uptime,
        "patterns_per_min": round(ppm, 2)
    }

# Prometheus text exposition format
@router.get("/metrics/prom", include_in_schema=False)
async def metrics_prom():
    latest = performance_log[-1] if performance_log else {}
    ppm = patterns_seen / (int(time.time() - engine_start_ts) / 60 or 1)
    lines = [
        f"# HELP synergesis_patterns_total Total patterns processed", 
        f"# TYPE synergesis_patterns_total counter", 
        f"synergesis_patterns_total {patterns_seen}",
        f"# HELP synergesis_clusters_total Current number of clusters", 
        f"# TYPE synergesis_clusters_total gauge", 
        f"synergesis_clusters_total {latest.get('clusters_total', 0)}",
        f"# HELP synergesis_avg_cluster_size Average size of clusters", 
        f"# TYPE synergesis_avg_cluster_size gauge", 
        f"synergesis_avg_cluster_size {latest.get('avg_cluster_size', 0)}",
        f"# HELP synergesis_patterns_per_min Ingest rate patterns per minute", 
        f"# TYPE synergesis_patterns_per_min gauge", 
        f"synergesis_patterns_per_min {round(ppm, 2)}",
    ]
    return "\n".join(lines)

# Utility to guarantee at least one log entry
