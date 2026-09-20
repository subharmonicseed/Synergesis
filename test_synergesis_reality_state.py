import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import sqlite3
import threading
from pathlib import Path

import pytest

from synergesis_reality_state import (
    LoopbackHttpJsonPolicy,
    LoopbackHttpJsonProbe,
    SQLiteProbePolicy,
    SQLiteStateProbe,
)


def test_sqlite_probe_reads_real_persistent_state(tmp_path):
    root = tmp_path / "db"
    root.mkdir()
    db = root / "state.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute("INSERT INTO kv(k,v) VALUES (?,?)", ("alpha", "one"))
        conn.commit()
    finally:
        conn.close()

    probe = SQLiteStateProbe(
        observer_id="db:sqlite",
        policy=SQLiteProbePolicy(
            database_path=db,
            allowed_root=root,
            select_sql="SELECT v AS value FROM kv WHERE k = ?",
            bind_parameter_keys=("key",),
            result_column="value",
        ),
    )
    observation = probe.observe(
        action_type="db.put",
        resource="action:db.put",
        parameters={"key": "alpha", "value": "one"},
    )[0]
    assert observation.facts["database_exists"] is True
    assert observation.facts["found"] is True
    assert observation.facts["value"] == "one"


def test_sqlite_probe_reports_missing_row(tmp_path):
    root = tmp_path / "db"
    root.mkdir()
    db = root / "state.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
        conn.commit()
    finally:
        conn.close()

    probe = SQLiteStateProbe(
        observer_id="db:sqlite",
        policy=SQLiteProbePolicy(
            database_path=db,
            allowed_root=root,
            select_sql="SELECT v AS value FROM kv WHERE k = ?",
            bind_parameter_keys=("key",),
            result_column="value",
        ),
    )
    observation = probe.observe(
        action_type="db.put",
        resource="action:db.put",
        parameters={"key": "missing"},
    )[0]
    assert observation.facts["found"] is False
    assert observation.facts["value"] is None


def test_sqlite_probe_is_read_only_and_rejects_non_select(tmp_path):
    root = tmp_path / "db"
    root.mkdir()
    with pytest.raises(ValueError, match="only permits SELECT"):
        SQLiteProbePolicy(
            database_path=root / "state.sqlite",
            allowed_root=root,
            select_sql="DELETE FROM kv",
            bind_parameter_keys=(),
            result_column="value",
        )


def test_sqlite_probe_rejects_database_outside_allowed_root(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes allowed_root"):
        SQLiteProbePolicy(
            database_path=tmp_path / "outside.sqlite",
            allowed_root=root,
            select_sql="SELECT 1 AS value",
            bind_parameter_keys=(),
            result_column="value",
        )


class _StateHandler(BaseHTTPRequestHandler):
    state = {}

    def do_GET(self):
        if not self.path.startswith("/state/"):
            self.send_response(404)
            self.end_headers()
            return
        key = self.path[len("/state/"):]
        from urllib.parse import unquote
        key = unquote(key)
        if key not in self.state:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"value": self.state[key]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def _server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_http_json_probe_reads_real_loopback_api_state():
    _StateHandler.state = {"alpha": "one"}
    server, thread = _server()
    try:
        probe = LoopbackHttpJsonProbe(
            observer_id="api:http",
            policy=LoopbackHttpJsonPolicy(
                host="127.0.0.1",
                port=server.server_address[1],
                path_prefix="/state/",
                path_parameter="key",
                json_field="value",
                timeout_seconds=0.5,
            ),
        )
        observation = probe.observe(
            action_type="api.set",
            resource="action:api.set",
            parameters={"key": "alpha", "value": "one"},
        )[0]
        assert observation.facts["status_code"] == 200
        assert observation.facts["json_value"] == "one"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_json_probe_reports_missing_state():
    _StateHandler.state = {}
    server, thread = _server()
    try:
        probe = LoopbackHttpJsonProbe(
            observer_id="api:http",
            policy=LoopbackHttpJsonPolicy(
                host="127.0.0.1",
                port=server.server_address[1],
                path_prefix="/state/",
                path_parameter="key",
                json_field="value",
                timeout_seconds=0.5,
            ),
        )
        observation = probe.observe(
            action_type="api.set",
            resource="action:api.set",
            parameters={"key": "missing"},
        )[0]
        assert observation.facts["status_code"] == 404
        assert observation.facts["json_value"] is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_json_policy_rejects_non_loopback():
    with pytest.raises(ValueError, match="only permits loopback"):
        LoopbackHttpJsonPolicy(
            host="example.com",
            port=443,
            path_prefix="/state/",
            path_parameter="key",
            json_field="value",
            timeout_seconds=0.5,
        )
