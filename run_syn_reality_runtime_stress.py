import sys, os, socket, subprocess, time, json, shutil, select
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, "/mnt/data")

from synergesis_aegis import (
    ActionSecurityProfile, AegisGuard, AegisSecurityGraph,
    CapabilityStore, IdentityRegistry, IdentitySigner,
)
from synergesis_agent_loop_v2 import (
    ActionProposal, ActionResult, AgentObservation, Goal, Hypothesis,
    LearningSignal, PermissionPolicy, ReasoningOutput, StrategyLedger,
)
from synergesis_agent_loop_v4 import (
    ActionTypeResourceResolver, NoCapabilities,
    TrustedSourceObservationClassifier,
)
from synergesis_agent_loop_v5 import SynAgentLoopV5
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_life import PersistentMemory, SynKernel
from synergesis_reality import (
    RealityAssertion, RealityAuditService, RealityProbeBinding,
    RealityProfile, RealityVerifier,
)
from synergesis_reality_runtime import (
    ProcessMarkerPolicy, ProcessMarkerProbe,
    LoopbackTcpPolicy, LoopbackTcpProbe,
)

ROOT = Path("/mnt/data/syn_reality_runtime_stress")
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)

class DynamicReasoner:
    def __init__(self):
        self.case = None
    def set_case(self, case):
        self.case = case
    def reason(self, context):
        c = self.case
        if c["action_type"] == "process.spawn":
            params = {"marker": c["marker"], "mode": c["mode"]}
        else:
            params = {
                "host": c["host"],
                "port": c["port"],
                "mode": c["mode"],
            }
        return ReasoningOutput(
            (Hypothesis.create("Perform bounded runtime stress action.", rationale="stress"),),
            ActionProposal.create(
                c["action_type"],
                params,
                rationale="runtime truth stress",
                expected_outcome="independent runtime observer confirms effect",
                strategy_key=f"{c['action_type']}:{c['mode']}",
            ),
        )
    def evaluate(self, context, proposal, result):
        return LearningSignal(0.9, "Model evaluator accepted effective result.")

children = []

def cleanup_children():
    for proc in list(children):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=0.4)
        children.remove(proc)

def spawn_marked(marker):
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)", marker],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    children.append(proc)
    time.sleep(0.015)
    return proc

SERVER_CODE = r"""
import socket, sys, time
host=sys.argv[1]; port=int(sys.argv[2])
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((host,port)); s.listen(8)
print('READY', flush=True)
s.settimeout(0.2)
deadline=time.time()+30
while time.time()<deadline:
    try:
        c,a=s.accept(); c.close()
    except socket.timeout:
        pass
s.close()
"""

def spawn_listener(host, port):
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c", SERVER_CODE, host, str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    children.append(proc)
    ready, _, _ = select.select([proc.stdout], [], [], 1.0)
    if not ready or proc.stdout.readline().strip() != "READY":
        raise RuntimeError("listener failed to become ready")
    return proc

def process_executor(params):
    mode = params["mode"]
    marker = params["marker"]
    if mode == "honest_success":
        spawn_marked(marker)
        return ActionResult("process.spawn", True, {"claimed": "spawned"})
    if mode == "false_success":
        return ActionResult("process.spawn", True, {"claimed": "spawned"})
    if mode == "wrong_effect":
        spawn_marked(marker + "-WRONG")
        return ActionResult("process.spawn", True, {"claimed": "spawned"})
    if mode == "false_failure_side_effect":
        spawn_marked(marker)
        return ActionResult("process.spawn", False, {"claimed": "failed"}, "timeout")
    if mode == "honest_failure":
        return ActionResult("process.spawn", False, {"claimed": "failed"}, "spawn_error")
    raise AssertionError(mode)

def tcp_executor(params):
    mode = params["mode"]
    host = params["host"]
    port = params["port"]
    if mode == "honest_success":
        spawn_listener(host, port)
        return ActionResult("tcp.listen", True, {"claimed": "listening"})
    if mode == "false_success":
        return ActionResult("tcp.listen", True, {"claimed": "listening"})
    if mode == "wrong_effect":
        wrong = free_port()
        spawn_listener(host, wrong)
        return ActionResult("tcp.listen", True, {"claimed": "listening", "actual_hidden_port": wrong})
    if mode == "false_failure_side_effect":
        spawn_listener(host, port)
        return ActionResult("tcp.listen", False, {"claimed": "failed"}, "timeout")
    if mode == "honest_failure":
        return ActionResult("tcp.listen", False, {"claimed": "failed"}, "bind_error")
    raise AssertionError(mode)

