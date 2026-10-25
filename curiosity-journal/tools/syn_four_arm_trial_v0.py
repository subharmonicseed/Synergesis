"""Run or prepare a four-arm skill-transfer experiment without any oracle access.

'prepare' creates prompts usable in independent ChatGPT sessions without an API.
'ollama' calls only a user-selected model at 127.0.0.1, recording actual token
usage; it never reads oracle.jsonl or scores itself. All arms are prompt-level
*simulations of context availability*, not separate autonomous SYN deployments.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request
from typing import Callable

ARMS = ("baseline", "journal", "research", "skills")
DOMAINS = ("arithmetic", "calendar", "graph")
MAX_INPUT_BYTES = 2_000_000
MAX_TASKS = 300

PROCEDURES = {
    "arithmetic": "Use mathematical precedence and signs. First calculate each multiplication, then subtract the terms; output an exact integer.",
    "calendar": "Use a Gregorian calendar with leap days. Advance the specified count of days, crossing month and year boundaries when necessary. Format YYYY-MM-DD.",
    "graph": "Edges are directed, not undirected. From the starting node visit each outgoing edge until no new nodes remain or the target is found.",
}


class TrialError(ValueError):
    pass


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise TrialError(msg)


def _read_json(path: Path):
    _check(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_INPUT_BYTES, "invalid input file")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise TrialError("invalid JSON") from exc


def _read_jsonl(path: Path) -> list[dict]:
    _check(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_INPUT_BYTES, "invalid JSONL file")
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (UnicodeError, ValueError) as exc:
        raise TrialError("invalid JSONL") from exc
    _check(all(isinstance(row, dict) for row in rows), "JSONL rows must be objects")
    return rows


def _rows(manifest: dict, train: list[dict], test: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    _check(isinstance(manifest, dict) and manifest.get("schema") == "syn-skill-transfer-eval-v0", "wrong manifest schema")
    _check(manifest.get("arms") == list(ARMS), "invalid arms")
    _check(isinstance(manifest.get("model_id"), str) and 0 < len(manifest["model_id"]) <= 300, "bad model_id")
    requested = manifest.get("test_tasks")
    _check(isinstance(requested, list) and 1 <= len(requested) <= MAX_TASKS, "invalid test tasks")
    ids = set()
    domains = {}
    for row in requested:
        _check(isinstance(row, dict) and set(row) == {"task_id", "domain"}, "invalid test task metadata")
        tid, domain = row["task_id"], row["domain"]
        _check(isinstance(tid, str) and bool(tid.strip()) and tid not in ids and domain in DOMAINS, "invalid task ID or domain")
        ids.add(tid)
        domains[tid] = domain
    _check(isinstance(manifest.get("train_task_ids"), list), "missing training IDs")
    train_ids = set(manifest["train_task_ids"])
    _check(len(train_ids) == len(manifest["train_task_ids"]) and not train_ids.intersection(ids), "train/test ID overlap")
    train_by_domain = {domain: [] for domain in DOMAINS}
    train_seen = set()
    train_prompts = set()
    for row in train:
        _check(set(row) == {"task_id", "domain", "prompt", "answer"}, "bad train row")
        tid, dom, prompt, answer = (row[k] for k in ("task_id", "domain", "prompt", "answer"))
        _check(tid in train_ids and tid not in train_seen and dom in DOMAINS, "invalid training ID or domain")
        _check(isinstance(prompt, str) and 0 < len(prompt) <= 4000 and isinstance(answer, str) and 0 < len(answer) <= 300, "invalid train data")
        train_seen.add(tid)
        train_prompts.add(prompt)
        train_by_domain[dom].append(row)
    _check(train_seen == train_ids, "missing training rows")
    test_seen = set()
    clean_test = []
    for row in test:
        _check(set(row) == {"task_id", "domain", "prompt"}, "test answers are forbidden in prompt pack")
        tid, dom, prompt = (row[k] for k in ("task_id", "domain", "prompt"))
        _check(tid in ids and tid not in test_seen and dom == domains[tid], "unknown/duplicate test task")
        _check(isinstance(prompt, str) and 0 < len(prompt) <= 4000 and prompt not in train_prompts, "bad test prompt or exact leakage")
        test_seen.add(tid)
        clean_test.append(row)
    _check(test_seen == ids, "missing test prompts")
    _check(len(set(domains.values())) >= 2, "two test domains required")
    return clean_test, train_by_domain


def build_requests(manifest: dict, train: list[dict], test: list[dict]) -> list[dict]:
    """Return requests WITHOUT expected answers or oracle references."""
    test_rows, by_domain = _rows(manifest, train, test)
    messages = []
    for arm in ARMS:
        for row in test_rows:
            examples = by_domain[row["domain"]]
            sections = ["You are doing a controlled toy skill-transfer trial.",
                        "Answer the task; output ONLY JSON with one string field named answer.",
                        "Do not ask for the ground truth or read any hidden oracle."]
            if arm in ("journal", "research", "skills"):
                sections += ["Earlier solved exercises (training examples, not this test):"]
                sections.extend(f"Q: {x['prompt']}\nA: {x['answer']}" for x in examples)
            if arm in ("research", "skills"):
                sections += ["A previously provided, human-authored procedure (NOT an actual independent research tool):", PROCEDURES[row["domain"]]]
            if arm == "skills":
                sections += ["A candidate skill has been made available for reuse. Apply the general procedure above, but independently check the result. Its transfer has NOT been validated."]
            sections += ["Current task:", row["prompt"]]
            content = "\n\n".join(sections)
            _check(len(content) <= 25000, "excessive prompt")
            messages.append({"task_id": row["task_id"], "arm": arm, "domain": row["domain"], "model_id": manifest["model_id"],
                             "prompt": content,
                             "skill_ids": [f"human-procedure-{row['domain']}-v0"] if arm == "skills" else []})
    return messages


def _atomic_new(path: Path, content: str) -> None:
    _check(not path.exists() and not path.is_symlink(), "refusing to overwrite output")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(content)
        out.flush()
        os.fsync(out.fileno())


def prepare(manifest: dict, train: list[dict], test: list[dict], output: Path) -> dict:
    requests = build_requests(manifest, train, test)
    _check(not output.exists(), "output directory already exists")
    output.mkdir(parents=True, mode=0o700)
    _atomic_new(output / "requests.jsonl", "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in requests))
    _atomic_new(output / "NOTICE.txt", "Manual ChatGPT use: create FOUR independent chats (one per arm), copy prompts without answers between chats, preserve output JSON, then explicitly build attempts.\nThis pack contains NO ground-truth answers and cannot prove isolation, token usage, or causal skill transfer.\n")
    return {"n_tasks": len(test), "n_requests": len(requests), "output": str(output), "arms": list(ARMS),
            "status": "prepared_not_executed"}


class LocalOllama:
    """Loopback only; actual token usage must be reported, never inferred."""
    def __init__(self, model: str, port: int = 11434, seed: int = 26, timeout: int = 90):
        _check(isinstance(model, str) and re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,128}", model) is not None and ".." not in model and "://" not in model and "//" not in model and not model.startswith("/"), "invalid model name")
        _check(type(port) is int and 1 <= port <= 65535, "invalid local port")
        _check(type(seed) is int and 0 <= seed <= 2**31 - 1, "invalid seed")
        _check(type(timeout) is int and 1 <= timeout <= 180, "invalid timeout")
        self.model, self.port, self.seed, self.timeout = model, port, seed, timeout
        class _NeverRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NeverRedirect())

    def __call__(self, prompt: str) -> tuple[str, int]:
        payload = json.dumps({"model": self.model, "messages": [{"role": "user", "content": prompt}],
                              "format": "json", "stream": False,
                              "options": {"temperature": 0, "seed": self.seed, "num_predict": 128}}, ensure_ascii=False).encode()
        _check(len(payload) < 90_000, "payload too large")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/chat", data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as res:
                raw = res.read(65537)
            _check(len(raw) <= 65536, "oversized model reply")
            result = json.loads(raw)
            _check(result.get("done") is True and isinstance(result.get("message"), dict), "incomplete model reply")
            content = result["message"].get("content")
            _check(isinstance(content, str) and len(content) < 8000, "invalid model content")
            parsed = json.loads(content)
            _check(isinstance(parsed, dict) and set(parsed) == {"answer"} and isinstance(parsed["answer"], str)
                   and 0 < len(parsed["answer"]) <= 300, "model did not return answer schema")
            prompt_tokens, reply_tokens = result.get("prompt_eval_count"), result.get("eval_count")
            _check(type(prompt_tokens) is int and type(reply_tokens) is int
                   and 0 <= prompt_tokens <= 1_000_000 and 0 <= reply_tokens <= 1_000_000,
                   "no measured usage; refusing to invent tokens")
            return parsed["answer"], prompt_tokens + reply_tokens
        except Exception as exc:
            raise RuntimeError("Local Ollama call failed or returned invalid answer/usage") from exc


def run(requests: list[dict], model_id: str, backend: Callable[[str], tuple[str, int]], out: Path) -> dict:
    """Runs genuine backend calls, not synthetic score assignment. No oracle read."""
    _check(all(isinstance(q, dict) and q.get("model_id") == model_id for q in requests), "model_id mismatch")
    _check(not out.exists(), "refusing to overwrite past trial")
    out.mkdir(mode=0o700, parents=True)
    response_path = out / "attempts.jsonl"
    # Each verified response is persisted immediately, preserving work on interruption.
    fd = os.open(response_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    completed = 0
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        for q in requests:
            answer, measured_tokens = backend(q["prompt"])
            _check(isinstance(answer, str) and 0 < len(answer) <= 300 and type(measured_tokens) is int and measured_tokens >= 0, "invalid backend result")
            record = {"task_id": q["task_id"], "arm": q["arm"], "model_id": model_id,
                      "answer": answer, "tokens_used": measured_tokens, "skill_ids": q["skill_ids"]}
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            completed += 1
    return {"n_attempts": completed, "path": str(response_path), "status": "completed_unscored",
            "warning": "Not an ablation of SYN itself. Prompt arm labels do not prove skills, research, or isolated state."}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("prepare", "run-ollama"))
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--train", type=Path, required=True)
    p.add_argument("--test", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ollama-port", type=int, default=11434)
    p.add_argument("--seed", type=int, default=26)
    args = p.parse_args()
    manifest = _read_json(args.manifest)
    train, test = _read_jsonl(args.train), _read_jsonl(args.test)
    if args.action == "prepare":
        report = prepare(manifest, train, test, args.out)
    else:
        questions = build_requests(manifest, train, test)
        report = run(questions, manifest["model_id"], LocalOllama(manifest["model_id"], args.ollama_port, args.seed), args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
