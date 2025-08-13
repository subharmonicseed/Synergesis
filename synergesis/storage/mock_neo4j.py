"""Test-only Neo4j replacement.

The real `Neo4jStorage` opens a driver and executes Cypher; for unit-tests we
just need deterministic, in-memory answers.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class MockNeo4j:
    """Lightweight drop-in used via dependency-override in tests."""

    # ------------------------------------------------------------------ #
    # Public API expected by:
    #   * synergesis.api.execution_history router
    #   * tests/test_execution_history.py and tests/test_fastapi.py
    # ------------------------------------------------------------------ #

    def list_executions(
        self,
        limit: int = 20,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return *fake* executions, newest first."""
        now = datetime.now()
        items: List[Dict[str, Any]] = []
        for i in range(limit):
            ts = int((now - timedelta(minutes=i)).timestamp())
            if start_time and ts < start_time:
                continue
            if end_time and ts > end_time:
                continue

            items.append(
                {
                    "id": f"exec-{i}",
                    "start_ts": ts,
                    "duration_s": 42,
                    "status": "success" if i % 3 else "failed",
                }
            )
        return items

    def list_executions_stats(self, hours: int = 24) -> Dict[str, int]:
        """Very small synthetic statistics payload."""
        total = hours  # one per hour in the simple generator above
        return {"total": total, "success": total - total // 3, "failed": total // 3}

    def get_execution(self, exec_id: str) -> Optional[Dict[str, Any]]:
        """Return one execution – or None if ID unknown."""
        for item in self.list_executions(limit=50):
            if item["id"] == exec_id:
                return item
        return None

    # ------------------------------------------------------------------ #
    # Context-manager helpers so `with get_neo() as neo:` still works.
    # ------------------------------------------------------------------ #
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False
