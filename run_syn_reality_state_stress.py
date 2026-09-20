import sys, json, shutil, sqlite3, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
from urllib.request import Request, urlopen
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
from synergesis_reality_state import (
    LoopbackHttpJsonPolicy, LoopbackHttpJsonProbe,
    SQLiteProbePolicy, SQLiteStateProbe,
)

ROOT = Path("/mnt/data/syn_reality_state_stress")
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)
DBROOT = ROOT / "db"
DBROOT.mkdir()
DBPATH = DBROOT / "state.sqlite"

conn = sqlite3.connect(DBPATH)
conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
conn.commit()
conn.close()


class StateHandler(BaseHTTPRequestHandler):
    state = {}

    def do_GET(self):
        if not self.path.startswith("/state/"):
            self.send_response(404); self.end_headers(); return
        key = unquote(self.path[len("/state/"):])
        if key not in self.state:
            self.send_response(404); self.end_headers(); return
        body = json.dumps({"value": self.state[key]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self.path.startswith("/state/"):
            self.send_response(404); self.end_headers(); return
        key = unquote(self.path[len("/state/"):])
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self.state[key] = payload.get("value")
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        return


server = ThreadingHTTPServer(("127.0.0.1", 0), StateHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
API_PORT = server.server_address[1]


class DynamicReasoner:
    def __init__(self):
        self.case = None
    def set_case(self, case):
        self.case = case
    def reason(self, context):
        c = self.case
        return ReasoningOutput(
            (Hypothesis.create("Persist requested state.", rationale="stress"),),
            ActionProposal.create(
                c["action_type"],
                {"key": c["key"], "value": c["value"], "mode": c["mode"]},
                rationale="persistent-state reality stress",
                expected_outcome="independent read path sees requested value",
                strategy_key=f"{c['action_type']}:{c['mode']}",
            ),
        )
    def evaluate(self, context, proposal, result):
        return LearningSignal(0.9, "Model evaluator accepted effective state.")


def db_write(key, value):
    conn = sqlite3.connect(DBPATH)
    try:
        conn.execute(
            "INSERT INTO kv(k,v) VALUES (?,?) "
            "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def api_write(key, value):
    body = json.dumps({"value": value}).encode()
    req = Request(
        f"http://127.0.0.1:{API_PORT}/state/{key}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=1.0) as response:
        if response.status != 204:
            raise RuntimeError("unexpected API status")


def db_executor(params):
    mode = params["mode"]; key = params["key"]; value = params["value"]
    if mode == "honest_success":
        db_write(key, value)
        return ActionResult("db.put", True, {"claimed": "stored"})
    if mode == "false_success":
        return ActionResult("db.put", True, {"claimed": "stored"})
    if mode == "wrong_effect":
        db_write(key, value + "-WRONG")
        return ActionResult("db.put", True, {"claimed": "stored"})
    if mode == "false_failure_side_effect":
        db_write(key, value)
        return ActionResult("db.put", False, {"claimed": "failed"}, "timeout")
    if mode == "honest_failure":
        return ActionResult("db.put", False, {"claimed": "failed"}, "db_error")
    raise AssertionError(mode)


def api_executor(params):
    mode = params["mode"]; key = params["key"]; value = params["value"]
    if mode == "honest_success":
        api_write(key, value)
        return ActionResult("api.set", True, {"claimed": "stored"})
    if mode == "false_success":
        return ActionResult("api.set", True, {"claimed": "stored"})
    if mode == "wrong_effect":
        api_write(key, value + "-WRONG")
        return ActionResult("api.set", True, {"claimed": "stored"})
    if mode == "false_failure_side_effect":
        api_write(key, value)
        return ActionResult("api.set", False, {"claimed": "failed"}, "timeout")
    if mode == "honest_failure":
        return ActionResult("api.set", False, {"claimed": "failed"}, "api_error")
    raise AssertionError(mode)


graph = GlyphAuditGraph(GlyphLedger(ROOT / "glyphs.jsonl"))
core = GlyphAuditedCognitiveCore(ROOT / "semantic.jsonl", graph=graph, actor="ZÆL-0")
aura = GlyphAuditedAura(core, graph=graph)
kernel = SynKernel("ZÆL-0", PersistentMemory(ROOT / "episodic.jsonl"))

ids = IdentityRegistry(ROOT / "identities.jsonl")
signer = IdentitySigner("ZÆL-0")
ids.register("ZÆL-0", signer.public_key)

security = AegisSecurityGraph(graph)
allowed = frozenset({"db.put", "api.set"})
aegis = AegisGuard(
    graph=graph,
    identity_registry=ids,
    capability_store=CapabilityStore(ROOT / "caps.jsonl"),
    trusted_capability_issuers=frozenset(),
    allowed_actions=allowed,
    profiles=(
        ActionSecurityProfile("db.put", False, frozenset()),
        ActionSecurityProfile("api.set", False, frozenset()),
    ),
    security_graph=security,
)

sqlite_probe = SQLiteStateProbe(
    observer_id="db:sqlite",
    policy=SQLiteProbePolicy(
        database_path=DBPATH,
        allowed_root=DBROOT,
        select_sql="SELECT v AS value FROM kv WHERE k = ?",
        bind_parameter_keys=("key",),
        result_column="value",
    ),
)
http_probe = LoopbackHttpJsonProbe(
    observer_id="api:http",
    policy=LoopbackHttpJsonPolicy(
        host="127.0.0.1",
        port=API_PORT,
        path_prefix="/state/",
        path_parameter="key",
        json_field="value",
        timeout_seconds=0.3,
    ),
)

reality = RealityVerifier(
    graph=graph,
    security_graph=security,
    probe_bindings=(
        RealityProbeBinding("db:sqlite", "runtime_attested", sqlite_probe),
        RealityProbeBinding("api:http", "runtime_attested", http_probe),
    ),
    profiles=(
        RealityProfile(
            "db.put",
            ("db:sqlite",),
            (
                RealityAssertion("db:sqlite", "found", "truthy"),
                RealityAssertion(
                    "db:sqlite", "value", "eq_parameter", parameter_key="value"
                ),
            ),
        ),
        RealityProfile(
            "api.set",
            ("api:http",),
            (
                RealityAssertion("api:http", "status_code", "eq", 200),
                RealityAssertion(
                    "api:http", "json_value", "eq_parameter", parameter_key="value"
                ),
            ),
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
    executors={"db.put": db_executor, "api.set": api_executor},
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
for round_index in range(12):
    for mode in modes:
        for action_type in ("db.put", "api.set"):
            cases.append({
                "action_type": action_type,
                "mode": mode,
                "key": f"{action_type}-{round_index:02d}-{mode}",
                "value": f"value-{round_index:02d}-{mode}",
            })

rows = []
t0 = time.perf_counter()
try:
    for index, case in enumerate(cases, start=1):
        reasoner.set_case(case)
        cycle = loop.run_cycle(
            goal=Goal.create(f"Persistent state stress {index}"),
            observation=AgentObservation(
                "stress_case",
                {"index": index, "action_type": case["action_type"], "mode": case["mode"]},
                "user",
            ),
        )
        reality_info = cycle.action_result.output["reality"]
        raw = cycle.action_result.output["executor_claim"]
        expected_effect = case["mode"] in {
            "honest_success", "false_failure_side_effect"
        }
        expected_claim_match = case["mode"] in {
            "honest_success", "honest_failure"
        }
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
finally:
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=2)

elapsed = time.perf_counter() - t0
df = pd.DataFrame(rows)
df["effect_correct"] = df.expected_effect == df.effective_success
df["claim_match_correct"] = df.expected_claim_match == df.claim_match
df.to_csv(ROOT / "state_stress_results.csv", index=False)

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
summary.to_csv(ROOT / "state_stress_summary.csv", index=False)

audit = RealityAuditService(graph)
reports = {
    action: audit.reliability(action)
    for action in ("db.put", "api.set")
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
for action in ("db.put", "api.set"):
    sub = df[df.action_type == action]
    plt.plot(
        sub["index"],
        sub.effect_correct.expanding().mean(),
        label=action,
    )
plt.xlabel("Global action index")
plt.ylabel("Cumulative state-effect accuracy")
plt.ylim(0.95, 1.005)
plt.title("SYN-REALITY persistent/application state verification")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "state_accuracy.png", dpi=160)
plt.close()

print("=== SYN-REALITY DB + API STATE STRESS ===")
print(f"Actions: {len(df)} | elapsed: {elapsed:.3f}s")
print(summary.to_string(index=False))
print("\nOverall effect accuracy:", f"{report['overall_effect_accuracy']:.3f}")
print("Overall claim accuracy:", f"{report['overall_claim_classification_accuracy']:.3f}")
print("Mismatch learning zero rate:", f"{report['mismatch_learning_zero_rate']:.3f}")
for action, r in reports.items():
    print(f"{action} executor match rate:", f"{r.match_rate_on_verified:.3f}")
print("Glyph events:", checkpoint.event_count)
print("Merkle root:", checkpoint.merkle_root)
