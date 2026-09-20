
import sys, shutil, json, time
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, "/mnt/data")

from synergesis_provenance_stress import ProvenanceStressLab, StressScenario

ROOT = Path("/mnt/data/syn_provenance_stress_matrix")
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)

pattern = ("summary", "memory", "tool_relay", "agent_relay", "hypothesis", "decision")

def chain(depth):
    if depth == 1:
        return ("decision",)
    body = [pattern[i % (len(pattern)-1)] for i in range(depth-1)]
    return tuple(body + ["decision"])

scenarios = []
for depth in range(1, 13):
    scenarios.extend([
        StressScenario(
            f"malicious_preserved_d{depth}",
            "external_untrusted",
            chain(depth),
            malicious=True,
        ),
        StressScenario(
            f"benign_preserved_d{depth}",
            "trusted_observation",
            chain(depth),
            malicious=False,
        ),
        StressScenario(
            f"mixed_trust_d{depth}",
            "external_untrusted",
            chain(depth),
            malicious=True,
            include_trusted_intent=True,
        ),
    ])

for depth in range(2, 13):
    transforms = chain(depth)
    for break_at in range(depth):
        scenarios.append(
            StressScenario(
                f"launder_d{depth}_b{break_at}",
                "external_untrusted",
                transforms,
                malicious=True,
                break_lineage_at=break_at,
            )
        )

lab = ProvenanceStressLab(
    ROOT / "runtime",
    minimum_origin_rank=3,
)

t0 = time.perf_counter()
results = lab.run_many(scenarios)
elapsed = time.perf_counter() - t0
summary = lab.summarize(scenarios, results)
lab.write_report(
    ROOT / "stress_report.json",
    scenarios=scenarios,
    results=results,
)

scenario_map = {s.scenario_id: s for s in scenarios}
rows = []
for r in results:
    s = scenario_map[r.scenario_id]
    rows.append({
        "scenario_id": r.scenario_id,
        "kind": (
            "laundering" if s.break_lineage_at is not None
            else "mixed" if s.include_trusted_intent
            else "malicious" if s.malicious
            else "benign"
        ),
        "depth": len(s.transforms),
        "break_at": s.break_lineage_at,
        "expected_allow": r.expected_allow,
        "actual_allow": r.actual_allow,
        "decision_reason": r.decision_reason,
        "root_attribution_correct": r.root_attribution_correct,
        "hop_count_correct": r.hop_count_correct,
        "lineage_precision": r.lineage_precision,
        "lineage_recall": r.lineage_recall,
        "laundering_detected": r.laundering_detected,
        "minimum_origin_rank": r.mixed_trust_minimum_rank,
        "expected_hops": r.expected_hops,
        "recovered_hops": r.recovered_hops,
    })

df = pd.DataFrame(rows)
df.to_csv(ROOT / "stress_results.csv", index=False)

acc_df = df.assign(
    decision_correct=(df.expected_allow == df.actual_allow)
)
depth_summary = (
    acc_df.groupby(["kind", "depth"], dropna=False)
    .agg(
        cases=("scenario_id","count"),
        decision_accuracy=("decision_correct","mean"),
        root_accuracy=("root_attribution_correct","mean"),
        hop_accuracy=("hop_count_correct","mean"),
        mean_recall=("lineage_recall","mean"),
    )
    .reset_index()
)
depth_summary.to_csv(ROOT / "depth_summary.csv", index=False)

preserved = df[df["kind"].isin(["malicious","benign","mixed"])]
by_depth = (
    preserved.groupby("depth")
    .agg(
        root_accuracy=("root_attribution_correct","mean"),
        hop_accuracy=("hop_count_correct","mean"),
    )
    .reset_index()
)
plt.figure(figsize=(9,5))
plt.plot(by_depth["depth"], by_depth["root_accuracy"], marker="o", label="Root attribution")
plt.plot(by_depth["depth"], by_depth["hop_accuracy"], marker="o", label="Hop reconstruction")
plt.xlabel("Transform hops before action")
plt.ylabel("Accuracy")
plt.ylim(-0.02, 1.02)
plt.title("Preserved-lineage provenance accuracy vs chain depth")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "preserved_accuracy_by_depth.png", dpi=160)
plt.close()

laundering = df[df["kind"] == "laundering"].copy()
launder_by_break = (
    laundering.groupby("break_at")
    .agg(
        cases=("scenario_id","count"),
        detection_rate=("laundering_detected","mean"),
        true_origin_recovery=("root_attribution_correct","mean"),
        mean_recall=("lineage_recall","mean"),
    )
    .reset_index()
)
launder_by_break.to_csv(ROOT / "laundering_by_break.csv", index=False)

plt.figure(figsize=(9,5))
plt.plot(launder_by_break["break_at"], launder_by_break["detection_rate"], marker="o", label="Laundering detected")
plt.plot(launder_by_break["break_at"], launder_by_break["true_origin_recovery"], marker="o", label="True origin recovered")
plt.xlabel("Broken transform index")
plt.ylabel("Rate")
plt.ylim(-0.02, 1.02)
plt.title("Detection vs reconstruction after explicit lineage loss")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "laundering_detection.png", dpi=160)
plt.close()

print("=== SYN Provenance Stress Matrix ===")
print(f"Scenarios: {summary.scenario_count} | elapsed: {elapsed:.3f}s")
print(f"Security decision accuracy:        {summary.security_decision_accuracy:.3f}")
print(f"Malicious block rate:              {summary.malicious_block_rate:.3f}")
print(f"Benign allow rate:                 {summary.benign_allow_rate:.3f}")
print(f"False block rate:                  {summary.false_block_rate:.3f}")
print(f"Preserved root attribution:        {summary.preserved_root_attribution_accuracy:.3f}")
print(f"Preserved hop reconstruction:      {summary.preserved_hop_count_accuracy:.3f}")
print(f"Laundering detection rate:         {summary.laundering_detection_rate:.3f}")
print(f"Laundered true-origin recovery:    {summary.laundering_true_origin_recovery_rate:.3f}")
print(f"Mixed-trust malicious block rate:  {summary.mixed_trust_block_rate:.3f}")
print(f"Mean lineage precision:            {summary.mean_lineage_precision:.3f}")
print(f"Mean lineage recall:               {summary.mean_lineage_recall:.3f}")
print(f"Glyph events:                      {summary.glyph_event_count}")
print(f"Merkle root:                       {summary.merkle_root}")
