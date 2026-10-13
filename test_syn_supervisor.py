"""SIMULATED deterministic callbacks only; no arXiv/Ollama network calls."""
from copy import deepcopy
import json
import threading

import pytest

from synergesis_supervisor import KnownEffectFailure, Supervisor, SupervisorError


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


class Effects:
    def __init__(self):
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(("search", deepcopy(kwargs)))
        return {"receipt_id": "g:source-" + kwargs["step_id"], "status": "found",
                "sources": [{"path": "https://arxiv.org/abs/" + kwargs["query"],
                             "text": "Abstract for " + kwargs["query"]}]}

    def synthesis(self, **kwargs):
        self.calls.append(("synthesis", deepcopy(kwargs)))
        return {"receipt_id": "g:delivery-" + kwargs["step_id"],
                "text": "Simulated cited summary " + kwargs["query"] + " [W1]"}


@pytest.fixture
def setup(tmp_path):
    clock, effects = Clock(), Effects()
    supervisor = Supervisor(tmp_path / "supervisor", model="installed-test-model",
                            clock=clock, interval=0)
    return supervisor, clock, effects


def tick(supervisor, effects, **kwargs):
    return supervisor.tick(effects.search, effects.synthesis, **kwargs)


def restart(supervisor, clock, **kwargs):
    return Supervisor(supervisor.root, model=supervisor.model, clock=clock, interval=0, **kwargs)


def test_idle_has_no_callbacks_or_planning(setup):
    supervisor, _, effects = setup
    assert supervisor.snapshot() is supervisor.next_delay() is tick(supervisor, effects) is None
    assert effects.calls == []


@pytest.mark.parametrize("queries", [[], [""], ["x", " X "], ["a", "b", "c", "d"],
    ["a\nb"], ["a\rb"], ["a\tb"], ["a\x00b"], ["a\x1fb"], ["a\x7fb"], ["x" * 301], [42]])
def test_invalid_scope_cannot_create_mission(setup, queries):
    supervisor, _, effects = setup
    with pytest.raises(SupervisorError):
        supervisor.create(queries)
    assert effects.calls == [] and supervisor.snapshot() is None


@pytest.mark.parametrize("authorized", [False, None, 1, "true"])
def test_literal_explicit_authorization_required(setup, authorized):
    supervisor, _, effects = setup
    with pytest.raises(SupervisorError):
        supervisor.create(["a"], authorized=authorized)
    assert effects.calls == []


def test_one_effect_per_tick_fixed_scope_and_restart_budgets(setup):
    supervisor, clock, effects = setup
    initial = supervisor.create([" a ", "b", "c"], title="Explicit goal")
    assert initial["queries"] == ["a", "b", "c"] and initial["deadline"] == clock.now + 600
    assert initial["authorization"]["model"] == "installed-test-model" and initial["goal_id"]
    assert effects.calls == []
    for count in range(6):
        state = tick(supervisor, effects)
        assert len(effects.calls) == count + 1
        assert effects.calls[-1][1]["step_id"] == state["last_step"]
        assert effects.calls[-1][1]["timeout"] == 180
        supervisor = restart(supervisor, clock)
        assert supervisor.snapshot()["budget"] == state["budget"]
        assert supervisor.snapshot()["deadline"] == initial["deadline"]
    assert state["status"] == "completed"
    assert state["budget"]["searches_used"] == state["budget"]["model_calls_used"] == 3
    assert state["budget"]["searches_remaining"] == state["budget"]["model_calls_remaining"] == 0
    assert len({call[1]["step_id"] for call in effects.calls}) == 6
    tick(supervisor, effects)
    assert len(effects.calls) == 6


def test_durable_pause_resume_and_stop_do_not_reset_budgets(setup):
    supervisor, clock, effects = setup
    initial = supervisor.create(["a", "b"])
    tick(supervisor, effects)
    assert supervisor.pause()["next_wake"] is None
    supervisor = restart(supervisor, clock)
    assert supervisor.next_delay() is None
    tick(supervisor, effects)
    assert len(effects.calls) == 1
    clock.now += 10
    assert supervisor.resume()["deadline"] == initial["deadline"]
    tick(supervisor, effects)
    assert len(effects.calls) == 2
    supervisor.stop()
    supervisor = restart(supervisor, clock)
    tick(supervisor, effects)
    with pytest.raises(SupervisorError):
        supervisor.resume()
    assert len(effects.calls) == 2


