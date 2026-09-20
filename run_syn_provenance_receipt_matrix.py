
import sys, shutil, time, json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, "/mnt/data")

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_aegis import (
    AegisSecurityGraph, AegisGuard, ActionSecurityProfile,
    IdentityRegistry, IdentitySigner, CapabilityStore, SecurityContext,
)
from synergesis_agent_loop_v2 import ActionProposal
from synergesis_provenance_receipts import (
    ProvenanceReceiptStore, ProvenanceReceiptAuthority,
    ProvenanceReceiptVerifier, bind_verified_origin_receipt,
)

ROOT = Path("/mnt/data/syn_provenance_receipt_matrix")
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)

graph = GlyphAuditGraph(GlyphLedger(ROOT / "glyphs.jsonl"))
security = AegisSecurityGraph(graph)
registry = IdentityRegistry(ROOT / "identities.jsonl")
ingress_signer = IdentitySigner("ingress")
relay_signer = IdentitySigner("relay")
syn_signer = IdentitySigner("ZÆL-0")
for ident, signer in [
    ("ingress", ingress_signer),
    ("relay", relay_signer),
    ("ZÆL-0", syn_signer),
]:
    registry.register(ident, signer.public_key)

receipt_store = ProvenanceReceiptStore(ROOT / "receipts.jsonl")
origin_authority = ProvenanceReceiptAuthority(ingress_signer)
relay_authority = ProvenanceReceiptAuthority(relay_signer)
verifier = ProvenanceReceiptVerifier(
    store=receipt_store,
    identity_registry=registry,
    trusted_origin_issuers=frozenset({"ingress"}),
    trusted_derivation_issuers=frozenset({"relay"}),
    origin_ranks=security.ORIGIN_CLASSES,
)

guard = AegisGuard(
    graph=graph,
    identity_registry=registry,
    capability_store=CapabilityStore(ROOT / "caps.jsonl"),
    trusted_capability_issuers=frozenset(),
    allowed_actions=frozenset({"system.change"}),
    profiles=(
        ActionSecurityProfile(
            "system.change",
            False,
            frozenset(),
            require_bound_origins=True,
            minimum_origin_rank=3,
        ),
    ),
    security_graph=security,
)

pattern = ["concept", "fact", "observation", "hypothesis", "decision"]

def proposal(tag):
    return ActionProposal.create(
        "system.change",
        {"scenario": tag},
        rationale="portable provenance stress",
        expected_outcome="authorization only",
        strategy_key="receipt-matrix",
    )

rows = []
start = time.perf_counter()

