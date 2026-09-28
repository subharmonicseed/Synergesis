# First offline discovery — 2026-09-28

Base: PR #42, commit `6096bf2dd5e5fa599300311a6af094e4f64b9d35`.
All 186 base Git blobs matched the local source bytes before editing. This
cumulative branch already includes the preceding stacked corrections; no
legacy main files were overlaid, and no main merge is included here.

## Change

Add a French first-run guide and a checkout runner using the real
`build_secure_roam_reality_stack`, with deterministic injected providers and no
source adapters. Two isolated fresh scenarios distinguish a real file write
from an executor claim with no write. REALITY verification, prediction settlement,
world revision and Glyph audit are executed by the production modules. The demo
is not a language-model chat or an autonomous research service.

Fresh readers verify both audit ledgers and their checkpoints. JSON output
includes observed results, audit roots and trace identifiers. Existing output
directories are refused without changes. Files remain available for inspection.

## Validation

- Manual system-Python CLI: real write confirmed, 80 audit events; claim-only
  contradicted, 87 audit events; respective learning scores 0.9 (scripted) and 0.
- Two new integration tests: standard socket connect/DNS methods blocked;
  persisted report and referenced audit records checked; existing directory
  preserved. This is not an OS-level network sandbox.
- Full local suite: **657 passed, 2 pre-existing dependency warnings in 13.15s**.
- CPython 3.12.14; existing test dependencies reused through PYTHONPATH because
  the previous virtualenv executable terminated with code 139. System Python
  ran the demo and full suite successfully. This is not a fresh-install receipt.
- An independent lightweight agent reviewed the runner, guide and tests, with
  no blocking finding. Core modules were not modified.
- Remote CI must be checked separately for this commit.

## Remaining readiness work

This demo does not close the 29-item audit. In particular:

- SEC-04: clarify lexical resource-prefix semantics before using hierarchical
  path permissions (`synergesis_aegis.py` still uses `startswith`).
- COG-06: perception raw-origin binding is still performed only in the new-raw
  branch of `PerceptionBus.ingest`; interrupted binding needs its own recovery
  validation, not an assumption that transport recovery covers it.
- OPS-05: old stress runners still contain `/mnt/data` paths and automatic
  `rmtree`; this new runner does neither. Do not use those old runners as the
  first-user launch path.
- OPS-06: journals outside the explicitly locked set still require one writer;
  whole-stack enforcement and power-loss semantics are not established here.
- OPS-09: replacing legacy main still needs a restoration review. Draft PRs
  remain unmerged. Imports with uncertain partial writes require operator review.

No new LLM adapter, API credential, Internet run, automatic partial-import repair
or claim of complete audit closure is introduced.
