"""Record a bounded real execution of the historical four prompt conditions.

No oracle input. Uses syn_four_arm_trial_v0's prompts, parser and attempt schema.
Adds raw HTTP receipts, model pinning, randomized order and enforced call budgets.
This is a prompt experiment, not four full SYN deployments.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import time
import urllib.request


def legacy_module():
    path = Path(__file__).with_name("syn_four_arm_trial_v0.py")
    spec = importlib.util.spec_from_file_location("recorded_legacy_four_arm", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity(opener, model, port):
    with opener.open(f"http://127.0.0.1:{port}/api/tags", timeout=10) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("oversized model inventory")
    models = [x for x in json.loads(raw)["models"] if x.get("name") == model]
    if len(models) != 1:
        raise ValueError("model is not installed; no download allowed")
    return {k: models[0][k] for k in ("name", "digest", "details")}


class RecordedBackend:
    def __init__(self, legacy, manifest, requests, root, *, port=11434, seed=26):
        self.backend = legacy.LocalOllama(manifest["model_id"], port=port, seed=seed)
        self.transport = self.backend._opener
        self.identity = identity(self.transport, manifest["model_id"], port)
        self.legacy, self.manifest, self.requests, self.root = legacy, manifest, requests, root
        self.port, self.index, self.tokens = port, 0, dict.fromkeys(legacy.ARMS, 0)
        self.deadline = time.monotonic() + 1800
        self.backend._opener = self

    def open(self, request, timeout):
        question = self.requests[self.index]
        self.legacy._check(self.index < len(self.requests) and time.monotonic() < self.deadline,
                           "fixed trial call count or deadline exceeded")
        self.legacy._check(self.tokens[question["arm"]] + 4224 <= self.manifest["token_budget_per_arm"],
                           "registered arm token budget exhausted")
        current = identity(self.transport, self.manifest["model_id"], self.port)
        self.legacy._check(current["digest"] == self.identity["digest"], "installed model changed")
        payload = json.loads(request.data)
        payload["options"]["num_ctx"] = 4096
        data = json.dumps(payload, ensure_ascii=False).encode()
        folder = self.root / "transport" / f"{self.index:03d}"
        folder.mkdir(parents=True)
        self.legacy._atomic_new(folder / "request.json", data.decode() + "\n")
        actual = urllib.request.Request(request.full_url, data=data, headers=dict(request.headers), method="POST")
        started = time.monotonic()
        with self.transport.open(actual, timeout=timeout) as response:
            raw, status = response.read(65537), response.status
        with (folder / "response.json").open("xb") as stream:
            stream.write(raw)
        self.legacy._check(status == 200 and len(raw) <= 65536, "provider response failed")
        parsed = json.loads(raw)
        p, q = parsed.get("prompt_eval_count"), parsed.get("eval_count")
        self.legacy._check(type(p) is int and type(q) is int and 0 <= p <= 4096 and 0 <= q <= 128,
                           "measured usage absent or outside fixed context/output bounds")
        self.tokens[question["arm"]] += p+q
        self.legacy._check(self.tokens[question["arm"]] <= self.manifest["token_budget_per_arm"],
                           "measured arm budget exceeded")
        self.legacy._atomic_new(folder / "receipt.json", json.dumps({
            "task_id": question["task_id"], "arm": question["arm"], "http_status": status,
            "request_sha256": hashlib.sha256(data).hexdigest(),
            "response_sha256": hashlib.sha256(raw).hexdigest(), "tokens_used": p+q,
            "elapsed_seconds": time.monotonic()-started, "model_digest": self.identity["digest"]}, indent=2)+"\n")
        self.legacy._check(identity(self.transport, self.manifest["model_id"], self.port)["digest"]
                           == self.identity["digest"], "model changed during call")
        return io.BytesIO(raw)

    def __call__(self, prompt):
        self.legacy._check(self.index < len(self.requests) and prompt == self.requests[self.index]["prompt"],
                           "unregistered prompt or extra call")
        answer, tokens = self.backend(prompt)
        self.index += 1
        print(json.dumps({"completed": self.index, "total": len(self.requests)}), flush=True)
        return answer, tokens


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--seed", type=int, default=26)
    args = parser.parse_args()
    old = legacy_module()
    manifest, train, test = old._read_json(args.manifest), old._read_jsonl(args.train), old._read_jsonl(args.test)
    requests = old.build_requests(manifest, train, test)
    old._check(len(requests) <= 120, "recorded pilot limited to 120 model calls")
    old._check(not args.out.exists() and not args.out.is_symlink(), "refusing overwrite")
    args.out.mkdir(parents=True, mode=0o700)
    random.Random(args.seed).shuffle(requests)
    backend = RecordedBackend(old, manifest, requests, args.out, port=args.port, seed=args.seed)
    old._atomic_new(args.out / "requests.jsonl", "".join(json.dumps(r, ensure_ascii=False)+"\n" for r in requests))
    old._atomic_new(args.out / "preregistration.json", json.dumps({
        "schema": "syn-four-arm-recorded-v1", "model": backend.identity, "order_seed": args.seed,
        "n_tasks": len(test), "n_requests": len(requests), "context_limit": 4096,
        "output_limit": 128, "deadline_seconds": 1800,
        "token_budget_per_arm": manifest["token_budget_per_arm"],
        "input_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in
                          (("manifest", args.manifest), ("train", args.train), ("test", args.test))},
        "warning": "Real local model calls on synthetic tasks; four prompt conditions, not four SYN agents. Oracle is not an input."}, indent=2)+"\n")
    try:
        result = old.run(requests, manifest["model_id"], backend, args.out / "run")
    except Exception as exc:
        old._atomic_new(args.out / "status.json", json.dumps({
            "status": "incomplete_not_scored", "completed": backend.index,
            "error_type": type(exc).__name__, "automatic_retry": False}, indent=2)+"\n")
        raise
    result.update({"physical_calls": backend.index, "measured_tokens_by_arm": backend.tokens,
                   "model_digest": backend.identity["digest"]})
    old._atomic_new(args.out / "status.json", json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