# Every break location, for both malicious external and benign trusted origins.
for origin_class, malicious in [
    ("external_untrusted", True),
    ("trusted_observation", False),
]:
    for depth in range(2, 13):
        for break_at in range(depth):
            sid = f"{origin_class}_d{depth}_b{break_at}"
            origin = graph.create(
                "evidence" if malicious else "observation",
                actor="source:ingress",
                content={"scenario": sid, "root": True},
            )
            if malicious:
                security.mark_taint(
                    origin.glyph_id,
                    label="external_untrusted",
                    reason="receipt matrix adversarial origin",
                )

            receipt = origin_authority.issue_origin(
                glyph_id=origin.glyph_id,
                authority_class=origin_class,
                rank=security.ORIGIN_CLASSES[origin_class],
            )
            receipt_store.append(receipt)

            current = origin
            recovered_trace = None
            for i in range(depth):
                gtype = pattern[i % len(pattern)]
                preserve_edge = i != break_at
                child = graph.create(
                    gtype,
                    actor="relay",
                    content={
                        "scenario": sid,
                        "step": i,
                        "break_here": not preserve_edge,
                    },
                    derived_from=(current.glyph_id,) if preserve_edge else (),
                )
                receipt = relay_authority.issue_derivation(
                    glyph_id=child.glyph_id,
                    parent_receipt_id=receipt.receipt_id,
                    transform_kind=f"hop_{i}",
                )
                receipt_store.append(receipt)

                if not preserve_edge:
                    recovered_trace = bind_verified_origin_receipt(
                        security_graph=security,
                        glyph_id=child.glyph_id,
                        receipt_id=receipt.receipt_id,
                        verifier=verifier,
                    )
                current = child

            action = graph.create(
                "action",
                actor="ZÆL-0",
                content={"scenario": sid, "action_type": "system.change"},
                derived_from=(current.glyph_id,),
            )
            decision = guard.check(
                proposal(sid),
                SecurityContext(
                    actor_id="ZÆL-0",
                    provenance_glyph_ids=(action.glyph_id,),
                    resource="action:system.change",
                ),
            )

            assessment = security.assess_provenance((action.glyph_id,), max_depth=64)
            binding = assessment.origin_bindings[0] if assessment.origin_bindings else {}
            expected_allow = not malicious
            rows.append({
                "scenario": sid,
                "origin_class": origin_class,
                "malicious": malicious,
                "depth": depth,
                "break_at": break_at,
                "expected_allow": expected_allow,
                "actual_allow": decision.allowed,
                "decision_reason": decision.reason,
                "receipt_origin_recovered": (
                    recovered_trace is not None
                    and recovered_trace.true_origin_glyph_id == origin.glyph_id
                ),
                "binding_true_origin_recovered": (
                    binding.get("true_origin_glyph_id") == origin.glyph_id
                ),
                "receipt_hops": (
                    recovered_trace.hops if recovered_trace else None
                ),
                "minimum_origin_rank": assessment.minimum_origin_rank,
                "unbound_roots": len(assessment.unbound_root_glyph_ids),
            })

elapsed = time.perf_counter() - start
df = pd.DataFrame(rows)
df["decision_correct"] = df.expected_allow == df.actual_allow
df.to_csv(ROOT / "receipt_stress_results.csv", index=False)

summary = {
    "scenarios": len(df),
    "elapsed_seconds": elapsed,
    "decision_accuracy": float(df.decision_correct.mean()),
    "receipt_true_origin_recovery": float(df.receipt_origin_recovered.mean()),
    "binding_true_origin_recovery": float(df.binding_true_origin_recovered.mean()),
    "unbound_after_verified_receipt_rate": float((df.unbound_roots > 0).mean()),
    "malicious_block_rate": float((~df[df.malicious].actual_allow).mean()),
    "benign_allow_rate": float(df[~df.malicious].actual_allow.mean()),
}
checkpoint = graph.ledger.verify()
summary["glyph_events"] = checkpoint.event_count
summary["glyph_merkle_root"] = checkpoint.merkle_root
summary["receipt_events"] = len(receipt_store.events())

(ROOT / "receipt_stress_report.json").write_text(
    json.dumps(summary, indent=2),
    encoding="utf-8",
)

by_depth = (
    df.groupby(["origin_class","depth"])
      .agg(
          cases=("scenario","count"),
          decision_accuracy=("decision_correct","mean"),
          origin_recovery=("receipt_origin_recovered","mean"),
          binding_recovery=("binding_true_origin_recovered","mean"),
      )
      .reset_index()
)
by_depth.to_csv(ROOT / "receipt_by_depth.csv", index=False)

plt.figure(figsize=(9,5))
for origin_class in by_depth.origin_class.unique():
    sub = by_depth[by_depth.origin_class == origin_class]
    plt.plot(
        sub.depth,
        sub.origin_recovery,
        marker="o",
        label=f"{origin_class}: signed origin recovery",
    )
plt.xlabel("Transform depth")
plt.ylabel("Recovery rate")
plt.ylim(-0.02, 1.02)
plt.title("Portable Ed25519 provenance survives local lineage breaks")
plt.legend()
plt.tight_layout()
plt.savefig(ROOT / "receipt_origin_recovery.png", dpi=160)
plt.close()

print("=== Portable Provenance Receipt Matrix ===")
for k, v in summary.items():
    if isinstance(v, float):
        print(f"{k}: {v:.3f}")
    else:
        print(f"{k}: {v}")
