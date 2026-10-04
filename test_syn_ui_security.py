"""Independent local HTTP safety tests; no Ollama or Internet request occurs."""
import http.client
import json
import threading
import time
from uuid import uuid4

import pytest

from synergesis_ui import (
    MAX_BODY_BYTES, MAX_DOCUMENT_BYTES, LocalUIService, create_server,
)


class ControlledBackend:
    def __init__(self):
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.fail = False

    def reply(self, messages):
        self.calls.append(messages)
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("fixture wait expired")
        if self.fail:
            self.fail = False
            raise RuntimeError("private-provider-error-sentinel")
        return "Réponse contrôlée <script>alert('untrusted')</script>."


@pytest.fixture
def local_http(tmp_path):
    backend = ControlledBackend()
    service = LocalUIService(tmp_path / "profile", tmp_path / "service",
        backend=backend, provider_probe=lambda: {
            "available": True, "model_available": True, "model": "fixture",
            "digest": None, "error": None})
    server = create_server(service, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield service, server, backend
    backend.release.set()
    server.shutdown()
    thread.join(3)
    server.server_close()
    service.close(timeout=10)


def request(local_http, payload=None, *, method="POST", path="/api/action",
            headers=None, raw=None):
    service, server, _ = local_http
    if raw is None:
        raw = json.dumps(payload or {"action": "message", "text": "Bonjour",
            "request_id": str(uuid4())}, ensure_ascii=False).encode("utf-8")
    if headers is None:
        headers = [
            ("Host", f"127.0.0.1:{server.server_port}"),
            ("Origin", f"http://127.0.0.1:{server.server_port}"),
            ("Sec-Fetch-Site", "same-origin"),
            ("X-Syn-Token", service.csrf_token),
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(raw))),
        ]
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in headers:
            connection.putheader(name, value)
        connection.endheaders(raw if method == "POST" else None)
        response = connection.getresponse()
        content = response.read()
        body = json.loads(content) if content else {}
        return response.status, dict(response.getheaders()), body
    finally:
        connection.close()


def valid_headers(local_http, raw=b"{}"):
    service, server, _ = local_http
    return [
        ("Host", f"127.0.0.1:{server.server_port}"),
        ("Origin", f"http://127.0.0.1:{server.server_port}"),
        ("Sec-Fetch-Site", "same-origin"),
        ("X-Syn-Token", service.csrf_token),
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(raw))),
    ]


def wait_idle(service):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = service.state()
        if not state["busy"]:
            return state
        time.sleep(0.01)
    pytest.fail("operation remained busy")


def test_loopback_headers_and_no_cross_origin_read(local_http):
    service, server, backend = local_http
    assert server.server_address[0] == "127.0.0.1"
    status, headers, state = request(local_http, method="GET", path="/api/state")
    assert status == 200 and state["instance_id"] == service.instance_id
    assert headers["Content-Type"].startswith("application/json")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers
    assert backend.calls == []


@pytest.mark.parametrize("name,values", [
    ("Host", ["attacker.example:8765"]),
    ("Host", ["localhost:8765"]),
    ("Host", ["duplicate", "duplicate"]),
    ("Origin", ["https://attacker.example"]),
    ("Origin", ["null"]),
    ("Origin", ["duplicate", "duplicate"]),
    ("Sec-Fetch-Site", ["cross-site"]),
    ("Sec-Fetch-Site", ["same-site"]),
    ("Sec-Fetch-Site", ["same-origin", "same-origin"]),
    ("X-Syn-Token", []),
    ("X-Syn-Token", ["wrong"]),
    ("X-Syn-Token", ["duplicate", "duplicate"]),
])
def test_csrf_rebinding_and_duplicate_headers(local_http, name, values):
    raw = b"{}"
    headers = valid_headers(local_http, raw)
    real = next(value for key, value in headers if key == name)
    headers = [(key, value) for key, value in headers if key != name]
    headers.extend((name, real if value == "duplicate" else value) for value in values)
    status, _, body = request(local_http, raw=raw, headers=headers)
    assert status == 403 and body["error"]
    assert local_http[2].calls == []
    assert local_http[0].state()["busy"] is False


def test_third_party_reads_cannot_obtain_token(local_http):
    headers = valid_headers(local_http)
    headers = [(key, "https://attacker.example" if key == "Origin" else value)
               for key, value in headers]
    status, _, body = request(local_http, method="GET", path="/api/state", headers=headers)
    assert status == 403
    assert "csrf_token" not in body


@pytest.mark.parametrize("name,values,status", [
    ("Content-Length", [], 411),
    ("Content-Length", ["-1"], 411),
    ("Content-Length", ["2", "2"], 411),
    ("Content-Length", [str(MAX_BODY_BYTES + 1)], 413),
    ("Content-Type", ["text/plain"], 415),
    ("Content-Type", ["application/json", "application/json"], 415),
    ("Transfer-Encoding", ["chunked"], 400),
])
def test_http_body_framing_is_bounded(local_http, name, values, status):
    headers = [(key, value) for key, value in valid_headers(local_http) if key != name]
    headers.extend((name, value) for value in values)
    actual, _, body = request(local_http, headers=headers, raw=b"{}")
    assert actual == status and body["error"]


