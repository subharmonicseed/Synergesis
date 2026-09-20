
import sys
sys.path.insert(0, "/mnt/data")

from pathlib import Path
import shutil, random, json
import pandas as pd
import matplotlib.pyplot as plt

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_aegis import AegisSecurityGraph
from synergesis_roam import (
    SourceRegistry, SourcePolicy, RetrievedItem, RoamLimits, RoamRuntime,
    MethodLedger, SelectionConfig, UtilityWeights,
    SynRoam, SearchStep, make_method, ResearchQuestion, OutcomeMetrics
)
from synergesis_roam_adaptive import (
    AdaptiveResearchMethodLearner, AdaptiveSelectionConfig
)

ROOT = Path("/mnt/data/syn_roam_endurance_adaptive_v2")
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)

class RegimeAdapter:
    def __init__(self, source_id, cost):
        self.source_id = source_id
        self.cost = cost
        self.cycle = 0
    def set_cycle(self, cycle):
        self.cycle = cycle
    def search(self, *, query, max_items):
        return tuple(
            RetrievedItem(
                source_ref=f"https://{self.source_id}.example/{self.cycle}/{i}",
                title=f"{self.source_id} signal cycle {self.cycle} item {i}",
                content=json.dumps(
                    {"source": self.source_id, "cycle": self.cycle, "query": query, "item": i},
                    sort_keys=True,
                ),
                source_type=self.source_id,
                cost_units=self.cost,
            )
            for i in range(max_items)
        )

REGIME_A = {
    "arxiv":   dict(reliability=.92, novelty=.70, contradiction=.78, predictive=.76),
    "patents": dict(reliability=.62, novelty=.58, contradiction=.72, predictive=.55),
    "github":  dict(reliability=.48, novelty=.72, contradiction=.52, predictive=.43),
}
REGIME_B = {
    "arxiv":   dict(reliability=.56, novelty=.46, contradiction=.54, predictive=.42),
    "patents": dict(reliability=.84, novelty=.78, contradiction=.82, predictive=.86),
    "github":  dict(reliability=.88, novelty=.90, contradiction=.80, predictive=.92),
}

graph = GlyphAuditGraph(GlyphLedger(ROOT / "glyphs.jsonl"))
core = GlyphAuditedCognitiveCore(ROOT / "semantic.jsonl", graph=graph, actor="ZÆL-0")
aura = GlyphAuditedAura(core, graph=graph)
security = AegisSecurityGraph(graph)

sources = SourceRegistry()
for sid, cost in [("arxiv", .15), ("patents", .25), ("github", .20)]:
    sources.register(SourcePolicy(
        source_id=sid,
        source_type=sid,
        domains=("technology",),
        max_items_per_query=2,
        external_untrusted=True,
    ))

adapters = {
    "arxiv": RegimeAdapter("arxiv", .15),
    "patents": RegimeAdapter("patents", .25),
    "github": RegimeAdapter("github", .20),
}

runtime = RoamRuntime(
    graph=graph,
    aura=aura,
    security_graph=security,
    source_registry=sources,
    adapters=adapters,
    limits=RoamLimits(4, 6, 2.0),
    actor="SYN-ROAM-ENDURANCE",
)

ledger = MethodLedger(ROOT / "method_outcomes.jsonl")
learner = AdaptiveResearchMethodLearner(
    ledger=ledger,
    config=SelectionConfig(
        exploration_strength=0.0,
        require_counter_search_for_hypothesis=True,
    ),
    adaptive_config=AdaptiveSelectionConfig(
        rolling_window_per_method=8,
        max_selection_gap=5,
        exploration_strength=0.25,
        decay_half_life_events=4.0,
    ),
    graph=graph,
    actor="SYN-ROAM-ENDURANCE",
)

methods = [
    make_method(
        name="paper_skeptic",
        domain="technology",
        created_by="experiment",
        steps=(SearchStep("arxiv", "challenge", "{question} {hypothesis}", 2),),
    ),
    make_method(
        name="implementation_signals",
        domain="technology",
        created_by="experiment",
        steps=(
            SearchStep("github", "explore", "{question}", 1),
            SearchStep("patents", "challenge", "{question} {hypothesis}", 1),
        ),
    ),
    make_method(
        name="triangulated",
        domain="technology",
        created_by="experiment",
        steps=(
            SearchStep("arxiv", "explore", "{question}", 1),
            SearchStep("patents", "challenge", "{question} {hypothesis}", 1),
            SearchStep("github", "challenge", "{question} {hypothesis}", 1),
        ),
    ),
]
for m in methods:
    learner.register(m)

weights = UtilityWeights(
    verified_yield=1.1,
    novelty_yield=.7,
    contradiction_yield=.9,
    calibration_gain=1.0,
    predictive_value=1.3,
    redundancy_penalty=.8,
    cost_penalty=1.1,
)
roam = SynRoam(learner=learner, runtime=runtime, utility_weights=weights)
rng = random.Random(260912)

