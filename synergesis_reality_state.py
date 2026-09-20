"""Persistent/application state probes for SYN-REALITY.

These probes verify post-action state through independent read paths:
- SQLiteStateProbe opens a configured SQLite database read-only and runs a
  fixed SELECT query. The model cannot supply SQL.
- LoopbackHttpJsonProbe performs a bounded GET against a configured loopback
  HTTP endpoint and extracts one configured JSON field.

Both probes are deliberately narrow to avoid turning reality verification into
an arbitrary database or network access surface.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from synergesis_reality import RealityObservation


@dataclass(frozen=True)
class SQLiteProbePolicy:
    database_path: Path
    allowed_root: Path
    select_sql: str
    bind_parameter_keys: tuple[str, ...]
    result_column: str
    max_rows: int = 8

    def __post_init__(self):
        root = Path(self.allowed_root).resolve()
        db = Path(self.database_path).resolve()
        try:
            db.relative_to(root)
        except ValueError as exc:
            raise ValueError("SQLite database_path escapes allowed_root") from exc
        normalized = self.select_sql.strip().lower()
        if not normalized.startswith("select "):
            raise ValueError("SQLite reality probe only permits SELECT")
        if ";" in self.select_sql.rstrip(";"):
            raise ValueError("SQLite reality probe forbids multiple statements")
        if not self.result_column.strip():
            raise ValueError("result_column is required")
        if self.max_rows < 1:
            raise ValueError("max_rows must be >= 1")


class SQLiteStateProbe:
    def __init__(self, *, observer_id: str, policy: SQLiteProbePolicy):
        if not observer_id.strip():
            raise ValueError("observer_id is required")
        self.observer_id = observer_id
        self.policy = policy

    def observe(
        self,
        *,
        action_type: str,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[RealityObservation]:
        binds = []
        for key in self.policy.bind_parameter_keys:
            if key not in parameters:
                raise ValueError(
                    f"SQLite reality probe missing parameter: {key}"
                )
            binds.append(parameters[key])

        db = Path(self.policy.database_path).resolve()
        if not db.exists():
            facts = {
                "database_exists": False,
                "found": False,
                "row_count": 0,
                "value": None,
            }
        else:
            uri = f"{db.as_uri()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            try:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    self.policy.select_sql,
                    tuple(binds),
                ).fetchmany(self.policy.max_rows + 1)
            finally:
                conn.close()

            truncated = len(rows) > self.policy.max_rows
            rows = rows[: self.policy.max_rows]
            values = []
            for row in rows:
                if self.policy.result_column not in row.keys():
                    raise ValueError(
                        "SQLite reality result_column missing from SELECT result"
                    )
                values.append(row[self.policy.result_column])
            facts = {
                "database_exists": True,
                "found": bool(rows),
                "row_count": len(rows),
                "value": values[0] if values else None,
                "values": values,
                "truncated": truncated,
            }

        return (
            RealityObservation.create(
                observer_id=self.observer_id,
                channel="sqlite_readonly",
                resource=resource,
                facts=facts,
            ),
        )


@dataclass(frozen=True)
class LoopbackHttpJsonPolicy:
    host: str
    port: int
    path_prefix: str
    path_parameter: str
    json_field: str
    timeout_seconds: float
    max_response_bytes: int = 65536

    def __post_init__(self):
        if self.host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("HTTP reality probe only permits loopback hosts")
        if not (1 <= self.port <= 65535):
            raise ValueError("invalid HTTP reality probe port")
        if not self.path_prefix.startswith("/"):
            raise ValueError("path_prefix must start with /")
        if not self.path_parameter.strip() or not self.json_field.strip():
            raise ValueError("path_parameter and json_field are required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be >= 1")


class LoopbackHttpJsonProbe:
    def __init__(
        self,
        *,
        observer_id: str,
        policy: LoopbackHttpJsonPolicy,
    ):
        if not observer_id.strip():
            raise ValueError("observer_id is required")
        self.observer_id = observer_id
        self.policy = policy

    def observe(
        self,
        *,
        action_type: str,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[RealityObservation]:
        raw_value = parameters.get(self.policy.path_parameter)
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError("HTTP path parameter must be a non-empty string")
        encoded = quote(raw_value, safe="")
        host_for_url = (
            f"[{self.policy.host}]"
            if ":" in self.policy.host
            else self.policy.host
        )
        url = (
            f"http://{host_for_url}:{self.policy.port}"
            f"{self.policy.path_prefix}{encoded}"
        )

        status_code = None
        parsed = None
        error_type = None
        json_value = None
        response_bytes = 0

        try:
            request = Request(
                url,
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urlopen(
                request,
                timeout=self.policy.timeout_seconds,
            ) as response:
                status_code = int(response.status)
                body = response.read(self.policy.max_response_bytes + 1)
                response_bytes = len(body)
                if len(body) > self.policy.max_response_bytes:
                    raise ValueError("HTTP reality response exceeds max_response_bytes")
                parsed = json.loads(body.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("HTTP reality response JSON must be an object")
                json_value = parsed.get(self.policy.json_field)
        except HTTPError as exc:
            status_code = int(exc.code)
            error_type = type(exc).__name__
        except URLError as exc:
            error_type = type(exc.reason).__name__
        except OSError as exc:
            error_type = type(exc).__name__

        return (
            RealityObservation.create(
                observer_id=self.observer_id,
                channel="http_json_state",
                resource=resource,
                facts={
                    "status_code": status_code,
                    "json_value": json_value,
                    "response_bytes": response_bytes,
                    "error_type": error_type,
                },
            ),
        )