@pytest.mark.parametrize("raw", [
    b"{", b"\xff", b"[]", b"null",
    b'{"action":"message","action":"remember"}',
])
def test_invalid_json_is_rejected_without_model_call(local_http, raw):
    status, _, body = request(local_http, raw=raw, headers=valid_headers(local_http, raw))
    assert status == 400 and body["error"]
    assert local_http[2].calls == []


@pytest.mark.parametrize("action", [[], {}, 3, None, "unknown"])
def test_invalid_action_types_return_json_error(local_http, action):
    status, _, body = request(local_http, {"request_id": str(uuid4()), "action": action})
    assert status == 400 and body["error"]


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE", "OPTIONS"])
def test_unsupported_methods_do_not_mutate(local_http, method):
    status, _, body = request(local_http, method=method)
    assert status == 405 and body["error"]
    assert local_http[2].calls == []


def test_double_submission_and_busy_are_serialized(local_http):
    service, _, backend = local_http
    backend.release.clear()
    payload = {"request_id": str(uuid4()), "action": "message", "text": "cuivre"}
    status, _, first = request(local_http, payload)
    assert status == 202 and first["operation"]["status"] == "running"
    assert backend.entered.wait(3)
    status, _, second = request(local_http, payload)
    assert status == 202 and second["duplicate"] is True
    status, _, _ = request(local_http, {**payload, "text": "autre"})
    assert status == 409
    status, _, _ = request(local_http, {**payload, "request_id": str(uuid4())})
    assert status == 409
    backend.release.set()
    state = wait_idle(service)
    assert state["operation"]["status"] == "succeeded"
    status, _, replay = request(local_http, payload)
    assert status == 202 and replay["duplicate"] is True
    assert replay["operation"]["status"] == "succeeded"
    assert len(backend.calls) == 1
    assert state["conversation"]["attempts"] == 1
    assert state["conversation"]["messages"][-1]["content"] == \
        "Réponse contrôlée <script>alert('untrusted')</script>."


def test_provider_error_releases_busy_and_excludes_failed_history(local_http):
    service, _, backend = local_http
    backend.fail = True
    assert request(local_http, {"request_id": str(uuid4()), "action": "message",
        "text": "private-failed-question"})[0] == 202
    state = wait_idle(service)
    assert state["operation"]["status"] == "failed"
    assert state["conversation"]["attempts"] == 1
    assert "private-provider-error-sentinel" not in json.dumps(state)
    assert request(local_http, {"request_id": str(uuid4()), "action": "message",
        "text": "reprise"})[0] == 202
    state = wait_idle(service)
    assert state["operation"]["status"] == "succeeded"
    assert state["conversation"]["attempts"] == 2
    assert backend.calls[-1] == [{"role": "user", "content": "reprise"}]


def test_empty_message_is_ignored(local_http):
    status, _, body = request(local_http, {"request_id": str(uuid4()),
        "action": "message", "text": " \n\t "})
    assert status == 202 and body["ignored"] is True
    assert local_http[0].state()["conversation"]["attempts"] == 0
    assert local_http[0].state()["busy"] is False
    assert local_http[2].calls == []


@pytest.mark.parametrize("name", [
    "../secret.txt", "/etc/passwd.txt", "C:\\secret.txt", "notes.html",
    "notes.txt/../../secret.txt", "notes.txt:stream", "NUL.txt", "notes\x00.txt",
])
def test_upload_refuses_paths_and_other_formats(local_http, name):
    status, _, body = request(local_http, {"request_id": str(uuid4()),
        "action": "upload_document", "name": name, "content": "cuivre"})
    assert status == 400 and body["error"]
    assert local_http[0].state()["documents"] == []


def test_upload_is_byte_bounded_and_browser_cannot_supply_path(local_http):
    payload = {"request_id": str(uuid4()), "action": "upload_document",
        "name": "notes.md", "content": "é" * (MAX_DOCUMENT_BYTES // 2 + 1)}
    assert request(local_http, payload)[0] == 413
    payload.update(request_id=str(uuid4()), content="cuivre", path="/etc/passwd")
    assert request(local_http, payload)[0] == 400
    assert local_http[0].state()["documents"] == []


def test_unknown_static_paths_never_serve_local_files(local_http):
    for path in ["/../synergesis_ui.py", "/uploads/notes.md", "/api/state?x=1"]:
        status, _, body = request(local_http, method="GET", path=path)
        assert status == 404 and body["error"]


def test_duplicate_server_profiles_are_locked_and_released(local_http, tmp_path):
    service, _, _ = local_http
    with pytest.raises(RuntimeError, match="déjà"):
        LocalUIService(service.profile_dir, tmp_path / "other-service",
            backend=ControlledBackend(), provider_probe=lambda: {})
    with pytest.raises(RuntimeError, match="déjà"):
        LocalUIService(tmp_path / "other-profile", service.root_dir,
            backend=ControlledBackend(), provider_probe=lambda: {})
