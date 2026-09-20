import sys, shutil, time, json
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
    FileStateProbe, RealityAssertion, RealityAuditService,
    RealityProbeBinding, RealityProfile, RealityVerifier,
)

ROOT = Path("/mnt/data/syn_reality_filesystem_stress")
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)
RUNTIME = ROOT / "runtime"

class DynamicReasoner:
    def __init__(self):
        self.current = None

    def set_case(self, case):
        self.current = case

    def reason(self, context):
        c = self.current
        return ReasoningOutput(
            (Hypothesis.create("Execute filesystem test case.", rationale="stress"),),
            ActionProposal.create(
                "file.write",
                {
                    "path": c["path"],
                    "content": c["content"],
                    "mode": c["mode"],
                },
                rationale="filesystem reality stress case",
                expected_outcome="requested file content exists",
                strategy_key=f"file-write:{c['mode']}",
            ),
        )

    def evaluate(self, context, proposal, result):
        # Intentionally trusts whatever effective result reaches it.
        return LearningSignal(0.9, "Model-side evaluator score before reality guard.")


def executor(params):
    target = RUNTIME / params["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = params["mode"]

    if mode == "honest_success":
        target.write_text(params["content"], encoding="utf-8")
        return ActionResult("file.write", True, {"claimed": "written"})

    if mode == "false_success":
        return ActionResult("file.write", True, {"claimed": "written"})

    if mode == "wrong_content":
        target.write_text("CORRUPTED", encoding="utf-8")
        return ActionResult("file.write", True, {"claimed": "written"})

    if mode == "false_failure_side_effect":
        target.write_text(params["content"], encoding="utf-8")
        return ActionResult(
            "file.write", False, {"claimed": "failed"}, "timeout"
        )

    if mode == "honest_failure":
        return ActionResult(
            "file.write", False, {"claimed": "failed"}, "io_error"
        )

    raise AssertionError(mode)


graph = GlyphAuditGraph(GlyphLedger(ROOT / "glyphs.jsonl"))
core = GlyphAuditedCognitiveCore(
    ROOT / "semantic.jsonl", graph=graph, actor="ZÆL-0"
)
aura = GlyphAuditedAura(core, graph=graph)
kernel = SynKernel(
    "ZÆL-0", PersistentMemory(ROOT / "episodic.jsonl")
)

ids = IdentityRegistry(ROOT / "identities.jsonl")
signer = IdentitySigner("ZÆL-0")
ids.register("ZÆL-0", signer.public_key)

security = AegisSecurityGraph(graph)
aegis = AegisGuard(
    graph=graph,
    identity_registry=ids,
    capability_store=CapabilityStore(ROOT / "caps.jsonl"),
    trusted_capability_issuers=frozenset(),
    allowed_actions=frozenset({"file.write"}),
    profiles=(
        ActionSecurityProfile("file.write", False, frozenset()),
    ),
    security_graph=security,
)

probe = FileStateProbe(
    observer_id="os:file",
    allowed_root=RUNTIME,
    path_parameter="path",
    max_hash_bytes=1024 * 1024,
)
reality = RealityVerifier(
    graph=graph,
    security_graph=security,
    probe_bindings=(
        RealityProbeBinding(
            "os:file", "runtime_attested", probe
        ),
    ),
    profiles=(
        RealityProfile(
            "file.write",
            ("os:file",),
            (
                RealityAssertion("os:file", "exists", "eq", True),
                RealityAssertion(
                    "os:file",
                    "sha256",
                    "sha256_parameter_utf8",
                    parameter_key="content",
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
    policy=PermissionPolicy(frozenset({"file.write"})),
    reasoner=reasoner,
    executors={"file.write": executor},
    strategy_ledger=StrategyLedger(ROOT / "strategy.jsonl"),
    context_selector=LexicalContextSelector(
        budget=ContextBudget(max_facts=4, max_evidence=4),
        k1=1.5,
        b=0.75,
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
    "wrong_content",
    "false_failure_side_effect",
    "honest_failure",
]
cases = []
for round_index in range(30):
    for mode in modes:
        cases.append({
            "mode": mode,
            "path": f"{mode}/{round_index:02d}.txt",
            "content": f"verified-content-{mode}-{round_index:02d}",
        })

rows = []
t0 = time.perf_counter()
for index, case in enumerate(cases, start=1):
    reasoner.set_case(case)
    cycle = loop.run_cycle(
        goal=Goal.create(f"Filesystem reality test {index}"),
        observation=AgentObservation(
            "test_case",
            {"index": index, "mode": case["mode"]},
            "user",
        ),
    )
    reality_info = cycle.action_result.output["reality"]
    executor_claim = cycle.action_result.output["executor_claim"]

    expected_effect = case["mode"] in {
        "honest_success", "false_failure_side_effect"
    }
    expected_claim_match = case["mode"] in {
        "honest_success", "honest_failure"
    }
    rows.append({
        "index": index,
        "mode": case["mode"],
        "expected_effect": expected_effect,
        "effective_success": cycle.action_result.success,
        "raw_executor_success": executor_claim["success"],
        "reality_status": reality_info["status"],
        "claim_match": reality_info["executor_claim_matches_reality"],
        "expected_claim_match": expected_claim_match,
        "learning_score": cycle.learning.score,
    })

elapsed = time.perf_counter() - t0
df = pd.DataFrame(rows)
df["effect_correct"] = df.expected_effect == df.effective_success
df["claim_match_correct"] = df.expected_claim_match == df.claim_match
df.to_csv(ROOT / "stress_results.csv", index=False)

summary = (
    df.groupby("mode")
      .agg(
          cases=("index","count"),
          effective_success_rate=("effective_success","mean"),
          raw_success_rate=("raw_executor_success","mean"),
          effect_accuracy=("effect_correct","mean"),
          claim_classification_accuracy=("claim_match_correct","mean"),
          mean_learning_score=("learning_score","mean"),
      )
      .reset_index()
)
summary.to_csv(ROOT / "mode_summary.csv", index=False)

audit = RealityAuditService(graph).reliability("file.write")
checkpoint = graph.ledger.verify()
report = {
    "actions": len(df),
    "elapsed_seconds": elapsed,
    "effect_accuracy": float(df.effect_correct.mean()),
    "claim_match_classification_accuracy": float(df.claim_match_correct.mean()),
    "executor_reliability": {
        "assessments": audit.assessments,
        "verified": audit.verified,
        "matches": audit.executor_claim_matches,
        "mismatches": audit.executor_claim_mismatches,
        "match_rate_on_verified": audit.match_rate_on_verified,
    },
    "mismatch_learning_zero_rate": float(
        (df.loc[df.claim_match == False, "learning_score"] == 0.0).mean()
    ),
    "glyph_events": checkpoint.event_count,
    "merkle_root": checkpoint.merkle_root,
}
(ROOT / "report.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)

plt.figure(figsize=(10,5))
for mode in modes:
    sub = df[df["mode"] == mode]
    plt.scatter(
        sub["index"],
        sub["effective_success"].astype(int),
        label=mode,
        s=18,
    )
plt.xlabel("Action index")
plt.ylabel("Reality-effective success (0/1)")
plt.yticks([0,1])
plt.title("SYN-REALITY: 150 real filesystem actions")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "effective_success.png", dpi=160)
plt.close()

print("=== SYN-REALITY FILESYSTEM STRESS ===")
print(f"Actions: {len(df)} | elapsed: {elapsed:.3f}s")
print(summary.to_string(index=False))
print("\nOverall effect accuracy:", f"{report['effect_accuracy']:.3f}")
print("Claim classification accuracy:", f"{report['claim_match_classification_accuracy']:.3f}")
print("Executor observed match rate:", f"{audit.match_rate_on_verified:.3f}")
print("Mismatch learning zero rate:", f"{report['mismatch_learning_zero_rate']:.3f}")
print("Glyph events:", checkpoint.event_count)
print("Merkle root:", checkpoint.merkle_root)