@pytest.mark.parametrize("control", ["pause", "stop"])
def test_control_before_reservation_does_not_charge_or_call(setup, control):
    supervisor, _, effects = setup
    supervisor.create(["a"])
    state = tick(supervisor, effects, control_check=lambda: control)
    assert state["status"] == ("paused" if control == "pause" else "stopped")
    assert state["budget"]["searches_used"] == 0 and effects.calls == []


@pytest.mark.parametrize("control", ["pause", "stop"])
@pytest.mark.parametrize("fails", [False, True])
def test_inflight_control_survives_last_confirmation_or_known_failure(setup, control, fails):
    supervisor, clock, effects = setup
    supervisor.create(["a"])
    tick(supervisor, effects)

    def finish(**kwargs):
        getattr(supervisor, control)()
        assert restart(supervisor, clock).snapshot()["status"] == ("paused" if control == "pause" else "stopped")
        if fails:
            raise KnownEffectFailure("Proven HTTP failure")
        return effects.synthesis(**kwargs)

    state = supervisor.tick(effects.search, finish)
    assert state["status"] == ("paused" if control == "pause" else "stopped")
    assert state["steps"][1]["status"] == ("failed" if fails else "confirmed")
    assert state["next_wake"] is None and supervisor.next_delay() is None
    assert restart(supervisor, clock).snapshot()["status"] == state["status"]
    assert supervisor.goals.snapshot(state["goal_id"]).status == ("suspended" if control == "pause" else "cancelled")


def test_persisted_next_wake_waits_without_external_calls(setup):
    original, clock, effects = setup
    supervisor = Supervisor(original.root, model=original.model, clock=clock, interval=17)
    supervisor.create(["a"])
    tick(supervisor, effects)
    supervisor = Supervisor(original.root, model=original.model, clock=clock, interval=17)
    assert supervisor.next_delay() == 17
    tick(supervisor, effects)
    assert len(effects.calls) == 1
    clock.now += 17
    tick(supervisor, effects)
    assert len(effects.calls) == 2


def test_resume_after_deadline_never_extends_it(setup):
    supervisor, clock, effects = setup
    supervisor.create(["a"])
    supervisor.pause()
    clock.now += 600
    assert supervisor.resume()["status"] == "blocked"
    tick(supervisor, effects)
    assert effects.calls == []


def test_inflight_effect_may_finish_after_deadline_without_new_effect(setup):
    supervisor, clock, effects = setup
    supervisor.create(["a", "b"])
    clock.now += 599

    def delayed(**kwargs):
        assert kwargs["timeout"] == 1
        clock.now += 3
        return effects.search(**kwargs)

    state = supervisor.tick(delayed, effects.synthesis)
    assert state["status"] == "blocked" and state["steps"][0]["status"] == "confirmed"
    tick(supervisor, effects)
    assert len(effects.calls) == 1


@pytest.mark.parametrize("reject_at", [1, 2])
def test_authorization_revalidated_before_reservation_and_call(setup, reject_at):
    supervisor, _, effects = setup
    supervisor.create(["a"])
    checks = []

    def authorization(state):
        checks.append(state["authorization"])
        return len(checks) != reject_at

    state = tick(supervisor, effects, authorization_check=authorization)
    assert state["status"] == "blocked" and len(checks) == reject_at
    assert state["budget"]["searches_used"] == reject_at - 1 and effects.calls == []


@pytest.mark.parametrize("advance_at", [1, 2])
def test_deadline_rechecked_after_authorization_adapter(setup, advance_at):
    supervisor, clock, effects = setup
    supervisor.create(["a"])
    checks = []

    def authorization(_):
        checks.append(True)
        if len(checks) == advance_at:
            clock.now += 600
        return True

    assert tick(supervisor, effects, authorization_check=authorization)["status"] == "blocked"
    assert effects.calls == []


def test_known_failed_attempts_charged_after_restart_suspend_without_retry(setup):
    supervisor, clock, effects = setup
    supervisor.create(["a", "b", "c"])
    calls = []

    def fail(**kwargs):
        calls.append(kwargs["query"])
        raise KnownEffectFailure("Known HTTP 503")

    assert supervisor.tick(fail, effects.synthesis)["budget"]["searches_used"] == 1
    supervisor = restart(supervisor, clock)
    state = supervisor.tick(fail, effects.synthesis)
    assert state["status"] == "suspended" and state["budget"]["searches_used"] == 2
    supervisor.tick(fail, effects.synthesis)
    assert calls == ["a", "b"] and effects.calls == []