def free_port():
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        if 20000 <= port <= 60000:
            return port

graph = GlyphAuditGraph(GlyphLedger(ROOT / "glyphs.jsonl"))
core = GlyphAuditedCognitiveCore(ROOT / "semantic.jsonl", graph=graph, actor="ZÆL-0")
aura = GlyphAuditedAura(core, graph=graph)
kernel = SynKernel("ZÆL-0", PersistentMemory(ROOT / "episodic.jsonl"))

ids = IdentityRegistry(ROOT / "identities.jsonl")
signer = IdentitySigner("ZÆL-0")
ids.register("ZÆL-0", signer.public_key)

security = AegisSecurityGraph(graph)
allowed = frozenset({"process.spawn", "tcp.listen"})
aegis = AegisGuard(
    graph=graph,
    identity_registry=ids,
    capability_store=CapabilityStore(ROOT / "caps.jsonl"),
    trusted_capability_issuers=frozenset(),
    allowed_actions=allowed,
    profiles=(
        ActionSecurityProfile("process.spawn", False, frozenset()),
        ActionSecurityProfile("tcp.listen", False, frozenset()),
    ),
    security_graph=security,
)

process_probe = ProcessMarkerProbe(
    observer_id="os:process",
    policy=ProcessMarkerPolicy(
        marker_parameter="marker",
        allowed_executable_basenames=frozenset({Path(sys.executable).name}),
        max_processes_scanned=4096,
    ),
)
tcp_probe = LoopbackTcpProbe(
    observer_id="os:tcp",
    policy=LoopbackTcpPolicy(
        host_parameter="host",
        port_parameter="port",
        allowed_hosts=frozenset({"127.0.0.1"}),
        min_port=20000,
        max_port=60000,
        timeout_seconds=0.08,
    ),
)

reality = RealityVerifier(
    graph=graph,
    security_graph=security,
    probe_bindings=(
        RealityProbeBinding("os:process", "runtime_attested", process_probe),
        RealityProbeBinding("os:tcp", "runtime_attested", tcp_probe),
    ),
    profiles=(
        RealityProfile(
            "process.spawn",
            ("os:process",),
            (RealityAssertion("os:process", "marker_found", "truthy"),),
        ),
        RealityProfile(
            "tcp.listen",
            ("os:tcp",),
            (RealityAssertion("os:tcp", "connected", "truthy"),),
        ),
    ),
)

reasoner = DynamicReasoner()
loop = SynAgentLoopV5(
    kernel=kernel,
    cognitive_core=core,
    aura=aura,
    policy=PermissionPolicy(allowed),
    reasoner=reasoner,
    executors={
        "process.spawn": process_executor,
        "tcp.listen": tcp_executor,
    },
    strategy_ledger=StrategyLedger(ROOT / "strategy.jsonl"),
    context_selector=LexicalContextSelector(
        budget=ContextBudget(max_facts=4, max_evidence=4),
        k1=1.5, b=0.75,
    ),
    graph=graph,
    aegis_guard=aegis,
    observation_classifier=TrustedSourceObservationClassifier(
        trusted_sources=frozenset({"user"})
    ),
    capability_resolver=NoCapabilities(),
    resource_resolver=ActionTypeResourceResolver(),
    reality_verifier=reality,
)

modes = [
    "honest_success",
    "false_success",
    "wrong_effect",
    "false_failure_side_effect",
    "honest_failure",
]
cases = []
for round_index in range(16):
    for mode in modes:
        cases.append({
            "action_type": "process.spawn",
            "mode": mode,
            "marker": f"syn-runtime-{round_index:02d}-{mode}",
        })
        cases.append({
            "action_type": "tcp.listen",
            "mode": mode,
            "host": "127.0.0.1",
            "port": None,
        })

