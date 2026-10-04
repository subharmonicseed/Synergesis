"""Real engine/UI workflows with a controlled backend, never a real model."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import pytest

from synergesis_conversation import open_conversation
from synergesis_initiative import InitiativeError, InitiativeProfile
from synergesis_ui import LocalUIService, UIError, probe_provider


class Backend:
    def __init__(self):
        self.calls = []
        self.fail = False

    def reply(self, messages):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("private-provider-sentinel")
        return "Réponse contrôlée [D1], jamais une réponse de modèle réel."


def provider():
    return {"available": True, "model_available": True, "model": "test-local",
            "digest": "test-digest", "error": None}


@pytest.fixture
def service(tmp_path):
    backend = Backend()
    local = LocalUIService(tmp_path / "profile", tmp_path / "ui", model="test-local",
                           backend=backend, provider_probe=provider, internet=True)
    try:
        yield local, backend
    finally:
        local.close()


def perform(service, action, **payload):
    request_id = str(uuid4())
    response = service.submit({"request_id": request_id, "action": action, **payload})
    assert response["operation"]["id"] == request_id
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = service.state()
        if not state["busy"]:
            return state
        time.sleep(0.01)
    pytest.fail("controlled operation did not finish")


def test_memory_survives_service_restart_and_new_conversation(service):
    local, backend = service
    old = local.state()["conversation"]["id"]
    state = perform(local, "remember", text="Mon atelier expérimental est à Bellac.")
    assert state["memories"][0]["created_at"]
    assert state["memories"][0]["claim_status"] == "unverified"
    state = perform(local, "new_conversation")
    assert state["conversation"]["id"] != old
    assert state["conversation"]["messages"] == []
    assert state["memories"][0]["text"].endswith("Bellac.")
    local.close()
    restored = LocalUIService(local.profile_dir, local.root_dir, model="test-local",
                             backend=backend, provider_probe=provider)
    try:
        state = perform(restored, "recall", text="Bellac")
        assert "Bellac" in state["conversation"]["messages"][-1]["content"]
        assert not backend.calls
        state = perform(restored, "recall", text="introuvableXYZ")
        assert "Aucun souvenir" in state["conversation"]["messages"][-1]["content"]
    finally:
        restored.close()


def test_failure_consumes_turn_recovers_and_does_not_enter_history(service):
    local, backend = service
    backend.fail = True
    state = perform(local, "message", text="Message qui échoue")
    assert state["operation"]["status"] == "failed" and not state["busy"]
    assert state["conversation"]["attempts"] == 1
    assert "private-provider-sentinel" not in json.dumps(state)
    backend.fail = False
    state = perform(local, "message", text="Reprise")
    assert state["operation"]["status"] == "succeeded"
    assert state["conversation"]["attempts"] == 2
    assert backend.calls[-1] == [{"role": "user", "content": "Reprise"}]
    assert state["conversation"]["messages"][-1]["receipt"]["cycle_glyph_id"]


def test_twenty_turn_limit_counts_failed_attempts(service):
    local, backend = service
    backend.fail = True
    for _ in range(20):
        state = perform(local, "message", text="Échec contrôlé")
    assert state["conversation"]["remaining_turns"] == 0
    assert len(backend.calls) == 20
    state = perform(local, "message", text="Un tour de trop")
    assert state["operation"]["status"] == "failed"
    assert len(backend.calls) == 20
    state = perform(local, "new_conversation")
    assert state["conversation"]["attempts"] == 0
    assert state["limits"]["search_remaining"] == 3


def test_profile_command_limit_is_separate_from_turns(service):
    local, backend = service
    for _ in range(32):
        state = perform(local, "recall", text="introuvableXYZ")
    assert state["limits"]["profile_commands_remaining"] == 0
    state = perform(local, "remember", text="Un souvenir de trop")
    assert state["operation"]["status"] == "failed"
    assert not state["memories"] and not backend.calls
    state = perform(local, "new_conversation")
    assert state["limits"]["profile_commands_remaining"] == 32


def test_targeted_step_preserves_older_pending_question(tmp_path):
    profile = InitiativeProfile(tmp_path / "profile")
    old = profile.add_question("Ancienne question zirconium")
    target = profile.add_question("QUOTATEST")
    document = tmp_path / "test.md"
    document.write_text("QUOTATEST : le plafond inédit est 741.\n", encoding="utf-8")
    result = profile.step([document], question_id=target)
    assert result["question_id"] == target
    assert [q["id"] for q in profile.pending()] == [old]
    with pytest.raises(InitiativeError, match="not pending"):
        profile.step([document], question_id=target)


def test_scoped_turns_still_respect_complete_history_budget(tmp_path):
    profile = InitiativeProfile(tmp_path / "profile")
    question = profile.add_question("QUOTATEST")
    result = profile.step([], question_id=question)
    class LargeBackend:
        calls = 0
        def reply(self, messages):
            self.calls += 1
            return "x" * 8000
    backend = LargeBackend()
    with open_conversation(tmp_path / "conversation", backend, profile=profile) as conversation:
        text = "QUOTATEST " + "y" * 2490
        conversation.turn(text, source_receipt_id=result["receipt_id"])
        conversation.turn(text, source_receipt_id=result["receipt_id"])
        with pytest.raises(ValueError, match="32000"):
            conversation.turn(text, source_receipt_id=result["receipt_id"])
        assert backend.calls == 2 and conversation._attempts == 2


def test_document_selection_excludes_previous_receipts_memories_and_history(service):
    local, backend = service
    perform(local, "remember", text="QUOTATEST secret mémoire : 999.")
    state = perform(local, "upload_document", name="A.md", content="QUOTATEST : le code inédit est 741.\n")
    doc_a = state["documents"][0]["id"]
    state = perform(local, "document_question", document_id=doc_a, text="QUOTATEST code ?")
    assert state["operation"]["status"] == "succeeded"
    supplied = backend.calls[-1]
    assert len(supplied) == 1 and "741" in supplied[0]["content"]
    assert "QUOTATEST secret mémoire : 999." not in supplied[0]["content"]
    source = state["sources"][0]
    assert source["title"] == "A.md" and source["line"] == 1
    assert source["sha256"] and source["receipt_id"] and source["retrieved_at"]
    assert source["supplied"] is True and source["cited"] is True
    state = perform(local, "upload_document", name="B.txt", content="Un autre document parle uniquement de cuivre.\n")
    doc_b = state["documents"][-1]["id"]
    state = perform(local, "document_question", document_id=doc_b, text="QUOTATEST code ?")
    assert state["operation"]["status"] == "succeeded"
    supplied = backend.calls[-1]
    assert len(supplied) == 1
    assert "le code inédit est 741" not in supplied[0]["content"]
    assert "QUOTATEST secret mémoire : 999." not in supplied[0]["content"]
    assert "no_evidence" in supplied[0]["content"]
    assert state["conversation"]["messages"][-1]["receipt"]["source_references"] == []


def test_three_searches_shared_between_web_and_document_reset_only_on_new_conversation(service):
    local, backend = service
    class Research:
        def search(self, query):
            return []
    local._profile._web_research = Research()
    state = perform(local, "upload_document", name="test.txt", content="QUOTATEST : trois.\n")
    doc_id = state["documents"][0]["id"]
    state = perform(local, "web", text="controlled arxiv")
    assert state["limits"]["search_remaining"] == 2
    perform(local, "document_question", document_id=doc_id, text="QUOTATEST")
    state = perform(local, "web", text="controlled arxiv")
    assert state["limits"]["search_remaining"] == 0
    state = perform(local, "document_question", document_id=doc_id, text="QUOTATEST")
    assert state["operation"]["status"] == "failed"
    assert len(backend.calls) == 1
    assert len(local._profile.pending()) == 0
    state = perform(local, "new_conversation")
    assert state["limits"]["search_remaining"] == 3
    assert len(state["documents"]) == 1
    state = perform(local, "document_question", document_id=doc_id, text="QUOTATEST")
    assert state["operation"]["status"] == "succeeded"
    assert state["limits"]["search_remaining"] == 2


def test_service_singleton_profile_and_root_then_releases(service, tmp_path):
    local, backend = service
    with pytest.raises(RuntimeError, match="déjà"):
        LocalUIService(local.profile_dir, tmp_path / "other-ui", backend=backend,
                       provider_probe=provider)
    with pytest.raises(RuntimeError, match="déjà"):
        LocalUIService(tmp_path / "other-profile", local.root_dir, backend=backend,
                       provider_probe=provider)


def test_actual_local_http_transport_tags_and_trace(tmp_path):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/tags"
            self._send({"models": [{"name": "test-local:latest", "digest": "abc"}]})

        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self._send({"done": True, "model": "test-local:latest",
                        "message": {"content": "HTTP contrôlé, aucun modèle réel."}})

        def _send(self, body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    local = None
    try:
        absent = probe_provider("absent", server.server_port)
        assert absent["available"] and not absent["model_available"]
        local = LocalUIService(tmp_path / "profile", tmp_path / "ui", model="test-local",
                               ollama_port=server.server_port)
        state = perform(local, "message", text="Bonjour")
        assert state["provider"]["available"] and state["provider"]["model_available"]
        assert state["provider"]["digest"] == "abc"
        assert state["provider"]["last_model"] == "test-local:latest"
        trace = [json.loads(line) for line in (tmp_path / "ui" / "transport.jsonl").read_text().splitlines()]
        assert len(requests) == len(trace) == 1
        assert trace[0]["request"] == requests[0]
        assert trace[0]["request"]["messages"][0]["role"] == "system"
        assert trace[0]["request"]["stream"] is False and "format" not in trace[0]["request"]
        assert trace[0]["response"]["message"]["content"] == state["conversation"]["messages"][-1]["content"]
        assert local.backend.timeout == 180
    finally:
        if local:
            local.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_service_opens_when_provider_unavailable(tmp_path):
    provider_down = lambda: {"available": False, "model_available": False,
        "model": "test-local", "error": "Ollama indisponible"}
    local = LocalUIService(tmp_path / "profile", tmp_path / "ui", backend=Backend(),
                           provider_probe=provider_down)
    try:
        assert local.state()["app"] == "synergesis-local-ui"
        assert not local.state()["provider"]["available"]
        assert local.state()["conversation"]["id"]
    finally:
        local.close()


def test_shutdown_refuses_active_job_then_worker_closes_its_context(service):
    local, backend = service
    entered, release = threading.Event(), threading.Event()
    def wait_reply(messages):
        entered.set()
        assert release.wait(5)
        return "Réponse contrôlée avant arrêt."
    backend.reply = wait_reply
    local.submit({"request_id": str(uuid4()), "action": "message", "text": "Bonjour"})
    assert entered.wait(5)
    with pytest.raises(UIError) as error:
        local.submit({"request_id": str(uuid4()), "action": "shutdown"})
    assert error.value.status == 409
    release.set()
    deadline = time.monotonic() + 5
    while local.state()["busy"] and time.monotonic() < deadline:
        time.sleep(0.01)
    perform(local, "shutdown")
    assert local._stopped.wait(5)
    assert local._context is None and local._session is None
    with pytest.raises(UIError) as error:
        local.submit({"request_id": str(uuid4()), "action": "message", "text": "Trop tard"})
    assert error.value.status == 503