def test_empty_searches_suspend_without_model_call(setup):
    supervisor, _, effects = setup
    supervisor.create(["a", "b", "c"])

    def empty(**kwargs):
        return {"receipt_id": "g:empty-" + kwargs["step_id"], "sources": [], "status": "no_evidence"}

    assert supervisor.tick(empty, effects.synthesis)["steps"][1]["status"] == "skipped"
    state = supervisor.tick(empty, effects.synthesis)
    assert state["status"] == "suspended" and state["budget"]["model_calls_used"] == 0
    assert effects.calls == []


def test_source_subset_new_receipt_ids_and_timestamps_are_not_progress(setup):
    supervisor, _, effects = setup
    supervisor.create(["a", "b", "c"])
    a = {"path": "https://arxiv.org/abs/A", "text": "stable abstract A"}
    b = {"path": "https://arxiv.org/abs/B", "text": "stable abstract B"}

    def source(**kwargs):
        entries = [a, b] if kwargs["query"] == "a" else [{**a, "created_at": kwargs["step_id"],
                                                            "receipt_id": kwargs["step_id"]}]
        return {"receipt_id": "g:" + kwargs["step_id"], "sources": entries}

    supervisor.tick(source, effects.synthesis)
    tick(supervisor, effects)
    supervisor.tick(source, effects.synthesis)
    assert supervisor.snapshot()["no_progress_count"] == 1
    tick(supervisor, effects)
    state = supervisor.tick(source, effects.synthesis)
    assert state["status"] == "suspended" and state["no_progress_count"] == 2
    assert state["budget"]["model_calls_used"] == 2


class Crash(BaseException):
    pass


@pytest.mark.parametrize("boundary,confirmed,calls", [
    ("reserved", False, 0), ("effect_returned", False, 1),
    ("proof_persisted", True, 1), ("confirmed", True, 1)])
def test_crash_frontiers_reconcile_proof_or_block_never_repeat_search(setup, boundary, confirmed, calls):
    original, clock, effects = setup

    def crash(actual):
        if actual == boundary:
            raise Crash(actual)

    supervisor = Supervisor(original.root, model=original.model, clock=clock, interval=0, checkpoint=crash)
    supervisor.create(["a", "b"])
    with pytest.raises(Crash):
        tick(supervisor, effects)
    assert len(effects.calls) == calls
    restored = restart(supervisor, clock)
    assert restored.snapshot()["budget"]["searches_used"] == 1
    state = tick(restored, effects)
    if confirmed:
        assert state["steps"][0]["status"] == "confirmed"
        assert not any(kind == "search" and args["query"] == "a" for kind, args in effects.calls[calls:])
    else:
        assert state["status"] == "blocked"
        assert state["uncertain_step_id"] == state["steps"][0]["step_id"]
        tick(restored, effects)
        assert len(effects.calls) == calls


def test_callback_existing_receipt_reconciles_without_effect_replay(setup):
    original, clock, effects = setup
    durable = {}

    def crash(boundary):
        if boundary == "effect_returned":
            raise Crash()

    supervisor = Supervisor(original.root, model=original.model, clock=clock, interval=0, checkpoint=crash)
    supervisor.create(["a"])

    def effect(**kwargs):
        result = effects.search(**kwargs)
        durable[(kwargs["step_id"], "search")] = deepcopy(result)
        return result

    with pytest.raises(Crash):
        supervisor.tick(effect, effects.synthesis)
    supervisor = restart(supervisor, clock)
    state = tick(supervisor, effects, reconcile=lambda step_id, kind: durable.get((step_id, kind)))
    assert state["steps"][0]["status"] == "confirmed" and len(effects.calls) == 1
    tick(supervisor, effects)
    assert len(effects.calls) == 2 and effects.calls[1][0] == "synthesis"


def test_unknown_socket_outcome_blocks_charged_step_without_retry(setup):
    supervisor, clock, effects = setup
    supervisor.create(["a", "b"])
    calls = []

    def unknown(**kwargs):
        calls.append(kwargs)
        raise TimeoutError("Bytes may already have been sent")

    state = supervisor.tick(unknown, effects.synthesis)
    assert state["status"] == "blocked" and state["budget"]["searches_used"] == 1
    supervisor = restart(supervisor, clock)
    supervisor.tick(unknown, effects.synthesis)
    assert len(calls) == 1
    with pytest.raises(SupervisorError):
        supervisor.resume()