rows = []
t0 = time.perf_counter()
try:
    for index, case in enumerate(cases, start=1):
        if case["action_type"] == "tcp.listen":
            case = dict(case)
            case["port"] = free_port()
        reasoner.set_case(case)
        cycle = loop.run_cycle(
            goal=Goal.create(f"Runtime stress {index}"),
            observation=AgentObservation(
                "stress_case",
                {"index": index, "action_type": case["action_type"], "mode": case["mode"]},
                "user",
            ),
        )
        reality_info = cycle.action_result.output["reality"]
        raw = cycle.action_result.output["executor_claim"]

        expected_effect = case["mode"] in {"honest_success", "false_failure_side_effect"}
        expected_claim_match = case["mode"] in {"honest_success", "honest_failure"}

        rows.append({
            "index": index,
            "action_type": case["action_type"],
            "mode": case["mode"],
            "expected_effect": expected_effect,
            "effective_success": cycle.action_result.success,
            "raw_executor_success": raw["success"],
            "reality_status": reality_info["status"],
            "claim_match": reality_info["executor_claim_matches_reality"],
            "expected_claim_match": expected_claim_match,
            "learning_score": cycle.learning.score,
        })
        cleanup_children()
finally:
    cleanup_children()

elapsed = time.perf_counter() - t0
df = pd.DataFrame(rows)
df["effect_correct"] = df.expected_effect == df.effective_success
df["claim_match_correct"] = df.expected_claim_match == df.claim_match
df.to_csv(ROOT / "runtime_stress_results.csv", index=False)

summary = (
    df.groupby(["action_type", "mode"])
      .agg(
          cases=("index", "count"),
          effect_accuracy=("effect_correct", "mean"),
          claim_accuracy=("claim_match_correct", "mean"),
          effective_success_rate=("effective_success", "mean"),
          raw_success_rate=("raw_executor_success", "mean"),
          mean_learning_score=("learning_score", "mean"),
      )
      .reset_index()
)
summary.to_csv(ROOT / "runtime_stress_summary.csv", index=False)

audit = RealityAuditService(graph)
reports = {
    action: audit.reliability(action)
    for action in ("process.spawn", "tcp.listen")
}
checkpoint = graph.ledger.verify()
report = {
    "actions": len(df),
    "elapsed_seconds": elapsed,
    "overall_effect_accuracy": float(df.effect_correct.mean()),
    "overall_claim_classification_accuracy": float(df.claim_match_correct.mean()),
    "mismatch_learning_zero_rate": float(
        (df.loc[df.claim_match == False, "learning_score"] == 0.0).mean()
    ),
    "action_reports": {
        action: {
            "assessments": r.assessments,
            "verified": r.verified,
            "matches": r.executor_claim_matches,
            "mismatches": r.executor_claim_mismatches,
            "match_rate_on_verified": r.match_rate_on_verified,
        }
        for action, r in reports.items()
    },
    "glyph_events": checkpoint.event_count,
    "merkle_root": checkpoint.merkle_root,
}
(ROOT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

plt.figure(figsize=(10,5))
for action in ("process.spawn", "tcp.listen"):
    sub = df[df.action_type == action]
    cumulative = sub.effect_correct.expanding().mean()
    plt.plot(sub["index"], cumulative, label=action)
plt.xlabel("Global action index")
plt.ylabel("Cumulative effect-classification accuracy")
plt.ylim(0.95, 1.005)
plt.title("SYN-REALITY runtime truth across process and TCP effects")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "runtime_accuracy.png", dpi=160)
plt.close()

print("=== SYN-REALITY PROCESS + NETWORK STRESS ===")
print(f"Actions: {len(df)} | elapsed: {elapsed:.3f}s")
print(summary.to_string(index=False))
print("\nOverall effect accuracy:", f"{report['overall_effect_accuracy']:.3f}")
print("Overall claim accuracy:", f"{report['overall_claim_classification_accuracy']:.3f}")
print("Mismatch learning zero rate:", f"{report['mismatch_learning_zero_rate']:.3f}")
for action, r in reports.items():
    print(f"{action} executor match rate:", f"{r.match_rate_on_verified:.3f}")
print("Glyph events:", checkpoint.event_count)
print("Merkle root:", checkpoint.merkle_root)
