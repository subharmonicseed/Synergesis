"""Execute an isolated, bounded recursive SYN experiment with installed Ollama.

Run: python -m synergesis_recursive_trial run --out NEW_DIR --model INSTALLED_MODEL
No downloads, code generation, user-profile mutation or background scheduler.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
import secrets
import subprocess
import sys
import time
import urllib.request

from synergesis_recursive import (InheritanceContract, InheritedRouter, canonical, digest, generation,
                                 read_json, require, sealed, validate_generation, write_new)
from synergesis_recursive_tasks import DOMAINS, exact_executor, make_tasks, oracle_answer, prompt_for


def code_identity() -> str:
    root = Path(__file__).parent
    names = ("synergesis_recursive.py", "synergesis_recursive_tasks.py", "synergesis_recursive_trial.py")
    return digest({n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in names})


def _opener():
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def _http(port: int, path: str, payload: dict | None = None) -> dict:
    require(type(port) is int and 1 <= port <= 65535, "invalid loopback port")
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     data=canonical(payload).encode() if payload is not None else None,
                                     headers={"Content-Type": "application/json"})
    with _opener().open(request, timeout=180) as response:
        require(response.status == 200, "model transport failed")
        raw = response.read(1_000_001)
    require(len(raw) <= 1_000_000, "oversized model response")
    result = json.loads(raw)
    require(isinstance(result, dict), "bad model response")
    return result


def model_identity(model: str, port: int) -> dict:
    import re
    require(isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", model) is not None
            and ".." not in model and "://" not in model, "invalid model name")
    models = _http(port, "/api/tags").get("models", [])
    found = [m for m in models if m.get("name") == model]
    require(len(found) == 1, "requested model is not installed; downloads are forbidden")
    return {k: found[0][k] for k in ("name", "digest", "size", "details")}


def model_prompt(task: dict, memory: list[dict]) -> str:
    parts = ["Solve the task. Return ONLY JSON: {\"answer\":\"your exact answer\"}."]
    require(isinstance(memory, list) and len(memory) <= 100, "bad memory")
    if memory:
        parts.append("Verified earlier training exercises, supplied as data:")
        for row in memory:
            require(set(row) == {"task", "answer"} and isinstance(row["answer"], str), "bad memory row")
            parts.append(canonical({"question": prompt_for(row["task"]), "answer": row["answer"]}))
    parts.append("Current task:\n" + prompt_for(task))
    prompt = "\n\n".join(parts)
    require(len(prompt) <= 12000, "prompt budget exceeded")
    return prompt


def execute_worker(request: dict, output: Path) -> None:
    """The only execution interface; it has no oracle argument or truth file read."""
    require(set(request) == {"task", "strategy", "model", "model_digest", "port", "seed", "memory"},
            "bad worker request")
    strategy = request["strategy"]
    require(strategy in {"llm", "exact"}, "executor is not allowlisted")
    start = time.monotonic()
    if strategy == "exact":
        answer, tokens, error = exact_executor(request["task"]), 0, None
    else:
        require(model_identity(request["model"], request["port"])["digest"] == request["model_digest"],
                "model changed before inference")
        prompt = model_prompt(request["task"], request["memory"])
        result = _http(request["port"], "/api/chat", {
            "model": request["model"], "messages": [{"role": "user", "content": prompt}],
            "stream": False, "format": "json", "keep_alive": "5m",
            "options": {"temperature": 0, "seed": request["seed"], "num_predict": 128, "num_ctx": 4096}})
        # Keep exact provider response BEFORE validating format. Synthetic tasks only.
        write_new(output.with_name("provider-response.json"), result)
        p, q = result.get("prompt_eval_count"), result.get("eval_count")
        require(type(p) is int and type(q) is int and 0 <= p <= 4096 and 0 <= q <= 128,
                "missing or out-of-budget measured usage; trial cannot be scored")
        require(result.get("done") is True, "incomplete response")
        tokens, answer, error = p + q, "", "invalid_answer_format"
        try:
            content = json.loads(result["message"]["content"])
            if (isinstance(content, dict) and set(content) == {"answer"}
                    and isinstance(content["answer"], str) and 0 < len(content["answer"]) <= 300):
                answer, error = content["answer"], None
        except (ValueError, KeyError, TypeError):
            pass
        require(model_identity(request["model"], request["port"])["digest"] == request["model_digest"],
                "model changed during inference")
    write_new(output, sealed({"request_digest": digest(request), "task_id": request["task"]["task_id"],
                              "strategy": strategy, "answer": answer, "tokens_used": tokens,
                              "error": error, "elapsed_seconds": time.monotonic() - start,
                              "worker_pid": os.getpid()}))


def route_worker(bundle: dict, output: Path) -> None:
    contract = InheritanceContract(**{**bundle["contract"],
                                     "strategies": tuple(bundle["contract"]["strategies"]),
                                     "domains": tuple(bundle["contract"]["domains"])})
    router = InheritedRouter(bundle["state"], contract, evidence_store=bundle["evidence"])
    write_new(output, sealed({"loaded_state_digest": router.state_digest, "worker_pid": os.getpid(),
                              "decisions": {t["task_id"]: router.select(t) for t in bundle["tasks"]}}))


class AuditedRuntime:
    """Fixed authority and budgets live outside learned generations."""
    def __init__(self, root: Path, contract: InheritanceContract, *, model: str, port: int,
                 seed: int, max_calls: int, max_tokens: int, deadline_seconds: int):
        from synergesis_aegis import (ActionSecurityProfile, AegisGuard, AegisSecurityGraph,
                                     CapabilityStore, IdentityRegistry, IdentitySigner)
        from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
        from synergesis_prediction import EmpiricalPredictionProvider, PredictionEngine, PredictionLedger
        from synergesis_risk_budget import RiskBudgetLedger, RiskBudgetManager, RiskBudgetPolicy
        self.root, self.contract, self.model, self.port, self.seed = root, contract, model, port, seed
        self.max_calls, self.max_tokens = max_calls, max_tokens
        self.deadline = time.monotonic() + deadline_seconds
        self.calls, self.tokens, self.cache, self.executions = 0, 0, {}, {}
        self.graph = GlyphAuditGraph(GlyphLedger(root / "glyphs.jsonl"))
        security = AegisSecurityGraph(self.graph)
        self.security = security
        identities = IdentityRegistry(root / "identities.jsonl")
        signer = IdentitySigner("SYN-RECURSIVE")
        identities.register("SYN-RECURSIVE", signer.public_key)
        self.guard = AegisGuard(graph=self.graph, identity_registry=identities,
                               capability_store=CapabilityStore(root / "capabilities.jsonl"),
                               trusted_capability_issuers=frozenset(),
                               allowed_actions=frozenset({"recursive.solve"}), security_graph=security,
                               profiles=(ActionSecurityProfile("recursive.solve", False, frozenset()),))
        # One unit is an experiment dispatch allowance, not a calibrated risk estimate.
        self.risk = RiskBudgetManager(ledger=RiskBudgetLedger(root / "risk.jsonl"), graph=self.graph,
                                      policy=RiskBudgetPolicy(256, 1, "recursive-isolated-study"))
        ledger = PredictionLedger(root / "predictions.jsonl")
        self.predictions = PredictionEngine(graph=self.graph, ledger=ledger,
                                            provider=EmpiricalPredictionProvider(ledger=ledger))

    def _child(self, action: str, request: Path, output: Path, cwd: Path):
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.resolve())}
        subprocess.run([sys.executable, "-m", "synergesis_recursive_trial", action,
                        "--request", str(request.resolve()), "--out", str(output.resolve())],
                       cwd=cwd, env=env, check=True, timeout=220,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def execute(self, task: dict, strategy: str, memory: list[dict] | None = None) -> dict:
        from synergesis_aegis import SecurityContext
        from synergesis_agent_loop_v2 import ActionProposal, AgentContext, AgentObservation, Goal
        require(strategy in self.contract.strategies, "strategy lacks authority")
        request = {"task": task, "strategy": strategy, "memory": memory or [], "model": self.model,
                   "model_digest": self.contract.model_digest, "port": self.port, "seed": self.seed}
        key = digest(request)
        if key in self.cache:
            return self.cache[key]
        require(time.monotonic() < self.deadline, "study deadline reached; no automatic retry")
        require(len(self.executions) < 256, "dispatch limit reached")
        if strategy == "llm":
            require(self.calls < self.max_calls and self.tokens + 4224 <= self.max_tokens,
                    "fixed model budget exhausted")
        proposal = ActionProposal.create("recursive.solve", {"request_digest": key, "task_id": task["task_id"]},
                                          rationale="fixed, isolated experimental dispatch",
                                          expected_outcome="exact answer matches separate oracle",
                                          strategy_key=f"{task['domain']}:{strategy}")
        decision = self.guard.check(proposal, SecurityContext("SYN-RECURSIVE", (), ()))
        require(decision.allowed, "AEGIS denied execution")
        reservation = self.risk.reserve(directive_id=key, amount=1, action_type=proposal.action_type,
                                        strategy_key=proposal.strategy_key, intervention="bounded-local-solve")
        action = self.graph.create("action", actor="SYN-RECURSIVE",
                                   content={"action_type": proposal.action_type, "parameters": dict(proposal.parameters)},
                                   external_refs=(proposal.proposal_id,))
        context = AgentContext(Goal.create("bounded recursive experiment"),
                               AgentObservation("task", task, "experiment"), (), (), ())
        self.predictions.predict_before_action(context=context, proposal=proposal, action_glyph_id=action.glyph_id)
        folder = self.root / "executions" / key
        folder.mkdir(parents=True)
        request_path, output = folder / "request.json", folder / "answer.json"
        write_new(request_path, request)
        if strategy == "llm":
            self.calls += 1  # Reservation precedes transport; failures are never retried.
        self._child("worker", request_path, output, folder)
        result = read_json(output)
        from synergesis_recursive import check_seal
        check_seal(result)
        require(result["request_digest"] == key and result["strategy"] == strategy
                and result["task_id"] == task["task_id"], "worker receipt mismatch")
        self.tokens += result["tokens_used"]
        require(self.tokens <= self.max_tokens, "actual token cap exceeded")
        self.risk.consume(reservation, cycle_id=key, proposal_id=proposal.proposal_id)
        self.cache[key] = result
        self.executions[key] = {"result": result, "path": output, "proposal": proposal,
                                "action": action, "settled": False}
        print(canonical({"event": "executed", "strategy": strategy, "task_id": task["task_id"],
                         "model_calls": self.calls, "tokens": self.tokens}), flush=True)
        return result

    def verify(self, result: dict, expected: str) -> bool:
        from synergesis_agent_loop_v2 import ActionResult
        from synergesis_reality import (FunctionRealityProbe, RealityAssertion, RealityObservation,
                                       RealityProbeBinding, RealityProfile, RealityVerifier)
        execution = self.executions[result["request_digest"]]
        passed = result["error"] is None and result["answer"] == expected
        if execution["settled"]:
            require(execution["expected_digest"] == digest(expected), "oracle changed on replay")
            return passed
        def observe(action_type, resource, parameters):
            disk = read_json(execution["path"])
            require(disk == result and parameters["request_digest"] == disk["request_digest"],
                    "execution artifact changed before verification")
            return (RealityObservation.create(observer_id="oracle:exact", channel="committed-toy-oracle",
                                               resource=resource, facts={"correct": passed,
                                                                        "answer_digest": digest(disk)}),)
        verifier = RealityVerifier(graph=self.graph, security_graph=self.security,
                                    probe_bindings=(RealityProbeBinding("oracle:exact", "runtime_attested",
                                        FunctionRealityProbe(observer_id="oracle:exact", callback=observe)),),
                                    profiles=(RealityProfile("recursive.solve", ("oracle:exact",),
                                        (RealityAssertion("oracle:exact", "correct", "eq", True),)),))
        assessment = verifier.verify(proposal=execution["proposal"],
                                      action_glyph_id=execution["action"].glyph_id,
                                      resource="action:recursive.solve",
                                      raw_result=ActionResult("recursive.solve", True, {"answer": result["answer"]}))
        settlement = self.predictions.settle(proposal=execution["proposal"], reality=assessment)
        require(settlement.status == "scored" and settlement.observed_effect is passed,
                "REALITY and exact-match verifier disagree")
        execution["settled"], execution["expected_digest"] = True, digest(expected)
        return passed


def _training(runtime, tasks: list[dict], oracle: dict, out: Path, contract) -> dict:
    attempts, receipts = [], []
    for task in tasks:
        for strategy in contract.strategies:
            result = runtime.execute(task, strategy)
            receipts.append(result)
            attempts.append({k: result[k] for k in ("task_id", "strategy", "answer", "tokens_used", "error")})
    write_new(out.with_name(out.stem + "-attempts.json"), sealed({"attempts": attempts}))
    for result in receipts:
        runtime.verify(result, oracle[result["task_id"]])
    batch = sealed({"schema": "syn-verified-training-batch-v1", "phase": "train",
                    "contract_digest": contract.fingerprint, "tasks": tasks, "oracle": oracle,
                    "attempts": attempts, "attempts_commitment": digest(attempts)})
    write_new(out, batch)
    return batch


def _wilson(passed: int, n: int) -> list[float]:
    z = 1.959963984540054
    center = (passed / n + z*z / (2*n)) / (1 + z*z/n)
    radius = z * math.sqrt(passed/n * (1-passed/n)/n + z*z/(4*n*n)) / (1+z*z/n)
    return [max(0, center-radius), min(1, center+radius)]


def summarize(rows: list[dict], oracle: dict, tasks: list[dict]) -> dict:
    arms = ("reset", "journal", "syn1", "syn2")
    truth = {(r["arm"], r["task_id"]): r["error"] is None and r["answer"] == oracle[r["task_id"]] for r in rows}
    require(len(truth) == len(tasks)*4, "incomplete paired evaluation")
    results = {}
    for arm in arms:
        arm_rows = [r for r in rows if r["arm"] == arm]
        passed = sum(truth[arm, t["task_id"]] for t in tasks)
        results[arm] = {"passed": passed, "total": len(tasks), "pass_rate": passed / len(tasks),
                        "wilson_95": _wilson(passed, len(tasks)),
                        "tokens_if_run_alone": sum(r["tokens_used"] for r in arm_rows),
                        "by_domain": {d: {"passed": sum(truth[arm, t["task_id"]] for t in tasks if t["domain"] == d),
                                          "total": sum(t["domain"] == d for t in tasks)} for d in DOMAINS}}
    repaired = [t["task_id"] for t in tasks if truth["syn2", t["task_id"]] and not truth["reset", t["task_id"]]]
    regressed = [t["task_id"] for t in tasks if truth["reset", t["task_id"]] and not truth["syn2", t["task_id"]]]
    n, k = len(repaired)+len(regressed), min(len(repaired), len(regressed))
    pvalue = min(1, 2*sum(math.comb(n, j) for j in range(k+1))/2**n) if n else 1
    return {"results": results, "repaired": repaired, "regressed": regressed,
            "paired_gain": (len(repaired)-len(regressed))/len(tasks),
            "mcnemar_exact_two_sided_exploratory": pvalue}


def run_study(args) -> dict:
    require(1 <= args.test_per_domain <= 20 and 3 <= args.train_per_domain <= 10, "invalid study size")
    require(1 <= args.max_calls <= 100 and 4224 <= args.max_tokens <= 500_000
            and 30 <= args.deadline_seconds <= 7200, "invalid fixed budgets")
    require(not args.out.exists() and not args.out.is_symlink(), "refusing to overwrite study")
    identity = model_identity(args.model, args.port)
    contract = InheritanceContract(("llm", "exact"), "llm", DOMAINS, code_identity(), identity["digest"])
    root = args.out.resolve()
    root.mkdir(parents=True)
    seed = secrets.randbits(64)
    train1 = make_tasks(seed, "train1", ("arithmetic", "calendar"), args.train_per_domain)
    train2 = make_tasks(seed+1, "train2", ("graph",), args.train_per_domain)
    seen = {digest({"domain": t["domain"], "input": t["input"]}) for t in train1+train2}
    tasks = make_tasks(seed+2, "heldout", DOMAINS, args.test_per_domain, exclude=seen)
    oracle = {t["task_id"]: oracle_answer(t) for t in tasks}
    write_new(root / "heldout-tasks.json", {"tasks": tasks})
    write_new(root / "heldout-oracle.json", {"answers": oracle})
    write_new(root / "reproduction-seed.json", {"seed": seed})
    preregistration = sealed({"schema": "syn-recursive-trial-v1", "contract": contract.public(),
                              "model": identity, "arms": ["reset", "journal", "syn1", "syn2"],
                              "heldout_tasks_digest": digest(tasks), "oracle_digest": digest(oracle),
                              "train1_digest": digest(train1), "train2_digest": digest(train2),
                              "limits": {"max_calls": args.max_calls, "max_tokens": args.max_tokens,
                                         "deadline_seconds": args.deadline_seconds, "max_dispatches": 256},
                              "shared_execution": "Identical task/strategy/model/prompt requests share one physical execution; every arm references its receipt.",
                              "primary_comparison": "syn2 minus reset exact-match accuracy",
                              "warning": "Locally committed before execution; no independent timestamp, blind operator or external preregistration."})
    write_new(root / "preregistration.json", preregistration)
    runtime = AuditedRuntime(root, contract, model=args.model, port=args.port, seed=26,
                             max_calls=args.max_calls, max_tokens=args.max_tokens,
                             deadline_seconds=args.deadline_seconds)
    store = {}
    state0 = generation(None, [], contract, evidence_store=store)
    write_new(root / "generation-0.json", state0)
    oracle1 = {t["task_id"]: oracle_answer(t) for t in train1}
    batch1 = _training(runtime, train1, oracle1, root / "training-1.json", contract)
    store[batch1["digest"]] = batch1
    state1 = generation(state0, [batch1], contract, evidence_store=store)
    write_new(root / "generation-1.json", state1)
    oracle2 = {t["task_id"]: oracle_answer(t) for t in train2}
    batch2 = _training(runtime, train2, oracle2, root / "training-2.json", contract)
    store[batch2["digest"]] = batch2
    state2 = generation(state1, [batch2], contract, evidence_store=store)
    write_new(root / "generation-2.json", state2)
    # All policies are frozen before any heldout result or answer is evaluated.
    decisions = {}
    for index, state in enumerate((state0, state1, state2)):
        loaded = read_json(root / f"generation-{index}.json")
        validate_generation(loaded, contract, evidence_store=store,
                            parent=(state0, state1)[index-1] if index else None)
        bundle, output = root / f"route-input-{index}.json", root / f"decisions-{index}.json"
        inherited_store = {key: store[key] for key in loaded["batch_digests"]}
        write_new(bundle, {"contract": contract.public(), "state": loaded, "evidence": inherited_store, "tasks": tasks})
        runtime._child("route", bundle, output, root)
        decisions[index] = read_json(output)
        require(decisions[index]["loaded_state_digest"] == loaded["digest"], "reader loaded wrong generation")
    memory = [{"task": t, "answer": {**oracle1, **oracle2}[t["task_id"]]} for t in train1+train2]
    scheduled = [(arm, task) for task in tasks for arm in ("reset", "journal", "syn1", "syn2")]
    random.Random(26).shuffle(scheduled)
    rows, heldout_receipts = [], []
    for arm, task in scheduled:
        strategy = (contract.default_strategy if arm in {"reset", "journal"}
                    else decisions[int(arm[-1])]["decisions"][task["task_id"]])
        relevant = [r for r in memory if r["task"]["domain"] == task["domain"]] if arm == "journal" else []
        result = runtime.execute(task, strategy, relevant)
        rows.append({"arm": arm, "task_id": task["task_id"], "strategy": strategy,
                     **{k: result[k] for k in ("answer", "tokens_used", "error", "request_digest")}})
        heldout_receipts.append(result)
    write_new(root / "frozen-heldout-attempts.json", sealed({"attempts": rows}))
    # Read the evaluator's sealed file only after committing ALL heldout attempts.
    heldout_oracle = read_json(root / "heldout-oracle.json")["answers"]
    require(digest(heldout_oracle) == preregistration["oracle_digest"], "heldout oracle changed")
    for result in heldout_receipts:
        runtime.verify(result, heldout_oracle[result["task_id"]])
    require(read_json(root / "generation-2.json") == state2, "evaluation mutated learned state")
    summary = summarize(rows, heldout_oracle, tasks)
    summary.update({"schema": "syn-recursive-results-v1", "preregistration_digest": preregistration["digest"],
                    "model": identity, "physical_model_calls": runtime.calls,
                    "physical_tokens": runtime.tokens, "physical_executions": len(runtime.executions),
                    "generation_policies": [s["policy"] for s in (state0, state1, state2)],
                    "generation_digests": [s["digest"] for s in (state0, state1, state2)],
                    "risk_state": asdict(runtime.risk.state()),
                    "glyph_events": runtime.graph.ledger.verify().event_count,
                    "shared_execution": preregistration["shared_execution"],
                    "interpretation": "Executed synthetic task benchmark with real local Mistral and fixed exact tools. Learned routing only; no model-weight update, new skill code, AGI claim or general scientific transfer. Single model/seed; intervals are descriptive; exploratory p-value is unadjusted."})
    write_new(root / "results.json", sealed(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "worker", "route"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--model", default="syn-mistral-import:latest")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--train-per-domain", type=int, default=3)
    parser.add_argument("--test-per-domain", type=int, default=4)
    parser.add_argument("--max-calls", type=int, default=48)
    parser.add_argument("--max-tokens", type=int, default=100000)
    parser.add_argument("--deadline-seconds", type=int, default=3600)
    args = parser.parse_args()
    if args.action == "worker":
        require(args.request is not None, "worker needs request")
        execute_worker(read_json(args.request), args.out)
    elif args.action == "route":
        require(args.request is not None, "router needs request")
        route_worker(read_json(args.request), args.out)
    else:
        print(canonical(run_study(args)), flush=True)


if __name__ == "__main__":
    main()
