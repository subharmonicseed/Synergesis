# Synergesis synchronized handoff — 350 green

Use the archive `Synergesis_integrated_350_green_2026-09-12.zip` as the coherent source snapshot.

Verified contents include:

- `synergesis_glyph_agent_v2.py`;
- `synergesis_aegis.py` with `runtime_attested`;
- `synergesis_world_revision.py`;
- `synergesis_causal_credit.py`;
- `synergesis_secure_roam_stack_v2.py`;
- strengthened `test_synergesis_causal_credit_stack.py`.

Validation:

- source tree: 350 passed, 0 failed;
- clean extraction of the snapshot: 350 passed, 0 failed.

The causal end-to-end test now observes the applied intervention through a separate runtime receipt rather than copying the requested intervention parameter. A requested `repair` with actual applied `check` yields `intervention_unverified`, `not_identified`, and keeps the posterior at 50/50.

Do not overlay isolated files onto an older branch. Replace the working source tree with this coherent snapshot or reconcile diffs explicitly before editing.
