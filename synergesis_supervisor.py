"""Passive, durable supervisor for an explicitly bounded local arXiv mission.

The UI's sole engine owner calls ``tick``. This class starts no thread, process,
model or network request of its own. One tick can invoke at most one supplied
effect callback. Callbacks must retain the supplied stable step ID in their
local receipts. Reservation is persisted before invocation and its proof before
confirmation, following SynRoamService's recovery pattern. An interrupted call
without a matching durable proof is blocked, never blindly replayed.

The ten-minute wall-clock deadline prevents new effects from starting. It cannot
kill an already engaged HTTP/socket call; callbacks receive a cooperative timeout
bounded by remaining time and 180 seconds. REALITY delivery is not truth.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Mapping
from uuid import uuid4

from synergesis_goal_manager import GoalLedger, SynGoalManager


class SupervisorError(ValueError):
    """A mission or control does not satisfy the fixed authorization contract."""


class KnownEffectFailure(RuntimeError):
    """The adapter proved failure (or no external invocation), not an unknown result.

    A socket timeout, malformed response after sending, or interrupted process
    must not be converted to this exception merely to obtain an automatic retry.
    Known failures consume the reservation and move to the next explicit query.
    """


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _write_atomic(path, data):
    """Persist a checksum-protected replacement, including its POSIX directory."""
    if path.is_symlink():
        raise SupervisorError("supervisor storage must not be a symlink")
    body = {"schema": "syn-supervisor-v0", "data": data, "sha256": _digest(data)}
    encoded = _canonical(body).encode("utf-8")
    if len(encoded) > 1_048_576:
        raise SupervisorError("supervisor state exceeds its bounded size")
    temporary = path.with_name(path.name + ".tmp")
    if temporary.is_symlink():
        raise SupervisorError("supervisor temporary storage must not be a symlink")
    with temporary.open("wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if hasattr(os, "O_DIRECTORY"):
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _read_atomic(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_048_576:
        raise SupervisorError("invalid supervisor storage")
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if (set(wrapper) != {"schema", "data", "sha256"}
                or wrapper["schema"] != "syn-supervisor-v0"
                or wrapper["sha256"] != _digest(wrapper["data"])):
            raise ValueError("integrity")
        return wrapper["data"]
    except (ValueError, TypeError, KeyError) as exc:
        raise SupervisorError("supervisor storage requires operator review") from exc


def _stable_sources(result):
    """Content progress excludes events, receipt IDs, timestamps and ordering."""
    sources = result.get("sources", result.get("evidence", []))
    if not isinstance(sources, list):
        raise SupervisorError("search sources must be a list")
    normalized = []
    for source in sources:
        if not isinstance(source, dict):
            raise SupervisorError("search source must be a mapping")
        text = source.get("text", source.get("excerpt", ""))
        location = source.get("url", source.get("path", ""))
        if not isinstance(text, str) or not isinstance(location, str):
            raise SupervisorError("invalid source content")
        if text.strip() or location.strip():
            normalized.append({"location": location.strip(),
                               "text": " ".join(text.split())})
    return tuple(sorted({_canonical(source) for source in normalized}))


class Supervisor:
    """Owned by one existing worker; snapshots are safe for HTTP readers.

    ``search_callback(**kwargs)`` returns existing ``receipt_id`` and a bounded
    JSON mapping including ``sources``/``evidence``. ``synthesis_callback`` also
    receives ``search_result`` and returns its real delivered ``text`` and
    ``receipt_id``. Optional ``reconcile(step_id, kind)`` reads local receipts
    only and returns an identical result mapping, or None. It performs no effect.
    """

    TERMINAL = frozenset({"completed", "stopped", "blocked"})

    def __init__(self, root, *, model, clock=time.time, interval=1.0,
                 goal_manager=None, checkpoint=None):
        if not isinstance(model, str) or not model.strip() or len(model) > 256:
            raise SupervisorError("a pinned installed local model is required")
        if isinstance(interval, bool) or not math.isfinite(interval) or not 0 <= interval <= 60:
            raise SupervisorError("wake interval must be in [0, 60]")
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.model, self.clock, self.interval = model, clock, float(interval)
        self._owner = threading.get_ident()
        self._guard = threading.RLock()
        self._in_tick = False
        self._checkpoint = checkpoint or (lambda boundary: None)
        # Registration and lifecycle use the existing identifiers and registry.
        # No planner/runtime is launched: the user supplied the complete v0 plan.
        self.goals = goal_manager or SynGoalManager(
            runtime=None, ledger=GoalLedger(self.root / "goals.jsonl"))
        self._mission = None
        self._published = None
        self._recovery_pending = False
        pointer = self.root / "current.json"
        if pointer.exists():
            mission_id = _read_atomic(pointer).get("mission_id")
            if not self._valid_id(mission_id):
                raise SupervisorError("invalid mission pointer")
            self._mission = _read_atomic(self._state_path(mission_id))
            self._validate_state()
            self._published = deepcopy(self._mission)
            self._recovery_pending = any(step["status"] == "reserved"
                                         for step in self._mission["steps"])

    @staticmethod
    def _valid_id(value):
        return (isinstance(value, str) and len(value) == 32
                and all(character in "0123456789abcdef" for character in value))

    def _owned(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("supervisor writes belong to the sole engine worker")

    def _state_path(self, mission_id=None):
        return self.root / (mission_id or self._mission["mission_id"]) / "state.json"

    def _proof_path(self, step):
        return self._state_path().parent / (step["step_id"] + ".proof.json")

    def _validate_state(self):
        mission = self._mission
        if (not isinstance(mission, dict) or not self._valid_id(mission.get("mission_id"))
                or mission.get("model") != self.model
                or mission.get("status") not in self.TERMINAL | {"active", "paused", "suspended"}
                or not isinstance(mission.get("steps"), list)):
            raise SupervisorError("mission state requires operator review")
        authorization = mission.get("authorization", {})
        expected = {"authorized": True, "provider": "ollama-local",
                    "model": self.model, "queries": mission.get("queries")}
        if authorization != {**expected, "scope_sha256": _digest(expected)}:
            raise SupervisorError("mission authorization requires operator review")
        queries = mission["queries"]
        self._validate_queries(queries)
        expected_plan = [(query, kind) for query in queries for kind in ("search", "synthesis")]
        if len(mission["steps"]) != len(expected_plan):
            raise SupervisorError("mission plan requires operator review")
        for index, (step, (query, kind)) in enumerate(zip(mission["steps"], expected_plan)):
            if (step.get("index") != index or step.get("query") != query or step.get("kind") != kind
                    or step.get("step_id") != _digest({"mission_id": mission["mission_id"], "index": index})[:32]
                    or step.get("status") not in {"pending", "reserved", "confirmed", "failed", "skipped"}):
                raise SupervisorError("invalid mission step")
        budget = mission.get("budget", {})
        if (budget.get("max_searches") != 3 or budget.get("max_model_calls") != 3
                or budget.get("max_effects_per_tick") != 1
                or any(type(budget.get(key)) is not int or not 0 <= budget[key] <= 3
                       for key in ("searches_used", "model_calls_used"))):
            raise SupervisorError("invalid mission budget")
        for kind, key in (("search", "searches_used"), ("synthesis", "model_calls_used")):
            if sum(step["kind"] == kind and step["status"] in {"reserved", "confirmed", "failed"}
                   for step in mission["steps"]) != budget[key]:
                raise SupervisorError("budget reservations disagree with mission steps")
        if (not isinstance(mission.get("created_at"), (int, float))
                or mission.get("deadline") != mission["created_at"] + 600
                or not math.isfinite(mission["deadline"])):
            raise SupervisorError("invalid fixed mission deadline")

    @staticmethod
    def _validate_queries(queries):
        if (not isinstance(queries, (list, tuple)) or not 1 <= len(queries) <= 3
                or any(not isinstance(query, str) or not query.strip() or len(query) > 300
                       or any(ord(character) < 32 or ord(character) == 127 for character in query)
                       for query in queries)
                or len({query.strip().casefold() for query in queries}) != len(queries)):
            raise SupervisorError("authorize 1..3 unique single-line arXiv queries")

    def _persist(self):
        self._validate_state()
        _write_atomic(self._state_path(), self._mission)
        with self._guard:
            self._published = deepcopy(self._mission)

    def _goal_event(self, kind, payload):
        self.goals.ledger.append(self._mission["goal_id"], kind,
                                 {"mission_id": self._mission["mission_id"], **payload})
        # GoalLedger is an ancillary registry, not the reservation authority.
        # Flush its existing append for durability without changing that class.
        with self.goals.ledger.path.open("rb") as stream:
            os.fsync(stream.fileno())

    def create(self, queries, *, authorized=True, title="Recherche scientifique", request_id=None):
        self._owned()
        if authorized is not True:
            raise SupervisorError("explicit mission authorization is required")
        self._validate_queries(queries)
        if not isinstance(title, str) or not title.strip() or len(title) > 2048:
            raise SupervisorError("mission title must contain 1..2048 characters")
        if request_id is not None and (not isinstance(request_id, str)
                                      or not 1 <= len(request_id) <= 128):
            raise SupervisorError("invalid mission start request ID")
        queries = [query.strip() for query in queries]
        request_digest = _digest({"queries": queries, "title": title.strip(), "model": self.model})
        with self._guard:
            requests_path = self.root / "start-requests.json"
            requests = _read_atomic(requests_path) if requests_path.exists() else {}
            if request_id is not None and request_id in requests:
                previous = requests[request_id]
                if previous["scope_sha256"] != request_digest:
                    raise SupervisorError("start request ID conflicts with its durable scope")
                archived = _read_atomic(self._state_path(previous["mission_id"]))
                if (archived.get("status") == "active"
                        and (not self._mission or self._mission["mission_id"] != archived["mission_id"])
                        and all(step["status"] == "pending" for step in archived["steps"])):
                    # Recover the authorized start intent if the process died
                    # after its dedup registry was durable but before pointer
                    # activation. No effect could have started in that gap.
                    if self._mission and self._mission["status"] not in self.TERMINAL:
                        raise SupervisorError("orphan start intent conflicts with an unfinished mission")
                    self._mission = archived
                    self._recovery_pending = False
                    self._persist()
                    _write_atomic(self.root / "current.json", {"mission_id": archived["mission_id"]})
                    self._goal_event("mission_linked", {"execution": "recovered-fixed-arxiv-start"})
                    return self.snapshot()
                return self._snapshot_data(archived)
            if request_id is not None and len(requests) >= 128:
                raise SupervisorError("durable mission request registry is full")
            if self._in_tick or (self._mission and self._mission["status"] not in self.TERMINAL):
                raise SupervisorError("a mission is already active or paused")
            now, mission_id = float(self.clock()), uuid4().hex
            if not math.isfinite(now):
                raise SupervisorError("invalid clock")
            directory = self.root / mission_id
            directory.mkdir()
            goal = self.goals.create(description=title.strip() + "\n" + "\n".join(queries),
                                     source="explicit-local-ui-user")
            authorization = {"authorized": True, "provider": "ollama-local",
                             "model": self.model, "queries": queries}
            steps = [{"step_id": _digest({"mission_id": mission_id, "index": index})[:32],
                      "index": index, "query": query, "kind": kind, "status": "pending"}
                     for index, (query, kind) in enumerate((query, kind) for query in queries
                                                           for kind in ("search", "synthesis"))]
            self._mission = {"mission_id": mission_id, "goal_id": goal.goal.goal_id,
                "title": title.strip(), "queries": queries, "model": self.model,
                "status": "active", "reason": None, "created_at": now,
                "deadline": now + 600, "next_wake": now,
                "authorization": {**authorization, "scope_sha256": _digest(authorization)},
                "budget": {"max_searches": 3, "max_model_calls": 3,
                           "searches_used": 0, "model_calls_used": 0, "max_effects_per_tick": 1},
                "steps": steps, "last_step": None, "no_progress_count": 0,
                "consecutive_failures": 0, "seen_evidence": [], "uncertain_step_id": None,
                "start_request_id": request_id}
            self._recovery_pending = False
            self._persist()
            if request_id is not None:
                requests[request_id] = {"mission_id": mission_id, "scope_sha256": request_digest}
                _write_atomic(requests_path, requests)
                self._checkpoint("start_registered")
            _write_atomic(self.root / "current.json", {"mission_id": mission_id})
            self._goal_event("mission_linked", {"execution": "fixed-arxiv-supervisor-v0"})
            return self.snapshot()

    start = create

    def snapshot(self):
        with self._guard:
            result = deepcopy(self._published)
            recovering = self._recovery_pending
        result = self._snapshot_data(result)
        if result:
            result["recovery_pending"] = recovering
        return result

    @staticmethod
    def _snapshot_data(data):
        result = deepcopy(data)
        if result:
            budget = result["budget"]
            budget["searches_remaining"] = 3 - budget["searches_used"]
            budget["model_calls_remaining"] = 3 - budget["model_calls_used"]
            result["recovery_pending"] = any(step["status"] == "reserved" for step in result["steps"])
        return result

    def next_delay(self):
        with self._guard:
            if self._recovery_pending:
                return 0.0
            if not self._mission or self._mission["status"] != "active":
                return None
            wake = min(self._mission["next_wake"], self._mission["deadline"])
            return max(0.0, wake - self.clock())

    def _transition(self, status, reason):
        self._mission.update(status=status, reason=reason, next_wake=None)
        self._persist()
        kind = {"paused": "goal_suspended", "suspended": "goal_suspended",
                "stopped": "goal_cancelled", "blocked": "goal_blocked",
                "completed": "goal_completed"}.get(status, "goal_resumed")
        self._goal_event(kind, {"reason": reason})

    def pause(self):
        self._owned()
        with self._guard:
            if not self._mission or self._mission["status"] != "active":
                raise SupervisorError("only an active mission can be paused")
            self._transition("paused", "Pause demandée par l’utilisateur.")
            return self.snapshot()

    def stop(self):
        self._owned()
        with self._guard:
            if not self._mission or self._mission["status"] in self.TERMINAL:
                raise SupervisorError("mission is already final or absent")
            self._transition("stopped", "Arrêt demandé par l’utilisateur.")
            return self.snapshot()

    def resume(self):
        self._owned()
        with self._guard:
            if not self._mission or self._mission["status"] not in {"paused", "suspended"}:
                raise SupervisorError("only a known paused or suspended mission can resume")
            if self._recovery_pending:
                raise SupervisorError("reconcile interrupted effects before resuming")
            if self.clock() >= self._mission["deadline"]:
                self._transition("blocked", "Échéance de dix minutes dépassée ; aucun nouvel appel.")
            else:
                self._mission.update(status="active", reason=None, next_wake=float(self.clock()))
                self._persist()
                self._goal_event("goal_resumed", {"reason": "explicit user resume"})
            return self.snapshot()

    def _control(self, control_check):
        control = control_check() if control_check else None
        if control == "stop":
            self.stop()
            return True
        if control == "pause":
            self.pause()
            return True
        return False

    def _eligible(self, authorization_check, control_check):
        if self._mission["status"] != "active":
            return False
        if self._control(control_check):
            return False
        if self.clock() >= self._mission["deadline"]:
            self._transition("blocked", "Échéance de dix minutes dépassée ; aucun nouvel appel.")
            return False
        if authorization_check is not None and authorization_check(self.snapshot()) is not True:
            self._transition("blocked", "Autorisation locale ou portée de mission indisponible.")
            return False
        # Authorization can take time or pump a queued control on the sole
        # worker. Revalidate immediately at the effect boundary as well.
        if self._mission["status"] != "active" or self._control(control_check):
            return False
        if self.clock() >= self._mission["deadline"]:
            self._transition("blocked", "Échéance de dix minutes dépassée ; aucun nouvel appel.")
            return False
        return True

    def _result(self, result, step):
        if not isinstance(result, Mapping):
            raise SupervisorError("effect result requires a mapping")
        result = json.loads(_canonical(dict(result)))
        if len(_canonical(result).encode("utf-8")) > 65_536:
            raise SupervisorError("effect proof exceeds its bounded size")
        if not isinstance(result.get("receipt_id"), str) or not result["receipt_id"]:
            raise SupervisorError("confirmed effects require an existing receipt ID")
        if step["kind"] == "search":
            _stable_sources(result)
        elif not isinstance(result.get("text"), str) or not result["text"].strip():
            raise SupervisorError("confirmed synthesis requires delivered text")
        return result

    def _write_proof(self, step, result):
        proof = {"mission_id": self._mission["mission_id"], "step_id": step["step_id"],
                 "kind": step["kind"], "query": step["query"], "result": result}
        _write_atomic(self._proof_path(step), proof)

    def _confirm(self, step, result):
        prior_status = self._mission["status"]
        step.update(status="confirmed", confirmed_at=float(self.clock()),
                    receipt_id=result["receipt_id"], result=result)
        self._mission["last_step"] = step["step_id"]
        self._mission["consecutive_failures"] = 0
        self._mission["uncertain_step_id"] = None
        if step["kind"] == "search":
            fingerprints = {_digest(source) for source in _stable_sources(result)}
            seen = self._mission["seen_evidence"]
            if not fingerprints - set(seen):
                self._mission["no_progress_count"] += 1
            else:
                self._mission["no_progress_count"] = 0
                seen.extend(sorted(fingerprints - set(seen)))
            if not _stable_sources(result):
                self._mission["steps"][step["index"] + 1].update(
                    status="skipped", error="Aucun extrait disponible à synthétiser.")
        self._mission["next_wake"] = float(self.clock()) + self.interval if prior_status == "active" else None
        self._persist()
        if prior_status != "active":
            return
        if self._mission["no_progress_count"] >= 2:
            self._transition("suspended", "Deux recherches consécutives sans nouvelle preuve stable.")
        elif all(item["status"] in {"confirmed", "failed", "skipped"}
                 for item in self._mission["steps"]):
            self._transition("completed", "Plan explicitement autorisé terminé ; sources et limites conservées.")

    def _reconcile(self, reconcile):
        for step in self._mission["steps"]:
            if step["status"] != "reserved":
                continue
            path = self._proof_path(step)
            result = None
            if path.exists():
                proof = _read_atomic(path)
                expected = {"mission_id": self._mission["mission_id"], "step_id": step["step_id"],
                            "kind": step["kind"], "query": step["query"]}
                if {key: proof.get(key) for key in expected} != expected:
                    raise SupervisorError("interrupted proof does not match its reserved step")
                result = self._result(proof.get("result"), step)
            elif reconcile is not None:
                result = reconcile(step["step_id"], step["kind"])
                if result is not None:
                    result = self._result(result, step)
                    self._write_proof(step, result)
            if result is None:
                self._mission["uncertain_step_id"] = step["step_id"]
                if self._mission["status"] == "stopped":
                    self._mission["reason"] += " Résultat de l’appel interrompu inconnu ; aucun rejeu."
                    self._persist()
                else:
                    self._transition("blocked", "Résultat de l’appel interrompu inconnu ; examen requis, aucun rejeu.")
                self._recovery_pending = False
                return
            prior_status = self._mission["status"]
            self._confirm(step, result)
            if prior_status in {"paused", "stopped"}:
                self._mission.update(status=prior_status, next_wake=None)
                self._persist()
        self._recovery_pending = False

    def tick(self, search_callback, synthesis_callback, *, authorization_check=None,
             control_check=None, reconcile=None):
        """Advance at most one external effect; return the latest snapshot.

        Failed reservations remain charged. No available work invokes neither
        callback. Unknown outcomes are final blocked states requiring review.
        Checkpoint injection is solely for deterministic simulated crash tests.
        """
        self._owned()
        with self._guard:
            if self._in_tick:
                raise SupervisorError("a supervisor tick is already executing")
            if not self._mission:
                return None
            self._in_tick = True
        try:
            if self._recovery_pending:
                try:
                    self._reconcile(reconcile)
                except Exception as exc:
                    reserved = next((step for step in self._mission["steps"] if step["status"] == "reserved"), None)
                    self._mission["uncertain_step_id"] = reserved["step_id"] if reserved else None
                    self._transition("blocked", "Preuve interrompue invalide ; examen requis : " + type(exc).__name__)
                    self._recovery_pending = False
                return self.snapshot()
            if not self._eligible(authorization_check, control_check):
                return self.snapshot()
            if self.clock() < self._mission["next_wake"]:
                return self.snapshot()
            step = next((item for item in self._mission["steps"] if item["status"] == "pending"), None)
            if step is None:
                self._transition("completed", "Plan explicitement autorisé terminé.")
                return self.snapshot()
            key = "searches_used" if step["kind"] == "search" else "model_calls_used"
            if self._mission["budget"][key] >= 3:
                self._transition("blocked", "Budget de mission épuisé ; aucun nouvel appel.")
                return self.snapshot()
            self._mission["budget"][key] += 1
            step.update(status="reserved", reserved_at=float(self.clock()))
            self._mission["last_step"] = step["step_id"]
            self._persist()
            self._checkpoint("reserved")
            # Recheck signals and scope at the actual effect boundary. A reserved
            # but never invoked step stays charged and safely blocked on restart.
            if not self._eligible(authorization_check, control_check):
                step.update(status="failed", error="Invocation annulée avant tout effet externe.")
                if step["kind"] == "search":
                    self._mission["steps"][step["index"] + 1]["status"] = "skipped"
                self._persist()
                return self.snapshot()
            arguments = {"mission_id": self._mission["mission_id"], "step_id": step["step_id"],
                         "query": step["query"], "deadline": self._mission["deadline"],
                         "timeout": min(180.0, max(0.001, self._mission["deadline"] - self.clock()))}
            callback = search_callback
            if step["kind"] == "synthesis":
                callback = synthesis_callback
                arguments["search_result"] = deepcopy(self._mission["steps"][step["index"] - 1]["result"])
            try:
                result = callback(**arguments)
                self._checkpoint("effect_returned")
                result = self._result(result, step)
                self._write_proof(step, result)
                self._checkpoint("proof_persisted")
            except KnownEffectFailure as exc:
                step.update(status="failed", error=str(exc)[:2048])
                if step["kind"] == "search":
                    self._mission["steps"][step["index"] + 1].update(status="skipped", error="Recherche échouée.")
                self._mission["consecutive_failures"] += 1
                self._mission["next_wake"] = (float(self.clock()) + self.interval
                                                if self._mission["status"] == "active" else None)
                self._persist()
                if self._mission["status"] != "active":
                    return self.snapshot()
                if self._control(control_check):
                    return self.snapshot()
                if self._mission["consecutive_failures"] >= 2:
                    self._transition("suspended", "Deux tentatives consécutives échouées ; reprise explicite requise.")
                elif all(item["status"] in {"confirmed", "failed", "skipped"} for item in self._mission["steps"]):
                    self._transition("completed", "Plan terminé avec échec consigné ; aucun résultat inventé.")
                return self.snapshot()
            except Exception as exc:
                step["error"] = type(exc).__name__ + ": " + str(exc)[:2048]
                self._mission["uncertain_step_id"] = step["step_id"]
                if self._mission["status"] == "stopped":
                    self._mission["reason"] += " Résultat de l’appel engagé inconnu ; examen requis."
                    self._persist()
                else:
                    self._transition("blocked", "Résultat externe inconnu ; examen requis, aucun rejeu automatique.")
                return self.snapshot()
            self._confirm(step, result)
            self._checkpoint("confirmed")
            if self._mission["status"] == "active":
                if self._control(control_check):
                    return self.snapshot()
                if self.clock() >= self._mission["deadline"]:
                    self._transition("blocked", "Échéance atteinte pendant l’appel ; preuve conservée, aucun nouvel appel.")
            return self.snapshot()
        finally:
            with self._guard:
                self._in_tick = False
