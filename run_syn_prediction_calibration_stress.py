import sys, json, shutil, time
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, "/mnt/data")

from synergesis_aegis import (
    ActionSecurityProfile,
    AegisGuard,
    AegisSecurityGraph,
    CapabilityStore,
    IdentityRegistry,
    IdentitySigner,
)
from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentObservation,
    Goal,
    Hypothesis,
    LearningSignal,
    PermissionPolicy,
    ReasoningOutput,
    StrategyLedger,
)
from synergesis_agent_loop_v4 import (
    ActionTypeResourceResolver,
    NoCapabilities,
    TrustedSourceObservationClassifier,
)
from synergesis_agent_loop_v5 import SynAgentLoopV5
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_life import PersistentMemory, SynKernel
from synergesis_prediction import (
    EmpiricalPredictionProvider,
    PredictionAuditService,
    PredictionEngine,
    PredictionLedger,
)
from synergesis_prediction_curiosity import (
    PredictionCuriosityMonitor,
    PredictionCuriosityPolicy,
)
from synergesis_roam_attention import AttentionWeights, ResearchAgenda
from synergesis_reality import (
    FileStateProbe,
    RealityAssertion,
    RealityProbeBinding,
    RealityProfile,
    RealityVerifier,
)

ROOT = Path("/mnt/data/syn_prediction_calibration_stress")
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)
RUNTIME = ROOT / "runtime"


class DynamicReasoner:
    def __init__(self):
        self.index = 0

    def set_index(self, index):
        self.index = index

    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "Attempt the same file-write strategy.",
                    rationale="prediction calibration stress test",
                ),
            ),
            ActionProposal.create(
                "file.write",
                {
                    "path": f"cycle-{self.index:03d}.txt",
                    "content": f"verified-{self.index:03d}",
                },
                rationale="repeat a stable strategy in a changing environment",
                expected_outcome="requested file exists with requested bytes",
                strategy_key="adaptive-file-write",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            0.9 if result.success else 0.1,
            "Outcome learning remains separate from prediction calibration.",
        )


