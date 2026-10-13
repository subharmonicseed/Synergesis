"""Local, single-worker web interface to the existing Synergesis engine.

Run on POSIX (WSL on Windows). HTTP threads read immutable snapshots and submit
jobs; only the worker enters, uses and leaves a conversation context. Persistent
profile data remain in the engine's ledger. No model is downloaded.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import re
import secrets
import threading
import time
import urllib.request
from uuid import UUID, uuid4

from synergesis_conversation import MAX_INPUT_CHARS, MAX_TURNS, open_conversation
from synergesis_initiative import InitiativeError, InitiativeProfile
from synergesis_ollama_backend import OllamaBackend, _NoRedirect
from synergesis_supervisor import (
    Supervisor, SupervisorError, KnownEffectFailure, _write_atomic, _read_atomic,
)

APP_NAME = "synergesis-local-ui"
MAX_DOCUMENT_BYTES = 256 * 1024
MAX_DOCUMENTS = 16
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_PROFILE_COMMANDS = 32
ASSET_ROOT = Path(__file__).with_name("synergesis_ui_assets")


def _now():
    return datetime.now(timezone.utc).isoformat()


class UIError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class ServiceLock:
    """Lifetime flock; the sidecar is never removed or forcefully replaced."""
    def __init__(self, path):
        try:
            import fcntl
        except ImportError:
            raise RuntimeError("Le moteur nécessite Linux ou WSL sous Windows.") from None
        self._fcntl = fcntl
        self.path = Path(path)
        if self.path.is_symlink():
            raise RuntimeError("Le verrou du service ne doit pas être un lien symbolique.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self._file = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._file.close()
            raise RuntimeError("Une interface Syn utilise déjà ce profil ou ce dossier.") from None

    def close(self):
        if not self._file.closed:
            self._fcntl.flock(self._file.fileno(), self._fcntl.LOCK_UN)
            self._file.close()


class _TraceResponse:
    def __init__(self, response, finish):
        self.response, self.finish = response, finish

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def read(self, size):
        data = self.response.read(size)
        self.finish(data, getattr(self.response, "status", None))
        return data


class _TraceOpener:
    """Capture the actual bounded HTTP request and response inside service logs."""
    def __init__(self, opener, trace_path):
        self.opener, self.path = opener, Path(trace_path)

    def _write(self, record):
        with self.path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    def open(self, request, *, timeout):
        record = {"event": "ollama_transport", "created_at": _now(),
                  "url": request.full_url, "request": json.loads(request.data)}
        try:
            response = self.opener.open(request, timeout=timeout)
        except Exception as error:
            self._write({**record, "error_type": type(error).__name__})
            raise

        def finish(data, status):
            try:
                body = json.loads(data)
            except (ValueError, UnicodeError):
                body = {"invalid_json": True, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()}
            self._write({**record, "status": status, "response": body})
            message = body.get("message", {}) if isinstance(body, dict) else {}
            if (isinstance(body, dict) and body.get("done") is True
                    and isinstance(message, dict) and not message.get("tool_calls")
                    and isinstance(message.get("content"), str)
                    and bool(message["content"].strip()) and len(message["content"]) <= 16000
                    and isinstance(body.get("model"), str) and 0 < len(body["model"]) <= 128):
                self.last_model = body["model"]
        return _TraceResponse(response, finish)


class _BufferedHTTPResponse:
    """Actual bounded HTTP bytes, marshalled back to the engine owner."""
    def __init__(self, data, status):
        self.data, self.status = data, status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.data[:size]


class _MissionOpener:
    def __init__(self, owner, delegate):
        self.owner, self.delegate = owner, delegate

    def open(self, request, *, timeout):
        if self.owner._mission_effect is None:
            return self.delegate.open(request, timeout=timeout)
        self.owner._mission_boundary()
        remaining = self.owner._mission_effect["deadline"] - time.time()
        timeout = min(timeout, max(0.001, remaining))
        def retrieve():
            with self.delegate.open(request, timeout=timeout) as response:
                return response.read(262145), getattr(response, "status", None)
        data, status = self.owner._wait_external(retrieve)
        return _BufferedHTTPResponse(data, status)


class _MissionResearch:
    """Pure arXiv retrieval offloaded; profile receipts stay on the owner."""
    def __init__(self, owner):
        from synergesis_web_research import ArxivWebResearch
        self.owner = owner
        remaining = max(0.001, owner._mission_effect["deadline"] - time.time())
        self.delegate = ArxivWebResearch(timeout_seconds=min(15, remaining),
                                       max_total_seconds=min(20, remaining))
        self.error = None

    def search(self, query):
        self.owner._mission_boundary()
        try:
            return self.owner._wait_external(lambda: self.delegate.search(query))
        except Exception as exc:
            self.error = type(exc).__name__
            raise


def probe_provider(model, port):
    """Read installed models only; never call pull or send the profile to tags."""
    result = {"available": False, "model_available": False, "model": model,
              "digest": None, "error": None}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/tags", timeout=2) as response:
            data = response.read(1_048_577)
        if len(data) > 1_048_576:
            raise ValueError("tags too large")
        obj = json.loads(data)
        if not isinstance(obj, dict) or not isinstance(obj.get("models"), list):
            raise ValueError("invalid tags")
        result["available"] = True
        expected = model if ":" in model else model + ":latest"
        for item in obj["models"]:
            if not isinstance(item, dict):
                continue
            names = {item.get("name"), item.get("model")}
            if model in names or expected in names:
                result["model_available"] = True
                result["digest"] = item.get("digest") if isinstance(item.get("digest"), str) else None
                break
        if not result["model_available"]:
            result["error"] = "Ollama répond, mais le modèle choisi n’est pas installé."
    except Exception:
        result["error"] = "Ollama est indisponible sur son port local."
    return result


class LocalUIService:
    def __init__(self, profile_dir, root_dir, *, model="mistral", ollama_port=11434,
                 internet=False, backend=None, provider_probe=None):
        # Validate before creating files, using the same adapter as production.
        self.backend = backend or OllamaBackend(model, port=ollama_port,
            response_format=None, conversation=True, timeout=180)
        if type(internet) is not bool:
            raise ValueError("internet must be boolean")
        self.model, self.ollama_port, self.internet = model, ollama_port, internet
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.instance_id, self.csrf_token = uuid4().hex, secrets.token_urlsafe(32)
        self._guard = threading.RLock()
        self._jobs = queue.Queue()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._stopped = threading.Event()
        self._startup_error = None
        self._requests = {}
        self._locks = []
        self._context = self._session = self._profile = None
        self._documents = []
        self._sources = []
        self._profile_commands = 0
        self._supervisor = None
        self._controls = queue.Queue(maxsize=8)
        self._mission_effect = None
        self._cancelled_before_effect = False
        self._performing_request_id = None
        self._supervisor_failure = None
        self._shutdown_callback = None
        self._provider_probe = provider_probe or (lambda: probe_provider(model, ollama_port))
        self._state = {"app": APP_NAME, "instance_id": self.instance_id,
            "csrf_token": self.csrf_token, "busy": False,
            "profile_dir": str(self.profile_dir), "root_dir": str(self.root_dir),
            "model": model, "internet": internet,
            "source_manifest_sha256": hashlib.sha256(Path(__file__).with_name("MANIFEST_SHA256.json").read_bytes()).hexdigest()
                if Path(__file__).with_name("MANIFEST_SHA256.json").is_file() else None,
            "transport_trace_path": str(self.root_dir / "transport.jsonl"),
            "operation": {"id": None, "action": None, "status": "idle",
                          "message": "Prêt.", "error": None},
            "conversation": {"id": None, "attempts": 0, "max_turns": MAX_TURNS,
                "remaining_turns": MAX_TURNS, "messages": [], "output": None},
            "memories": [], "documents": [], "sources": [],
            "provider": {"available": False, "model_available": False,
                         "model": model, "digest": None, "error": None},
            "limits": {"max_document_bytes": MAX_DOCUMENT_BYTES,
                "max_documents": MAX_DOCUMENTS, "search_remaining": 3,
                "profile_commands_remaining": MAX_PROFILE_COMMANDS},
            "last_error": None, "supervisor": {"mission": None}, "mission_control": None}
        try:
            self._locks.append(ServiceLock(self.profile_dir / ".local-ui-service.lock"))
            if self.root_dir != self.profile_dir:
                self._locks.append(ServiceLock(self.root_dir / ".local-ui-service.lock"))
            uploads = self.root_dir / "uploads"
            if uploads.is_symlink():
                raise RuntimeError("Le dossier d’import ne doit pas être un lien symbolique.")
            uploads.mkdir(exist_ok=True)
            trace = self.root_dir / "transport.jsonl"
            if trace.is_symlink():
                raise RuntimeError("Le journal de transport ne doit pas être un lien symbolique.")
            if isinstance(self.backend, OllamaBackend):
                self.backend._opener = _TraceOpener(_MissionOpener(self, self.backend._opener), trace)
            self._worker = threading.Thread(target=self._run, name="syn-ui-worker", daemon=True)
            self._worker.start()
            if not self._ready.wait(30):
                self._stop.set()
                raise RuntimeError("Le moteur local ne démarre pas dans le délai prévu.")
            if self._startup_error:
                raise RuntimeError(self._startup_error)
        except BaseException:
            for lock in reversed(self._locks):
                lock.close()
            raise

    def set_shutdown_callback(self, callback):
        self._shutdown_callback = callback

    def state(self):
        with self._guard:
            return deepcopy(self._state)

    def _new_conversation(self):
        if self._context is not None:
            self._context.__exit__(None, None, None)
            self._context = self._session = None
        self._profile = InitiativeProfile(self.profile_dir)
        conversation_id = uuid4().hex
        output = self.root_dir / "conversations" / conversation_id
        output.parent.mkdir(exist_ok=True)
        context = open_conversation(output, self.backend, profile=self._profile)
        session = context.__enter__()
        self._context, self._session = context, session
        self._profile_commands = 0
        self._sources = []
        with self._guard:
            self._state["conversation"] = {"id": conversation_id, "attempts": 0,
                "max_turns": MAX_TURNS, "remaining_turns": MAX_TURNS,
                "messages": [], "output": str(output)}

    def _load_documents(self):
        manifest = self.root_dir / "documents.json"
        if not manifest.exists():
            return
        if manifest.is_symlink() or manifest.stat().st_size > 16_384:
            raise RuntimeError("Le registre des documents est invalide.")
        documents = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(documents, list) or len(documents) > MAX_DOCUMENTS:
            raise RuntimeError("Le registre des documents est invalide.")
        for document in documents:
            if not isinstance(document, dict) or set(document) != {"id", "name", "bytes", "suffix"}:
                raise RuntimeError("Le registre des documents est invalide.")
            self._validate_name(document["name"])
            if not re.fullmatch(r"[0-9a-f]{32}", str(document["id"])) or document["suffix"] not in {".txt", ".md"}:
                raise RuntimeError("Le registre des documents est invalide.")
            path = self._document_path(document)
            if (path.is_symlink() or not path.is_file() or type(document["bytes"]) is not int
                    or not 0 <= document["bytes"] <= MAX_DOCUMENT_BYTES
                    or path.stat().st_size != document["bytes"]):
                raise RuntimeError("Un document importé ne correspond plus à son registre.")
        self._documents = documents

    def _document_path(self, document):
        return self.root_dir / "uploads" / (document["id"] + document["suffix"])

    @staticmethod
    def _validate_name(name):
        if (not isinstance(name, str) or not name or len(name) > 100
                or name != name.strip() or any(c in name for c in "/\\:")
                or any(ord(c) < 32 for c in name)
                or name in {".", ".."} or name.endswith((".", " "))
                or Path(name).suffix.casefold() not in {".txt", ".md"}
                or re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", name, re.I)):
            raise UIError("Choisissez un nom simple de document .txt ou .md, sans chemin.")
        try:
            name.encode("utf-8")
        except UnicodeError:
            raise UIError("Le nom du document doit être un texte UTF-8 valide.") from None

    def _snapshot_engine(self):
        # Called only by the context-owning worker. GET never acquires ledger locks.
        with self._profile.ledger.transaction():
            glyphs = self._profile._state()
        memories, sources = [], []
        previous = {(s["receipt_id"], s["path"], s["sha256"], s["line"]): s for s in self._sources}
        for glyph in glyphs:
            content = glyph.content
            if content["kind"] == "user_claim":
                memories.append({"id": glyph.glyph_id, "text": content["text"],
                    "created_at": glyph.created_at, "claim_status": content["claim_status"]})
            elif content["kind"] == "receipt":
                for evidence in content["evidence"]:
                    key = (glyph.glyph_id, evidence["path"], evidence["sha256"], evidence["line"])
                    document = next((d for d in self._documents
                        if str(self._document_path(d)) == evidence["path"]), None)
                    source = {**evidence, "title": evidence.get("title") or
                        (document["name"] if document else Path(evidence["path"]).name),
                        "receipt_id": glyph.glyph_id,
                        "retrieved_at": evidence.get("retrieved_at", glyph.created_at),
                        "supplied": False, "cited": False}
                    old = previous.get(key)
                    if old:
                        source.update({k: old[k] for k in ("supplied", "cited", "alias") if k in old})
                    sources.append(source)
        self._sources = sources
        if self._supervisor:
            mission = self._supervisor.snapshot()
            for step in mission["steps"] if mission else []:
                if step["kind"] == "synthesis" and step["status"] == "confirmed":
                    self._mark_sources(step.get("result", {}))
        with self._guard:
            self._state["memories"] = memories
            self._state["sources"] = deepcopy(sources)
            self._state["documents"] = [{k: d[k] for k in ("id", "name", "bytes")} for d in self._documents]
            self._state["conversation"]["attempts"] = self._session._attempts
            self._state["conversation"]["remaining_turns"] = MAX_TURNS - self._session._attempts
            self._state["limits"]["search_remaining"] = self._profile.max_steps - self._profile._attempts
            self._state["limits"]["profile_commands_remaining"] = MAX_PROFILE_COMMANDS - self._profile_commands

    def _provider_status(self):
        try:
            provider = self._provider_probe()
        except Exception:
            provider = {"available": False, "model_available": False, "model": self.model,
                        "digest": None, "error": "Ollama est indisponible sur son port local."}
        with self._guard:
            provider["last_model"] = getattr(getattr(self.backend, "_opener", None), "last_model", None)
            self._state["provider"] = provider

    def _snapshot_supervisor(self):
        mission = self._supervisor.snapshot() if self._supervisor else None
        with self._guard:
            self._state["supervisor"] = {"mission": mission, "service_error": self._supervisor_failure}

    def _mission_authorized(self, mission):
        return (self.internet is True and mission["model"] == self.model
                and (not isinstance(self.backend, OllamaBackend)
                     or self.backend.model == self.model)
                and not self._stop.is_set())

    def _drain_controls(self):
        """Only the owner persists controls, also while awaiting raw network IO."""
        while True:
            try:
                request_id, payload = self._controls.get_nowait()
            except queue.Empty:
                break
            error = None
            try:
                self._perform_mission_control(payload)
            except (UIError, SupervisorError) as exc:
                error = str(exc)
            except Exception:
                error = "La commande de mission nécessite l’examen de ses traces."
            self._snapshot_supervisor()
            with self._guard:
                self._requests[request_id]["operation"] = {
                    "id": request_id, "action": payload["action"],
                    "status": "failed" if error else "succeeded",
                    "message": error or "Commande de mission enregistrée durablement.",
                    "error": error}
                self._state["mission_control"] = None
                self._state["operation"] = deepcopy(self._requests[request_id]["operation"])
                if error:
                    self._state["last_error"] = error
            self._controls.task_done()

    def _perform_mission_control(self, payload):
        mission = self._supervisor.snapshot()
        if not mission or payload["mission_id"] != mission["mission_id"]:
            raise UIError("Cette commande concerne une autre mission.", 409)
        action = payload["action"]
        {"mission_pause": self._supervisor.pause,
         "mission_resume": self._supervisor.resume,
         "mission_stop": self._supervisor.stop}[action]()

    def _mission_boundary(self):
        self._drain_controls()
        mission = self._supervisor.snapshot()
        current = self._mission_effect
        if (not current or not mission or current["mission_id"] != mission["mission_id"]
                or mission["status"] != "active" or not self._mission_authorized(mission)
                or time.time() >= mission["deadline"]):
            self._cancelled_before_effect = True
            raise KnownEffectFailure("Appel annulé avant son engagement ; pause, arrêt ou échéance.")
        reserved = next((s for s in mission["steps"] if s["step_id"] == current["step_id"]), None)
        if not reserved or reserved["status"] != "reserved":
            self._cancelled_before_effect = True
            raise KnownEffectFailure("Aucune réservation durable ne correspond à cet appel.")

    def _wait_external(self, retrieve):
        """One raw IO helper, always awaited; engine/file writes remain here.

        A control becomes durable within an owner checkpoint, but cannot undo an
        already engaged remote call. Socket timeouts are cooperative, not hard
        wall-clock deadlines. Idle work never enters this loop.
        """
        done, outcome = threading.Event(), {}
        def raw_io():
            try:
                outcome["value"] = retrieve()
            except BaseException as exc:
                outcome["error"] = exc
            finally:
                done.set()
        helper = threading.Thread(target=raw_io, name="syn-mission-raw-io", daemon=True)
        helper.start()
        while not done.wait(0.2):
            self._drain_controls()
            self._snapshot_supervisor()
        self._drain_controls()
        helper.join()
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def _effect_path(self, step_id):
        if not re.fullmatch(r"[0-9a-f]{32}", step_id):
            raise UIError("Identifiant d’étape invalide.")
        directory = self.root_dir / "mission-effects"
        if directory.is_symlink():
            raise UIError("Le dossier de preuves ne doit pas être un lien symbolique.")
        directory.mkdir(exist_ok=True)
        return directory / (step_id + ".json")

    def _save_effect(self, kind, result):
        current = self._mission_effect
        _write_atomic(self._effect_path(current["step_id"]), {
            "mission_id": current["mission_id"], "step_id": current["step_id"],
            "kind": kind, "query": current["query"], "result": result})

    @staticmethod
    def _fsync_file(path):
        with Path(path).open("rb") as stream:
            os.fsync(stream.fileno())

    def _mission_search(self, **effect):
        self._mission_effect, self._cancelled_before_effect = effect, False
        try:
            self._mission_boundary()
            # Same owner and persistent ledger, with mission counters separately
            # reserved durably by the supervisor rather than UI session resets.
            profile = InitiativeProfile(self.profile_dir)
            profile._web_research = _MissionResearch(self)
            result = profile.web_search(effect["query"], operation_id=effect["step_id"])
            self._fsync_file(profile.path)
            if self._cancelled_before_effect:
                raise KnownEffectFailure("Recherche annulée avant tout appel arXiv.")
            if profile._web_research.error is not None or result["status"] == "failed":
                raise RuntimeError("Recherche arXiv engagée sans résultat fiable ; examen requis.")
            result = {**result, "sources": result["evidence"]}
            self._save_effect("search", result)
            return result
        finally:
            self._mission_effect = None

    def _mission_synthesis(self, **effect):
        self._mission_effect, self._cancelled_before_effect = effect, False
        try:
            self._mission_boundary()
            profile = InitiativeProfile(self.profile_dir)
            directory = (self.root_dir / "mission-conversations" / effect["mission_id"]
                         / effect["step_id"] / uuid4().hex)
            directory.parent.mkdir(parents=True, exist_ok=True)
            request = ("Résume en français les extraits arXiv de la recherche suivante : "
                + effect["query"] + ". Cite seulement les références [W…] et URL du contexte. "
                "Distingue les hypothèses des résultats ; les résumés ne prouvent pas leurs conclusions.")
            with open_conversation(directory, self.backend, max_turns=1, profile=profile) as session:
                def record(receipt):
                    audit_path = str(session._stack.graph.ledger.path)
                    self._fsync_file(audit_path)
                    result = {**receipt, "receipt_id": receipt["cycle_glyph_id"],
                              "conversation_output": str(directory), "audit_path": audit_path}
                    self._save_effect("synthesis", result)
                try:
                    receipt = session.turn(request, source_receipt_id=effect["search_result"]["receipt_id"],
                                           receipt_hook=record, operation_id=effect["step_id"])
                except Exception:
                    if self._cancelled_before_effect:
                        raise KnownEffectFailure("Synthèse annulée avant tout appel Ollama.") from None
                    raise
            return _read_atomic(self._effect_path(effect["step_id"]))["result"]
        finally:
            self._mission_effect = None

    def _reconcile_effect(self, step_id, kind):
        mission = self._supervisor.snapshot()
        step = next(s for s in mission["steps"] if s["step_id"] == step_id)
        path = self._effect_path(step_id)
        if path.exists():
            proof = _read_atomic(path)
            if any(proof.get(key) != value for key, value in {
                "mission_id": mission["mission_id"], "step_id": step_id,
                "kind": kind, "query": step["query"]}.items()):
                raise SupervisorError("Les preuves de reprise ne correspondent pas à l’étape.")
            result = proof["result"]
            if kind == "synthesis":
                recovered = self._synthesis_receipt(Path(result["audit_path"]), mission, step)
                if recovered is None or recovered != result:
                    raise SupervisorError("La remise de la synthèse n’est pas prouvée.")
            else:
                self._verify_search_receipt(step_id, result["receipt_id"])
            return result
        if kind == "search":
            with self._profile.ledger.transaction():
                glyphs = self._profile._state()
            receipt = next((g for g in glyphs if g.content["kind"] == "receipt"
                            and g.content.get("operation_id") == step_id), None)
            if receipt:
                content = receipt.content
                if content["status"] == "failed":
                    return None
                return {"status": content["status"], "evidence": content["evidence"],
                        "sources": content["evidence"], "receipt_id": receipt.glyph_id,
                        "question_id": content["question_id"], "solved": False}
        else:
            directory = self.root_dir / "mission-conversations" / mission["mission_id"] / step_id
            if directory.is_symlink():
                raise SupervisorError("Dossier de reprise invalide.")
            candidates = list(directory.glob("*/stack/glyph_ledger.jsonl")) if directory.exists() else []
            if len(candidates) > 4:
                raise SupervisorError("Trop de tentatives de synthèse à réconcilier.")
            receipts = [r for audit in candidates
                        if (r := self._synthesis_receipt(audit, mission, step)) is not None]
            if len(receipts) > 1:
                raise SupervisorError("Plusieurs remises correspondent à cette étape ; examen requis.")
            if receipts:
                result = receipts[0]
                self._fsync_file(result["audit_path"])
                _write_atomic(path, {"mission_id": mission["mission_id"], "step_id": step_id,
                              "kind": kind, "query": step["query"], "result": result})
                return result
        return None

    def _synthesis_receipt(self, audit, mission, step):
        """Recover a completed, correlated delivery cycle, never raw model bytes.

        A transport response without the mailbox observation/cycle is unknown.
        This reads local evidence only; it cannot repeat the external call.
        """
        from synergesis_glyph_protocol import GlyphLedger
        expected = self.root_dir / "mission-conversations" / mission["mission_id"] / step["step_id"]
        audit = audit.absolute()
        if (not audit.resolve().is_relative_to(expected.resolve())
                or any(p.is_symlink() for p in (audit, *audit.parents))):
            raise SupervisorError("Chemin du reçu de remise invalide.")
        ledger = GlyphLedger(audit)
        ledger.verify()
        glyphs = {g.glyph_id: g for g in ledger.glyphs()}
        parents = {}
        for edge in ledger.edges():
            if edge.relation == "derived_from":
                parents.setdefault(edge.source, []).append(edge.target)
        found = []
        for cycle in glyphs.values():
            if cycle.glyph_type != "cycle":
                continue
            components = [glyphs[i] for i in parents.get(cycle.glyph_id, [])]
            def one(kind):
                matches = [g for g in components if g.glyph_type == kind]
                return matches[0] if len(matches) == 1 else None
            observation, action, policy, outcome = (one(k) for k in ("observation", "action", "policy", "outcome"))
            if not observation or observation.content.get("payload", {}).get("operation_id") != step["step_id"]:
                continue
            if not all((action, policy, outcome)):
                raise SupervisorError("Le cycle de remise est incomplet.")
            payload, parameters = observation.content["payload"], action.content["parameters"]
            text, turn_id = parameters.get("text"), parameters.get("turn_id")
            reality = outcome.content.get("output", {}).get("reality", {})
            verdict = glyphs.get(reality.get("verdict_glyph_id"))
            if (observation.content.get("kind") != "conversation_turn"
                    or action.content.get("action_type") != "emit_reply"
                    or outcome.content.get("action_type") != "emit_reply"
                    or policy.content.get("allowed") is not True
                    or outcome.content.get("success") is not True
                    or reality.get("status") != "confirmed" or reality.get("effect_observed") is not True
                    or not isinstance(text, str) or not text or len(text) > 16000
                    or payload.get("turn_id") != turn_id or not verdict
                    or verdict.content.get("status") != "confirmed"):
                raise SupervisorError("Le cycle ne prouve pas la remise de cette synthèse.")
            observations = [glyphs[i] for i in parents.get(verdict.glyph_id, []) if i in glyphs
                            and glyphs[i].content.get("observer_id") == "runtime:reply-mailbox"]
            if not any(g.content.get("facts") == {"present": True, "turn_id": turn_id,
                        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()} for g in observations):
                raise SupervisorError("Le texte ne correspond pas à l’observation de remise.")
            found.append({"text": text, "turn_id": turn_id, "cycle_glyph_id": cycle.glyph_id,
                "reality_status": "confirmed", "effective_success": True,
                "source_references": [{**r, "cited": '[' + r['alias'] + ']' in text}
                                      for r in payload.get("retrieved_source_references", [])],
                "verification_scope": "in-process mailbox delivery only",
                "receipt_id": cycle.glyph_id, "conversation_output": str(audit.parent.parent),
                "audit_path": str(audit)})
        if len(found) > 1:
            raise SupervisorError("Plusieurs cycles de remise correspondent à cette étape.")
        return found[0] if found else None

    def _verify_search_receipt(self, step_id, receipt_id):
        with self._profile.ledger.transaction():
            glyphs = self._profile._state()
        if not any(g.glyph_id == receipt_id and g.content["kind"] == "receipt"
                   and g.content.get("operation_id") == step_id for g in glyphs):
            raise SupervisorError("Le reçu de recherche persistant est introuvable.")

    def _run_mission_tick(self):
        self._drain_controls()
        with self._guard:
            if self._state["busy"] or not self._jobs.empty():
                return
            self._state["busy"] = True
            self._state["operation"] = {"id": None, "action": "mission_tick", "status": "running",
                "message": "La mission avance sur le service local.", "error": None}
        error = None
        try:
            self._supervisor.tick(self._mission_search, self._mission_synthesis,
                authorization_check=self._mission_authorized, reconcile=self._reconcile_effect)
            self._snapshot_engine()
        except Exception:
            error = "Le superviseur nécessite l’examen de ses traces ; aucune relance automatique."
            self._supervisor_failure = error
        self._snapshot_supervisor()
        with self._guard:
            self._state["busy"] = False
            self._state["operation"] = {"id": None, "action": "mission_tick",
                "status": "failed" if error else "succeeded",
                "message": error or "Étape de mission enregistrée.", "error": error}
            if error:
                self._state["last_error"] = error
            self._state["provider"]["last_model"] = getattr(
                getattr(self.backend, "_opener", None), "last_model", None)

    def _run(self):
        try:
            self._load_documents()
            self._new_conversation()
            self._supervisor = Supervisor(self.root_dir / "supervisor", model=self.model)
            self._snapshot_supervisor()
            self._snapshot_engine()
            self._provider_status()
        except Exception:
            self._startup_error = "Impossible d’ouvrir le profil ou la session. Vérifiez les journaux et les droits du dossier."
        finally:
            self._ready.set()
        try:
            if self._startup_error:
                return
            while not self._stop.is_set():
                self._drain_controls()
                delay = self._supervisor.next_delay() if not self._supervisor_failure else None
                if delay is not None and delay <= 0 and self._jobs.empty():
                    self._run_mission_tick()
                    continue
                try:
                    job = self._jobs.get(timeout=min(5, max(0.05, delay)) if delay is not None else 5)
                except queue.Empty:
                    self._provider_status()
                    continue
                if job is None:
                    break
                request_id, payload = job
                if payload["action"] == "_control_wakeup":
                    self._jobs.task_done()
                    continue
                self._performing_request_id = request_id
                error, message = None, "Opération terminée."
                try:
                    message = self._perform(payload)
                except Exception as exc:
                    if isinstance(exc, UIError):
                        error = str(exc)
                    elif isinstance(exc, InitiativeError):
                        error = self._initiative_error(exc)
                    elif isinstance(exc, ValueError):
                        error = "Le moteur a refusé cette demande ou sa limite de contexte est atteinte. Créez une nouvelle conversation."
                    else:
                        error = "Échec du modèle local ou du moteur. Vérifiez Ollama, puis réessayez ; la tentative est comptée."
                    with self._guard:
                        self._state["last_error"] = error
                        if payload["action"] in {"message", "document_question", "web"}:
                            self._state["conversation"]["messages"].append({
                                "role": "assistant", "content": error, "error": True,
                                "receipt": {"kind": "operation_error", "request_id": request_id,
                                    "action": payload["action"], "conversation_output": self._state["conversation"]["output"],
                                    "transport_trace_path": self._state["transport_trace_path"]}})
                try:
                    self._snapshot_engine()
                except Exception:
                    error = "La lecture des traces du profil a échoué. Les journaux restent conservés."
                self._provider_status()
                self._snapshot_supervisor()
                with self._guard:
                    operation = {"id": request_id, "action": payload["action"],
                        "status": "failed" if error else "succeeded",
                        "message": error or message, "error": error}
                    self._state["operation"] = operation
                    if payload["action"] == "shutdown" and not error:
                        self._stop.set()
                    self._state["busy"] = False
                    self._requests[request_id]["operation"] = deepcopy(operation)
                    if error:
                        self._state["last_error"] = error
                self._jobs.task_done()
                self._performing_request_id = None
                if payload["action"] == "shutdown" and not error:
                    self._stop.set()
                    if self._shutdown_callback:
                        threading.Thread(target=self._shutdown_callback, daemon=True).start()
        finally:
            if self._context is not None:
                self._context.__exit__(None, None, None)
                self._context = self._session = None
            self._stopped.set()

    @staticmethod
    def _initiative_error(error):
        value = str(error)
        if "budget" in value:
            return "Les trois recherches de cette conversation ont été utilisées. Créez une nouvelle conversation."
        if "running" in value:
            return "Une ancienne recherche interrompue nécessite l’inspection de ses traces avant une nouvelle recherche."
        return "Le profil a refusé l’opération : vérifiez ses limites et l’intégrité de ses traces."

    def _add_message(self, role, text, **details):
        with self._guard:
            self._state["conversation"]["messages"].append({"role": role, "content": text, **details})

    def _turn(self, text, display_text=None, *, source_receipt_id=None):
        if self._session._attempts >= MAX_TURNS:
            raise UIError("Les vingt tours de cette conversation sont utilisés. Créez une nouvelle conversation.")
        self._add_message("user", display_text if display_text is not None else text)
        receipt = self._session.turn(text, source_receipt_id=source_receipt_id)
        self._snapshot_engine()
        self._mark_sources(receipt)
        self._add_message("assistant", receipt["text"], receipt=receipt)
        return "Réponse reçue du modèle local."

    def _mark_sources(self, receipt):
        for reference in receipt.get("source_references", []):
            if reference["kind"] not in {"document", "web"}:
                continue
            for source in self._sources:
                if all(source.get(key) == reference.get(key) for key in ("receipt_id", "path", "sha256", "line")):
                    source.update(alias=reference["alias"], supplied=True,
                                  cited=source.get("cited", False) or reference["cited"])

    def _consume_profile_command(self, count=1):
        if self._profile_commands + count > MAX_PROFILE_COMMANDS:
            raise UIError("Les 32 commandes de profil sont utilisées. Créez une nouvelle conversation.")
        self._profile_commands += count

    def _perform(self, payload):
        action, text = payload["action"], payload.get("text", "")
        if action == "mission_start":
            if not self.internet:
                raise UIError("Lancez Syn avec --internet pour autoriser la mission arXiv.")
            self._supervisor.create(payload["queries"], authorized=payload["authorized"],
                title=text, request_id=self._performing_request_id)
            self._snapshot_supervisor()
            return "Mission explicitement autorisée et enregistrée. Le service poursuit son plan."
        if action in {"mission_pause", "mission_resume", "mission_stop"}:
            self._perform_mission_control(payload)
            self._snapshot_supervisor()
            return "Commande de mission enregistrée durablement."
        if action == "new_conversation":
            self._new_conversation()
            with self._guard:
                self._state["last_error"] = None
            return "Nouvelle conversation ouverte ; votre profil est conservé."
        if action == "shutdown":
            return "Interface arrêtée. Vous pouvez fermer cette fenêtre."
        if action == "message":
            return self._turn(text)
        if action == "remember":
            self._consume_profile_command()
            memory_id = self._profile.remember(text)
            self._add_message("assistant", "Souvenir enregistré explicitement dans le profil.",
                receipt={"kind": "memory_saved", "id": memory_id, "text": text})
            return "Souvenir enregistré."
        if action == "recall":
            self._consume_profile_command()
            matches = self._profile.recall(text)
            message = ("Souvenirs retrouvés :\n" + "\n".join(m["text"] for m in matches)
                       if matches else "Aucun souvenir ne correspond à cette recherche.")
            self._add_message("assistant", message,
                receipt={"kind": "memory_lookup", "query": text, "matches": matches})
            return "Consultation de la mémoire terminée."
        if action == "upload_document":
            if len(self._documents) >= MAX_DOCUMENTS:
                raise UIError("La limite de seize documents importés est atteinte.")
            content = payload["content"].encode("utf-8")
            document = {"id": uuid4().hex, "name": payload["name"],
                        "bytes": len(content), "suffix": Path(payload["name"]).suffix.casefold()}
            path = self._document_path(document)
            with path.open("xb") as output:
                output.write(content)
            documents = self._documents + [document]
            temp = self.root_dir / ("documents-" + uuid4().hex + ".tmp")
            temp.write_text(json.dumps(documents, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.root_dir / "documents.json")
            self._documents = documents
            return "Document importé dans le dossier de l’interface."
        if action == "document_question":
            document = next((d for d in self._documents if d["id"] == payload["document_id"]), None)
            if document is None:
                raise UIError("Ce document n’est pas importé dans cette interface.")
            if self._session._attempts >= MAX_TURNS:
                raise UIError("La limite des vingt tours est atteinte. Créez une nouvelle conversation.")
            if self._profile._attempts >= self._profile.max_steps:
                raise UIError("Les trois recherches sont utilisées. Créez une nouvelle conversation.")
            self._consume_profile_command(2)  # add_question + step, same CLI budget
            question_id = self._profile.add_question(text)
            result = self._profile.step([self._document_path(document)], question_id=question_id)
            self._snapshot_engine()
            if result["status"] == "failed":
                raise UIError("La lecture du document a échoué. Consultez ses traces.")
            request = ("Question sur le document " + document["name"] + " : " + text
                + "\nRéponds uniquement à partir des extraits fournis de ce document. "
                  "Cite leurs références [D…]. Si la réponse est absente, indique-le explicitement.")
            return self._turn(request, "Question sur « " + document["name"] + " » : " + text,
                              source_receipt_id=result["receipt_id"])
        if action == "web":
            if not self.internet:
                raise UIError("La recherche scientifique arXiv est désactivée pour ce lancement.")
            if self._session._attempts >= MAX_TURNS:
                raise UIError("La limite des vingt tours est atteinte. Créez une nouvelle conversation.")
            result = self._profile.web_search(text)
            self._snapshot_engine()
            if result["status"] == "failed":
                raise UIError("La recherche arXiv a échoué ; cette recherche est comptée.")
            if result["status"] == "no_evidence":
                self._add_message("assistant", "arXiv ne renvoie aucun résultat pour ces mots-clés.",
                    receipt={"kind": "arxiv_search", **result})
                return "Aucun résultat arXiv."
            request = ("Résume en français les extraits arXiv de la recherche suivante : " + text
                + ". Cite seulement les références [W…] et URL du contexte. "
                  "Distingue les hypothèses des résultats ; ces résumés ne prouvent pas leurs conclusions.")
            return self._turn(request, "Recherche scientifique arXiv : " + text,
                              source_receipt_id=result["receipt_id"])
        raise UIError("Action inconnue.")

    def submit(self, request):
        if not isinstance(request, dict):
            raise UIError("Un objet JSON est requis.")
        allowed = {"request_id", "action", "text", "message", "name", "content", "document_id",
                   "queries", "authorized", "mission_id"}
        if set(request) - allowed:
            raise UIError("Champ de requête inconnu.")
        try:
            request_id = str(UUID(request.get("request_id", "")))
        except (ValueError, TypeError, AttributeError):
            raise UIError("Un request_id UUID est requis.") from None
        action = request.get("action")
        if not isinstance(action, str) or action not in {"message", "remember", "recall", "new_conversation", "web", "upload_document", "document_question", "shutdown",
                "mission_start", "mission_pause", "mission_resume", "mission_stop"}:
            raise UIError("Action inconnue.")
        payload = {k: v for k, v in request.items() if k != "request_id"}
        if "text" in payload and "message" in payload and payload["text"] != payload["message"]:
            raise UIError("Les champs text et message se contredisent.")
        if "message" in payload:
            payload["text"] = payload.pop("message")
        text = payload.get("text", "")
        mission_control = action in {"mission_pause", "mission_resume", "mission_stop"}
        if action == "mission_start":
            if payload.get("authorized") is not True:
                raise UIError("Autorisez explicitement les requêtes arXiv et le modèle local.")
            try:
                Supervisor._validate_queries(payload.get("queries"))
            except SupervisorError:
                raise UIError("Indiquez une à trois requêtes arXiv uniques, de 300 caractères au maximum.") from None
            if not isinstance(text, str) or not text.strip() or len(text) > 2048:
                raise UIError("Décrivez la mission en 1 à 2048 caractères.")
            try:
                text.encode("utf-8")
                json.dumps(payload["queries"], ensure_ascii=False).encode("utf-8")
            except UnicodeError:
                raise UIError("La mission doit être un texte UTF-8 valide.") from None
        if mission_control and (not isinstance(payload.get("mission_id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", payload["mission_id"])):
            raise UIError("Un identifiant de mission est requis.")
        if action in {"message", "remember", "recall", "web", "document_question"}:
            maximum = 300 if action == "web" else (MAX_INPUT_CHARS if action == "message" else 2048)
            if not isinstance(text, str) or len(text) > maximum:
                raise UIError(f"Le texte doit contenir au plus {maximum} caractères.")
            if not text.strip() and action != "message":
                raise UIError("Un texte non vide est requis.")
            try:
                text.encode("utf-8")
            except UnicodeError:
                raise UIError("Le texte doit être un texte UTF-8 valide.") from None
            if action == "web" and any(ord(c) < 32 for c in text):
                raise UIError("La recherche arXiv doit tenir sur une ligne.")
        if action == "upload_document":
            self._validate_name(payload.get("name"))
            if not isinstance(payload.get("content"), str):
                raise UIError("Le contenu du document doit être du texte UTF-8.")
            try:
                content_bytes = payload["content"].encode("utf-8")
            except UnicodeError:
                raise UIError("Le document doit être du texte UTF-8 valide.") from None
            if len(content_bytes) > MAX_DOCUMENT_BYTES:
                raise UIError("Le document dépasse 256 Kio.", 413)
        if action == "document_question" and not isinstance(payload.get("document_id"), str):
            raise UIError("Un identifiant de document importé est requis.")
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        with self._guard:
            previous = self._requests.get(request_id)
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise UIError("Ce request_id a déjà été utilisé pour une autre demande.", 409)
                return {"operation": deepcopy(previous["operation"]), "duplicate": True}
            mission = self._state["supervisor"]["mission"]
            if mission_control:
                if not mission or payload["mission_id"] != mission["mission_id"]:
                    raise UIError("Cette commande concerne une autre mission.", 409)
                if self._state["mission_control"] is not None:
                    raise UIError("Une commande de mission attend déjà son enregistrement.", 409)
                if self._controls.full():
                    raise UIError("La file de contrôle est pleine.", 429)
            elif self._state["busy"]:
                raise UIError("Une opération est déjà en cours. Attendez sa fin.", 409)
            elif mission and mission["status"] == "active" and action != "shutdown":
                raise UIError("Mettez la mission en pause avant de modifier le dialogue ou le profil.", 409)
            if self._stop.is_set() or self._stopped.is_set():
                raise UIError("L’interface est arrêtée.", 503)
            if len(self._requests) >= 2048:
                raise UIError("La limite de requêtes de ce lancement est atteinte. Rouvrez l’interface.", 429)
            if action == "message" and not text.strip():
                operation = {"id": request_id, "action": action, "status": "succeeded",
                             "message": "Message vide ignoré.", "error": None}
                self._requests[request_id] = {"fingerprint": fingerprint, "operation": operation}
                return {"operation": deepcopy(operation), "ignored": True}
            operation = {"id": request_id, "action": action, "status": "running",
                         "message": "Traitement en cours…", "error": None}
            self._requests[request_id] = {"fingerprint": fingerprint, "operation": deepcopy(operation)}
            if mission_control:
                self._state["mission_control"] = {"action": action, "status": "pending", "request_id": request_id}
                self._controls.put_nowait((request_id, payload))
                # Wake an idle queue wait without taking the engine from its owner.
                self._jobs.put((None, {"action": "_control_wakeup"}))
                return {"operation": deepcopy(operation)}
            self._state.update(busy=True, operation=operation, last_error=None)
            self._jobs.put((request_id, payload))
            return {"operation": deepcopy(operation)}

    def close(self, *, timeout=190):
        # Never close a conversation context from a different thread or mid-job.
        self._stop.set()
        self._jobs.put(None)
        if not self._stopped.wait(timeout):
            raise RuntimeError("Le moteur termine encore une opération ; ses verrous sont conservés.")
        for lock in reversed(self._locks):
            lock.close()


class LocalUIServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, service, port=8765):
        self.service = service
        super().__init__(("127.0.0.1", port), LocalUIHandler)
        service.set_shutdown_callback(self.shutdown)


class LocalUIHandler(BaseHTTPRequestHandler):
    server_version = "SynLocal/1"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def _respond(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def _protect(self, mutation=False):
        expected_host = "127.0.0.1:" + str(self.server.server_port)
        hosts = self.headers.get_all("Host", [])
        if hosts != [expected_host]:
            raise UIError("Hôte local invalide.", 403)
        origin = self.headers.get_all("Origin", [])
        if origin and origin != ["http://" + expected_host]:
            raise UIError("Origine externe refusée.", 403)
        sites = self.headers.get_all("Sec-Fetch-Site", [])
        if sites and (len(sites) != 1 or sites[0] not in {"same-origin", "none"}):
            raise UIError("Requête provenant d’un autre site refusée.", 403)
        if mutation:
            tokens = self.headers.get_all("X-Syn-Token", [])
            if len(tokens) != 1 or not secrets.compare_digest(tokens[0], self.server.service.csrf_token):
                raise UIError("Jeton local absent ou invalide.", 403)

    def do_GET(self):
        try:
            self._protect()
            if self.path == "/api/state":
                self._respond(200, self.server.service.state())
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if self.path not in assets:
                raise UIError("Route inconnue.", 404)
            filename, content_type = assets[self.path]
            try:
                body = (ASSET_ROOT / filename).read_bytes()
            except OSError:
                raise UIError("Les fichiers de l’interface sont absents.", 503) from None
            self._respond(200, body, content_type)
        except UIError as error:
            self._respond(error.status, {"error": str(error)})

    def do_POST(self):
        try:
            self._protect(mutation=True)
            if self.path != "/api/action":
                raise UIError("Route inconnue.", 404)
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get_all("Transfer-Encoding", []):
                raise UIError("Le transport segmenté est refusé.")
            if len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0]):
                raise UIError("Une longueur de contenu unique est requise.", 411)
            length = int(lengths[0])
            if length > MAX_BODY_BYTES:
                raise UIError("La requête dépasse la taille autorisée.", 413)
            content_types = self.headers.get_all("Content-Type", [])
            if len(content_types) != 1 or content_types[0].split(";")[0].strip().lower() != "application/json":
                raise UIError("Un corps application/json est requis.", 415)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise UIError("Corps JSON incomplet.")
            def unique_object(pairs):
                obj = {}
                for key, value in pairs:
                    if key in obj:
                        raise ValueError("duplicate JSON key")
                    obj[key] = value
                return obj
            try:
                request = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
            except (ValueError, UnicodeError):
                raise UIError("Le JSON UTF-8 est invalide.") from None
            self._respond(202, self.server.service.submit(request))
        except UIError as error:
            self._respond(error.status, {"error": str(error)})
        except (TimeoutError, ConnectionError, OSError):
            self.close_connection = True

    def _unsupported(self):
        try:
            self._protect()
            self._respond(405, {"error": "Méthode refusée."})
        except UIError as error:
            self._respond(error.status, {"error": str(error)})

    do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _unsupported


def create_server(service, port=8765):
    return LocalUIServer(service, port)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Interface web locale Synergesis (Linux / WSL).")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", default="mistral")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ollama-port", type=int, default=11434)
    parser.add_argument("--internet", action="store_true", help="Autoriser les requêtes scientifiques arXiv explicites.")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Le port local doit être compris entre 1 et 65535.")
    service = server = None
    try:
        service = LocalUIService(args.profile, args.root, model=args.model,
            ollama_port=args.ollama_port, internet=args.internet)
        server = create_server(service, args.port)
        print(f"Syn est ouvert sur http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever(poll_interval=0.2)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("L’interface Syn ne peut pas démarrer. Vérifiez le port, le profil et le dossier de service.", flush=True)
        return 1
    finally:
        if server:
            server.server_close()
        if service:
            service.close()


if __name__ == "__main__":
    raise SystemExit(main())
