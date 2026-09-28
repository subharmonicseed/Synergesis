# Perception provenance recovery

Base: PR #43, commit `2ef1bd5379c74f88893e8151b360f270d7738afd`.
Date: 2026-09-28. All 190 base files verified against the GitHub tree before edits.

## Reproduced defect

PerceptionBus only bound source authority and taint when it first created a raw
percept. A restart finding that raw percept skipped the binding. The normalized
percept could likewise survive without its derived-from edge.

Four regression scenarios stop a spawned process with `os._exit(39)` immediately
after appending raw, origin-policy, taint-policy or normalized glyphs. Against
the base version, all four fail: missing origin, missing taint or missing lineage.
These are process termination tests, not simulated power cuts.

## Recovery contract

New raw percepts preserve their configured source authority and taint contract
in the durable record, separately from sensor payload. Retrying reconciles
missing policy and lineage links, without adding another logical observation.
A changed contract or conflicting origin fails closed. Legacy observations
without a recorded contract cannot have an unknown original policy guessed
from today's settings; incomplete legacy records require operator review.

The scope is the PerceptionBus ingestion boundary. This does not automatically
repair downstream knowledge admission, arbitrary AEGIS operations, or a whole
agent run. Local POSIX cooperating-writer assumptions remain. Normalization
adapters must tolerate retry when interrupted before recording their output;
this does not provide exactly-once external adapter effects. Stored normalized
output is reused; adapter versions are not migrated by this change.

## Validation results

- Six process-restart cases pass, including changed authority/taint before origin
  binding. Four failure stages were reproduced on the unchanged base code.
- Six additional recovery tests cover contract mismatch, conflicting authority,
  complete/incomplete legacy data, explicitly cleared taint and malformed contracts.
- Targeted integrated tests: 62 passed.
- Full suite: **669 passed, 2 pre-existing dependency warnings in 13.63s**.
- System CPython 3.12.14 with existing test dependencies through PYTHONPATH;
  this local result is not a fresh-install receipt.
- Lightweight implementation agent; parent review strengthened replay validation
  and added independent real-process crash tests. Core AEGIS APIs unchanged.
- GitHub CI is checked separately on the published commit.

The full ingest holds the existing Glyph ledger transaction so cooperating
PerceptionBus callers cannot race contract selection and attachment. The lock
supplies serialization, not rollback. Adapters should be quick and must not
wait for another thread/process writing to the same ledger while normalizing.

