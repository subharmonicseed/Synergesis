"""Supervisor/UI integration with SIMULATED arXiv and Ollama HTTP only.

These fixtures exercise the real single engine worker, ledgers, control queue
and recovery paths. They never call arXiv, a model server, or an installed model.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import threading
import time
from uuid import uuid4

import pytest

import synergesis_ui as ui
from synergesis_conversation import ConversationSession
from synergesis_ollama_backend import OllamaBackend
from synergesis_supervisor import Supervisor, _read_atomic
from synergesis_web_research import ArxivWebResearch


def wait_for(local, predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = local.state()
        if predicate(state):
            return state
        time.sleep(0.01)
    pytest.fail("Simulated UI condition was not reached: " + repr(local.state()))


def submit(local, action, **payload):
    request = {"request_id": str(uuid4()), "action": action, **payload}
    local.submit(request)
    return request


def perform(local, action, **payload):
    request = submit(local, action, **payload)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        response = local.submit(request)  # Exact duplicate only reads its receipt.
        if response["operation"]["status"] != "running":
            return response["operation"]
        time.sleep(0.01)
    pytest.fail("Simulated operation did not finish")


def start(local, queries=None, **extra):
    return submit(local, "mission_start", text="Mission fictive contrôlée",
                  queries=queries or ["test-arxiv-a", "test-arxiv-b"], authorized=True, **extra)


class ControlledResponse:
    status = 200

    def __init__(self):
        self.data = json.dumps({"done": True, "model": "test-local:latest",
            "message": {"content": "Synthèse SIMULÉE issue du transport contrôlé. [W1]"}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.data[:size]


class ControlledOpener:
    def __init__(self, *, blocked=False):
        self.calls = []
        self.entered, self.release = threading.Event(), threading.Event()
        if not blocked:
            self.release.set()

    def open(self, request, *, timeout):
        self.calls.append({"body": json.loads(request.data), "timeout": timeout,
                           "thread": threading.get_ident()})
        self.entered.set()
        if not self.release.wait(10):
            raise TimeoutError("Controlled simulated socket remains blocked")
        return ControlledResponse()


@pytest.fixture
def harness(tmp_path, monkeypatch):
    environment = SimpleNamespace(services=[], openers=[], searches=[], fail_source=False)

    def search(_adapter, query):
        environment.searches.append({"query": query, "thread": threading.get_ident()})
        if environment.fail_source:
            raise ConnectionResetError("Controlled source outcome is unknown")
        text = "Abstract SIMULÉ : " + query
        return [{"path": "https://arxiv.org/abs/2401.12345v1", "line": 1,
            "title": "Publication fictive contrôlée", "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "hash_scope": "stored_excerpt_utf8", "excerpt_truncated": False,
            "retrieved_at": "2026-10-11T00:00:00Z",
            "claim_status": "remote_abstract_unverified"}]

    monkeypatch.setattr(ArxivWebResearch, "search", search)

    def make(*, blocked=False, internet=True, service_class=ui.LocalUIService):
        opener = ControlledOpener(blocked=blocked)
        backend = OllamaBackend("test-local", response_format=None, conversation=True, timeout=180)
        backend._opener = opener
        local = service_class(tmp_path / "profile", tmp_path / "ui", model="test-local",
            internet=internet, backend=backend, provider_probe=lambda: {
                "available": True, "model_available": True, "model": "test-local",
                "digest": "simulated-test-digest", "error": None})
        environment.openers.append(opener)
        environment.services.append(local)
        return local, opener

    environment.make = make
    try:
        yield environment
    finally:
        for opener in environment.openers:
            opener.release.set()
        for local in reversed(environment.services):
            local.close(timeout=15)


@pytest.mark.parametrize("authorized", [False, None, 1, "true"])
def test_start_requires_literal_explicit_authorization(harness, authorized):
    local, opener = harness.make()
    with pytest.raises(ui.UIError, match="explicitement"):
        submit(local, "mission_start", text="Mission test", queries=["a"], authorized=authorized)
    assert local.state()["supervisor"]["mission"] is None
    assert harness.searches == [] and opener.calls == []


def test_start_without_internet_cannot_create_or_execute_mission(harness):
    local, opener = harness.make(internet=False)
    result = perform(local, "mission_start", text="Mission test", queries=["a"], authorized=True)
    assert result["status"] == "failed"
    assert local.state()["supervisor"]["mission"] is None
    assert harness.searches == [] and opener.calls == []


def test_idle_ui_has_no_scientific_or_model_work(harness):
    local, opener = harness.make()
    # A state refresh does not schedule work; provider probes are controlled too.
    for _ in range(5):
        assert local.state()["supervisor"]["mission"] is None
    assert local._supervisor.next_delay() is None
    assert harness.searches == [] and opener.calls == []


def test_active_scope_rejects_stale_controls_and_ordinary_mutations(harness):
    local, opener = harness.make(blocked=True)
    start(local)
    assert opener.entered.wait(8)
    mission = local.state()["supervisor"]["mission"]
    for action in ("mission_pause", "mission_stop", "mission_resume"):
        with pytest.raises(ui.UIError) as error:
            submit(local, action, mission_id="f" * 32)
        assert error.value.status == 409
    for action, payload in (("message", {"text": "bonjour"}),
                            ("remember", {"text": "Fait fictif"}),
                            ("new_conversation", {}),
                            ("web", {"text": "autre recherche"}),
                            ("upload_document", {"name": "test.md", "content": "fictif"})):
        with pytest.raises(ui.UIError) as error:
            submit(local, action, **payload)
        assert error.value.status == 409
    assert local.state()["supervisor"]["mission"]["mission_id"] == mission["mission_id"]
    assert len(harness.searches) == len(opener.calls) == 1
    perform(local, "mission_stop", mission_id=mission["mission_id"])


@pytest.mark.parametrize("control,status", [("mission_pause", "paused"), ("mission_stop", "stopped")])
def test_inflight_control_is_durable_before_simulated_http_release(harness, control, status):
    local, opener = harness.make(blocked=True)
    start(local)
    assert opener.entered.wait(8)
    mission_id = local.state()["supervisor"]["mission"]["mission_id"]
    assert perform(local, control, mission_id=mission_id)["status"] == "succeeded"
    state = wait_for(local, lambda state: state["supervisor"]["mission"]["status"] == status)
    # The wire is still engaged, yet the owner has fsynced the control and budget.
    assert state["busy"] is True and not opener.release.is_set()
    durable = _read_atomic(local.root_dir / "supervisor" / mission_id / "state.json")
    assert durable["status"] == status and durable["next_wake"] is None
    assert durable["budget"]["searches_used"] == durable["budget"]["model_calls_used"] == 1
    assert opener.calls[0]["thread"] != local._worker.ident
    opener.release.set()
    state = wait_for(local, lambda state: not state["busy"])
    mission = state["supervisor"]["mission"]
    assert mission["status"] == status and mission["steps"][1]["status"] == "confirmed"
    assert len(harness.searches) == len(opener.calls) == 1
    # Recreating dialogue and restarting service retain independent mission caps.
    budget = deepcopy(mission["budget"])
    assert perform(local, "new_conversation")["status"] == "succeeded"
    assert local.state()["supervisor"]["mission"]["budget"] == budget
    local.close()
    restored, restored_opener = harness.make()
    restored_mission = restored.state()["supervisor"]["mission"]
    assert restored_mission["status"] == status and restored_mission["budget"] == budget
    assert restored_mission["mission_id"] == mission_id
    assert restored_opener.calls == [] and len(harness.searches) == 1


def test_swallowed_source_exception_blocks_unknown_outcome_without_retry(harness):
    harness.fail_source = True
    local, opener = harness.make()
    start(local)
    state = wait_for(local, lambda state: state["supervisor"]["mission"] is not None
        and state["supervisor"]["mission"]["status"] == "blocked" and not state["busy"])
    mission = state["supervisor"]["mission"]
    assert mission["budget"]["searches_used"] == 1
    assert mission["budget"]["model_calls_used"] == 0
    assert mission["uncertain_step_id"] == mission["steps"][0]["step_id"]
    with local._profile.ledger.transaction():
        receipts = [glyph for glyph in local._profile._state() if glyph.content["kind"] == "receipt"]
    assert len(receipts) == 1 and receipts[0].content["status"] == "failed"
    local.close()
    restored, restored_opener = harness.make()
    wait_for(restored, lambda state: not state["busy"]
             and state["supervisor"]["mission"]["status"] == "blocked")
    assert len(harness.searches) == 1 and restored_opener.calls == opener.calls == []
    assert restored.state()["supervisor"]["mission"]["budget"]["searches_used"] == 1


class InjectedProcessCrash(BaseException):
    pass


class CrashHarnessService(ui.LocalUIService):
    """Simulated process death at a chosen durable boundary, without a real kill."""
    def _run_mission_tick(self):
        try:
            super()._run_mission_tick()
        except InjectedProcessCrash:
            self._stop.set()


@pytest.mark.parametrize("crash_kind", ["search", "synthesis"])
def test_existing_engine_receipt_recovers_without_either_supervisor_proof(harness, monkeypatch, crash_kind):
    class CrashingSupervisor(Supervisor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            def checkpoint(boundary):
                step = next((step for step in self._mission["steps"] if step["status"] == "reserved"), None)
                if boundary == "effect_returned" and step and step["kind"] == crash_kind:
                    raise InjectedProcessCrash()
            self._checkpoint = checkpoint

    monkeypatch.setattr(ui, "Supervisor", CrashingSupervisor)
    local, opener = harness.make(service_class=CrashHarnessService)
    start(local, queries=["test-arxiv-a"])
    assert local._stopped.wait(8)
    # Get the durable reservation; the worker intentionally died before refresh.
    pointer = _read_atomic(local.root_dir / "supervisor" / "current.json")
    mission_id = pointer["mission_id"]
    durable = _read_atomic(local.root_dir / "supervisor" / mission_id / "state.json")
    target = next(step for step in durable["steps"] if step["status"] == "reserved")
    assert target["kind"] == crash_kind
    correlated = local.root_dir / "mission-effects" / (target["step_id"] + ".json")
    expected_result = _read_atomic(correlated)["result"]
    expected_receipt = expected_result["receipt_id"]
    if crash_kind == "synthesis":
        assert local._synthesis_receipt(Path(expected_result["audit_path"]), durable, target) == expected_result
    correlated.unlink()  # Isolated simulated crash: recover from engine ledger only.
    assert not (local.root_dir / "supervisor" / mission_id / (target["step_id"] + ".proof.json")).exists()
    local.close()
    monkeypatch.setattr(ui, "Supervisor", Supervisor)
    restored, restored_opener = harness.make(blocked=True)
    state = wait_for(restored, lambda state: state["supervisor"]["mission"]["steps"][target["index"]]["status"] == "confirmed")
    confirmed = state["supervisor"]["mission"]["steps"][target["index"]]
    assert confirmed["receipt_id"] == expected_receipt
    assert confirmed["result"] == expected_result
    assert len(harness.searches) == 1
    if crash_kind == "synthesis":
        assert len(opener.calls) == 1 and restored_opener.calls == []
    else:
        perform(restored, "mission_stop", mission_id=mission_id)
        assert restored_opener.calls == []


def test_raw_simulated_model_response_without_delivery_cycle_cannot_resume(harness, monkeypatch):
    original_reason = ConversationSession.reason

    def interrupted_reason(self, context):
        original_reason(self, context)  # The controlled HTTP reply actually arrives.
        raise InjectedProcessCrash()   # No emit_reply action or final delivery cycle.

    monkeypatch.setattr(ConversationSession, "reason", interrupted_reason)
    local, opener = harness.make(service_class=CrashHarnessService)
    start(local, queries=["test-arxiv-a"])
    assert local._stopped.wait(8)
    assert len(opener.calls) == len(harness.searches) == 1
    trace = [json.loads(line) for line in (local.root_dir / "transport.jsonl").read_text().splitlines()]
    assert len(trace) == 1 and trace[0]["response"]["done"] is True
    local.close()
    monkeypatch.setattr(ConversationSession, "reason", original_reason)
    restored, restored_opener = harness.make()
    state = wait_for(restored, lambda state: state["supervisor"]["mission"]["status"] == "blocked"
                     and not state["busy"])
    mission = state["supervisor"]["mission"]
    assert mission["budget"]["searches_used"] == mission["budget"]["model_calls_used"] == 1
    assert mission["steps"][0]["status"] == "confirmed"
    assert mission["steps"][1]["status"] == "reserved"
    assert mission["uncertain_step_id"] == mission["steps"][1]["step_id"]
    assert restored_opener.calls == [] and len(harness.searches) == 1