def test_raw_model_response_without_delivery_receipt_is_not_proof(setup):
    supervisor, clock, effects = setup
    supervisor.create(["a", "b"])
    tick(supervisor, effects)
    state = supervisor.tick(effects.search, lambda **kwargs: {"text": "Unproven raw response"})
    assert state["status"] == "blocked" and state["budget"]["model_calls_used"] == 1
    assert restart(supervisor, clock).snapshot()["steps"][0]["status"] == "confirmed"


def test_corrupt_proof_blocks_without_network(setup):
    original, clock, effects = setup

    def crash(boundary):
        if boundary == "proof_persisted":
            raise Crash()

    supervisor = Supervisor(original.root, model=original.model, clock=clock, interval=0, checkpoint=crash)
    supervisor.create(["a"])
    with pytest.raises(Crash):
        tick(supervisor, effects)
    next(supervisor.root.glob("*/*.proof.json")).write_text("broken", encoding="utf-8")
    assert tick(restart(supervisor, clock), effects)["status"] == "blocked"
    assert len(effects.calls) == 1


def test_other_threads_can_read_but_cannot_write_or_tick(setup):
    supervisor, _, effects = setup
    supervisor.create(["a"])
    errors, reads = [], []

    def reader():
        reads.append(supervisor.snapshot())
        for mutation in (supervisor.pause, lambda: tick(supervisor, effects), lambda: supervisor.create(["b"])):
            try:
                mutation()
            except RuntimeError as error:
                errors.append(str(error))

    thread = threading.Thread(target=reader)
    thread.start()
    thread.join()
    assert len(errors) == 3 and reads[0]["status"] == "active" and effects.calls == []


def test_reentrant_tick_is_rejected_inside_callback(setup):
    supervisor, _, effects = setup
    supervisor.create(["a"])

    def callback(**kwargs):
        with pytest.raises(SupervisorError):
            tick(supervisor, effects)
        return effects.search(**kwargs)

    assert supervisor.tick(callback, effects.synthesis)["steps"][0]["status"] == "confirmed"
    assert len(effects.calls) == 1


def test_durable_start_request_dedup_scope_conflict_and_archived_replay(setup):
    supervisor, clock, effects = setup
    first = supervisor.create(["a"], title="Goal", request_id="first-start")
    for _ in range(2):
        tick(supervisor, effects)
    supervisor = restart(supervisor, clock)
    duplicate = supervisor.create(["a"], title="Goal", request_id="first-start")
    assert duplicate["mission_id"] == first["mission_id"] and duplicate["status"] == "completed"
    with pytest.raises(SupervisorError):
        supervisor.create(["b"], title="Goal", request_id="first-start")
    second = supervisor.create(["b"], request_id="second-start")
    archived = supervisor.create(["a"], title="Goal", request_id="first-start")
    assert archived["mission_id"] == first["mission_id"]
    assert supervisor.snapshot()["mission_id"] == second["mission_id"] and len(effects.calls) == 2


def test_tampered_saved_budget_fails_closed(setup):
    supervisor, clock, effects = setup
    supervisor.create(["a"])
    path = supervisor._state_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["data"]["budget"]["searches_used"] = 3
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SupervisorError):
        restart(supervisor, clock)
    assert effects.calls == []


def test_crash_after_start_registry_recovers_authorized_intent_on_same_request(setup):
    original, clock, effects = setup

    def crash(boundary):
        if boundary == "start_registered":
            raise Crash()

    supervisor = Supervisor(original.root, model=original.model, clock=clock, interval=0, checkpoint=crash)
    with pytest.raises(Crash):
        supervisor.create(["a"], request_id="durable-start-intent")
    initial = supervisor.snapshot()
    restored = restart(supervisor, clock)
    assert restored.snapshot() is None
    state = restored.create(["a"], request_id="durable-start-intent")
    assert state["mission_id"] == initial["mission_id"]
    assert restart(restored, clock).snapshot()["mission_id"] == initial["mission_id"]
    tick(restored, effects)
    assert len(effects.calls) == 1


@pytest.mark.parametrize("control", ["pause", "stop"])
def test_inflight_control_is_not_replaced_by_no_progress_suspension(setup, control):
    supervisor, _, effects = setup
    supervisor.create(["a", "b"])

    def empty(**kwargs):
        return {"receipt_id": "g:" + kwargs["step_id"], "sources": []}

    supervisor.tick(empty, effects.synthesis)

    def controlled_empty(**kwargs):
        getattr(supervisor, control)()
        return empty(**kwargs)

    state = supervisor.tick(controlled_empty, effects.synthesis)
    assert state["no_progress_count"] == 2
    assert state["status"] == ("paused" if control == "pause" else "stopped")
    assert state["next_wake"] is None and effects.calls == []