class Environment:
    def __init__(self):
        self.should_succeed = True

    def executor(self, params):
        target = RUNTIME / params["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if self.should_succeed:
            target.write_text(params["content"], encoding="utf-8")
            return ActionResult(
                "file.write",
                True,
                {"path": str(target)},
            )
        return ActionResult(
            "file.write",
            False,
            {"path": str(target)},
            "environment_rejected_write",
        )


def build_outcomes():
    values = []
    # Regime A: 90% success.
    for i in range(40):
        values.append((1, (i % 10) != 9))
    # Regime B: 20% success.
    for i in range(40):
        values.append((2, (i % 5) == 0))
    # Regime C: 75% success.
    for i in range(40):
        values.append((3, (i % 4) != 3))
    return values


graph = GlyphAuditGraph(GlyphLedger(ROOT / "glyphs.jsonl"))
core = GlyphAuditedCognitiveCore(
    ROOT / "semantic.jsonl",
    graph=graph,
    actor="ZÆL-0",
)
aura = GlyphAuditedAura(core, graph=graph)
kernel = SynKernel(
    "ZÆL-0",
    PersistentMemory(ROOT / "episodic.jsonl"),
)

identities = IdentityRegistry(ROOT / "identities.jsonl")
signer = IdentitySigner("ZÆL-0")
identities.register("ZÆL-0", signer.public_key)

security = AegisSecurityGraph(graph)
aegis = AegisGuard(
    graph=graph,
    identity_registry=identities,
    capability_store=CapabilityStore(ROOT / "caps.jsonl"),
    trusted_capability_issuers=frozenset(),
    allowed_actions=frozenset({"file.write"}),
    profiles=(
        ActionSecurityProfile(
            "file.write",
            requires_capability=False,
            forbidden_taints=frozenset(),
        ),
    ),
    security_graph=security,
)

file_probe = FileStateProbe(
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
            "os:file",
            "runtime_attested",
            file_probe,
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

prediction_ledger = PredictionLedger(ROOT / "prediction_ledger.jsonl")
prediction_engine = PredictionEngine(
    graph=graph,
    provider=EmpiricalPredictionProvider(
        ledger=prediction_ledger,
        prior_alpha=1.0,
        prior_beta=1.0,
        half_life_events=4.0,
    ),
    ledger=prediction_ledger,
)
prediction_audit = PredictionAuditService(
    graph=graph,
    ledger=prediction_ledger,
)

agenda = ResearchAgenda(
    ROOT / "research_agenda.jsonl",
    graph=graph,
    weights=AttentionWeights(
        uncertainty=1.0,
        expected_impact=1.0,
        staleness=1.0,
        novelty_gap=1.0,
    ),
    actor="SYN-ROAM",
)
curiosity = PredictionCuriosityMonitor(
    graph=graph,
    prediction_ledger=prediction_ledger,
    agenda=agenda,
    policy=PredictionCuriosityPolicy(
        min_observations=10,
        rolling_window=8,
        minimum_absolute_error=0.8,
        minimum_surprise_bits=2.2,
        rolling_brier_threshold=0.30,
        cooldown_records=10,
        surprise_scale_bits=4.0,
        default_domain="systems",
        default_expected_impact=0.8,
        domain_by_action={"file.write": "systems"},
        expected_impact_by_action={"file.write": 0.8},
    ),
)
prediction_engine.add_settlement_sink(curiosity)

reasoner = DynamicReasoner()
environment = Environment()

loop = SynAgentLoopV5(
    kernel=kernel,
    cognitive_core=core,
    aura=aura,
    policy=PermissionPolicy(frozenset({"file.write"})),
    reasoner=reasoner,
    executors={"file.write": environment.executor},
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
    prediction_engine=prediction_engine,
)

rows = []
outcomes = build_outcomes()
t0 = time.perf_counter()

for cycle_index, (regime, should_succeed) in enumerate(outcomes, start=1):
    reasoner.set_index(cycle_index)
    environment.should_succeed = should_succeed

    cycle = loop.run_cycle(
        goal=Goal.create("Calibrate file-write prediction"),
        observation=AgentObservation(
            "calibration_cycle",
            {"cycle": cycle_index},
            "user",
        ),
    )

    record = prediction_ledger.records()[-1]
    trigger_now = (
        curiosity.last_trigger is not None
        and curiosity.last_trigger.prediction_record_sequence == record.sequence
    )
    rows.append({
        "cycle": cycle_index,
        "regime": regime,
        "observed_success": int(record.observed_effect),
        "predicted_probability": record.probability_effect_success,
        "brier_score": record.brier_score,
        "absolute_error": record.absolute_error,
        "surprise_bits": record.surprise_bits,
        "effective_success": int(cycle.action_result.success),
        "learning_score": cycle.learning.score,
        "curiosity_triggered": trigger_now,
        "curiosity_need_id": (
            curiosity.last_trigger.need_id if trigger_now else None
        ),
    })

elapsed = time.perf_counter() - t0
df = pd.DataFrame(rows)
df["baseline_050_brier"] = (
    0.5 - df["observed_success"]
) ** 2
df.to_csv(ROOT / "calibration_results.csv", index=False)

summary = (
    df.groupby("regime")
    .agg(
        cycles=("cycle", "count"),
        empirical_success_rate=("observed_success", "mean"),
        mean_predicted_probability=("predicted_probability", "mean"),
        mean_brier=("brier_score", "mean"),
        baseline_050_brier=("baseline_050_brier", "mean"),
        mean_absolute_error=("absolute_error", "mean"),
    )
    .reset_index()
)

# Add beginning/end prediction means to expose adaptation after regime shifts.
for regime in (1, 2, 3):
    sub = df[df.regime == regime]
    first5 = sub.head(5)["predicted_probability"].mean()
    last5 = sub.tail(5)["predicted_probability"].mean()
    summary.loc[
        summary.regime == regime,
        "first5_mean_prediction",
    ] = first5
    summary.loc[
        summary.regime == regime,
        "last5_mean_prediction",
    ] = last5

summary.to_csv(ROOT / "regime_summary.csv", index=False)

trigger_df = df[df["curiosity_triggered"]].copy()
trigger_df[[
    "cycle",
    "regime",
    "predicted_probability",
    "observed_success",
    "brier_score",
    "absolute_error",
    "surprise_bits",
    "curiosity_need_id",
]].to_csv(ROOT / "curiosity_triggers.csv", index=False)

overall_stats = prediction_audit.stats(
    "file.write",
    strategy_key="adaptive-file-write",
)
checkpoint = graph.ledger.verify()
pred_count, pred_head = prediction_ledger.verify()

report = {
    "actions": len(df),
    "elapsed_seconds": elapsed,
    "overall_mean_brier": float(df.brier_score.mean()),
    "static_050_mean_brier": float(df.baseline_050_brier.mean()),
    "brier_improvement_vs_static_050": float(
        df.baseline_050_brier.mean() - df.brier_score.mean()
    ),
    "prediction_stats": {
        "observations": overall_stats.observations,
        "empirical_success_rate": overall_stats.empirical_success_rate,
        "mean_predicted_probability": overall_stats.mean_predicted_probability,
        "mean_brier_score": overall_stats.mean_brier_score,
        "mean_absolute_error": overall_stats.mean_absolute_error,
        "calibration_gap": overall_stats.calibration_gap,
    },
    "prediction_ledger_records": pred_count,
    "prediction_ledger_head": pred_head,
    "curiosity_trigger_count": int(df["curiosity_triggered"].sum()),
    "curiosity_trigger_cycles": [
        int(x) for x in df.loc[df["curiosity_triggered"], "cycle"].tolist()
    ],
    "pending_research_needs": len(agenda.pending()),
    "glyph_events": checkpoint.event_count,
    "glyph_merkle_root": checkpoint.merkle_root,
}
(ROOT / "report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)

# Rolling empirical success, shown only for interpretation after outcomes exist.
df["rolling_success_8"] = (
    df["observed_success"].rolling(8, min_periods=1).mean()
)

plt.figure(figsize=(11, 5))
plt.plot(
    df["cycle"],
    df["predicted_probability"],
    label="Syn predicted P(success)",
)
plt.plot(
    df["cycle"],
    df["rolling_success_8"],
    label="Observed success, rolling 8",
)
plt.axvline(40.5, linestyle="--")
plt.axvline(80.5, linestyle="--")
for trigger_cycle in df.loc[df["curiosity_triggered"], "cycle"]:
    plt.axvline(trigger_cycle, linestyle=":")
plt.ylim(0, 1)
plt.xlabel("Cycle")
plt.ylabel("Probability / empirical rate")
plt.title("SYN-PREDICT adapts to non-stationary verified outcomes")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "prediction_adaptation.png", dpi=170)
plt.close()

plt.figure(figsize=(11, 5))
plt.plot(
    df["cycle"],
    df["brier_score"].rolling(10, min_periods=1).mean(),
    label="Adaptive Brier, rolling 10",
)
plt.axhline(0.25, linestyle="--", label="Static p=0.5 Brier")
plt.axvline(40.5, linestyle="--")
plt.axvline(80.5, linestyle="--")
plt.xlabel("Cycle")
plt.ylabel("Brier score (lower is better)")
plt.title("Prediction quality through two environment shifts")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "brier_over_time.png", dpi=170)
plt.close()

print("=== SYN-PREDICT CALIBRATION STRESS ===")
print(f"Actions: {len(df)} | elapsed: {elapsed:.3f}s")
print(summary.to_string(index=False))
print(
    "\nOverall adaptive mean Brier:",
    f"{report['overall_mean_brier']:.4f}",
)
print(
    "Static p=0.5 mean Brier:",
    f"{report['static_050_mean_brier']:.4f}",
)
print(
    "Improvement vs static p=0.5:",
    f"{report['brier_improvement_vs_static_050']:.4f}",
)
print(
    "Overall calibration gap:",
    f"{report['prediction_stats']['calibration_gap']:.4f}",
)
print("Prediction ledger records:", pred_count)
print(
    "Curiosity trigger cycles:",
    report["curiosity_trigger_cycles"],
)
print("Pending research needs:", report["pending_research_needs"])
print("Glyph events:", checkpoint.event_count)
print("Glyph Merkle root:", checkpoint.merkle_root)