def evaluate_session(session, cycle):
    regime = REGIME_A if cycle <= 30 else REGIME_B
    srcs = [ex.source_id for ex in session.executions]
    perspectives = [ex.perspective for ex in session.executions]
    qualities = [regime[s] for s in srcs]
    def noise(scale):
        return rng.uniform(-scale, scale)

    verified = max(0, min(1, sum(q["reliability"] for q in qualities)/len(qualities) + noise(.04)))
    novelty = max(0, min(1, sum(q["novelty"] for q in qualities)/len(qualities) + noise(.04)))
    challenge_indices = [i for i,p in enumerate(perspectives) if p == "challenge"]
    contradiction = (
        sum(qualities[i]["contradiction"] for i in challenge_indices)/len(challenge_indices)
        if challenge_indices else 0.0
    )
    contradiction = max(0, min(1, contradiction + noise(.035)))
    diversity = len(set(srcs)) / 3.0
    calibration = max(0, min(1, 0.55*verified + 0.45*diversity + noise(.03)))
    predictive = max(0, min(1, sum(q["predictive"] for q in qualities)/len(qualities) + noise(.04)))
    redundancy = max(0, min(1, 1.0 - len(set(srcs))/len(srcs)))
    normalized_cost = min(1.0, session.total_cost_units / runtime.limits.max_budget_units)
    return OutcomeMetrics(
        verified_yield=verified,
        novelty_yield=novelty,
        contradiction_yield=contradiction,
        calibration_gain=calibration,
        predictive_value=predictive,
        redundancy=redundancy,
        normalized_cost=normalized_cost,
    )

rows = []
for cycle in range(1, 61):
    for adapter in adapters.values():
        adapter.set_cycle(cycle)

    q = ResearchQuestion.create(
        domain="technology",
        question=f"Which signals best reveal technological transition at cycle {cycle}?",
        hypothesis="A technology is moving from research toward deployment.",
    )
    selected = learner.select(q)
    session = runtime.run(question=q, method=selected)
    metrics = evaluate_session(session, cycle)
    outcome = roam.evaluate(session, metrics)

    rows.append({
        "cycle": cycle,
        "regime": "A" if cycle <= 30 else "B",
        "method": selected.name,
        "utility": outcome.utility,
        "verified": metrics.verified_yield,
        "novelty": metrics.novelty_yield,
        "contradiction": metrics.contradiction_yield,
        "predictive": metrics.predictive_value,
        "cost": metrics.normalized_cost,
    })

df = pd.DataFrame(rows)
df.to_csv(ROOT / "iterations.csv", index=False)

summary = (
    df.groupby(["regime", "method"])
      .agg(selections=("cycle","count"), mean_utility=("utility","mean"))
      .reset_index()
)
summary.to_csv(ROOT / "summary.csv", index=False)

windows = []
for start in range(1, 61, 10):
    sub = df[(df.cycle >= start) & (df.cycle < start+10)]
    counts = sub["method"].value_counts().to_dict()
    windows.append({
        "cycles": f"{start}-{min(start+9,60)}",
        **{m.name: counts.get(m.name, 0) for m in methods},
        "mean_utility": sub["utility"].mean(),
    })
window_df = pd.DataFrame(windows)
window_df.to_csv(ROOT / "windows.csv", index=False)

plt.figure(figsize=(10, 5))
for name in [m.name for m in methods]:
    sub = df[df["method"] == name]
    plt.scatter(sub["cycle"], sub["utility"], label=name, s=28)
plt.axvline(30.5, linestyle="--")
plt.xlabel("Cycle")
plt.ylabel("Observed utility")
plt.title("SYN-ROAM adaptive endurance run: regime shift")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "utility_by_cycle.png", dpi=160)
plt.close()

checkpoint = graph.ledger.verify()
final_stats = {
    m.name: {
        "observations": ledger.stats(m.method_id).observations,
        "mean_utility": ledger.stats(m.method_id).mean_utility,
        "variance": ledger.stats(m.method_id).utility_variance,
    }
    for m in methods
}
report = {
    "cycles": 60,
    "regime_shift_after_cycle": 30,
    "final_stats": final_stats,
    "glyph_checkpoint": {
        "event_count": checkpoint.event_count,
        "chain_head": checkpoint.chain_head,
        "merkle_root": checkpoint.merkle_root,
    },
}
(ROOT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

print("=== SYN-ROAM ADAPTIVE v2 endurance run: 60 bounded cycles ===")
print("\nSelections by 10-cycle window:")
print(window_df.to_string(index=False))
print("\nPer-regime summary:")
print(summary.to_string(index=False))
print("\nFinal method stats:")
for name, values in final_stats.items():
    print(f"- {name}: n={values['observations']}, mean={values['mean_utility']:.3f}, var={values['variance']:.4f}")
print(f"\nGlyph events: {checkpoint.event_count}")
print(f"Merkle root: {checkpoint.merkle_root}")
