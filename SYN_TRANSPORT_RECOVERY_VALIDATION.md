# Interrupted provenance-import guard

Prepared 2026-09-27 on PR 41 commit
`7ef429142dd4300643c0f1eef822a82b6cfb38da` (640 tests).
Draft review change; no merge or deployment.

## Behavior

The shared replay-ledger lock now also protects a persistent import-attempt
marker. Signature, freshness and staged receipt checks happen before this marker
is written. Before any destination receipt/Glyph/origin write, the importer
atomically writes and syncs `<replay-ledger>.transport-attempt.json`.
The marker binds the sender, bundle, nonce, remote Glyph, destination paths and
exact prior replay-journal length/head. Its checksum detects accidental damage;
it is not authentication against a writer who can rewrite these files.

On entry, the importer verifies the replay chain and checks any outstanding
marker before processing another bundle. Only an exact next terminal replay
event, with the recorded predecessor and identities, confirms completion. In
that case the stale marker is removed and ordinary replay checks still reject
the already-imported bundle. No receipt or Glyph effects are repeated.

An uncertain attempt, damaged marker, wrong destination or inconsistent journal
blocks further imports. The marker is retained. This includes a failure after
marker persistence but before the first destination write: the implementation
deliberately does not guess whether effects occurred. This is a recoverable
completed-import receipt plus an incomplete-import stop, not automatic completion
of partially written imports.

## Operator boundary

Keep the marker and replay/receipt/Glyph journals together in backups. After an
uncertain-import error, preserve these files and review them as a consistent
set. Do not delete the marker just to restart imports: doing so bypasses the
uncertainty guard. No automatic reset or destructive cleanup is provided.
A destination path change while an attempt is pending requires review as well.

The protocol coordinates cooperating importers sharing one replay ledger and
compatible configuration. Direct journal writers and unrelated readers do not
participate in a multi-store transaction. Partial Glyphs can remain visible to
other readers; this change does not roll them back or quarantine them globally.

Local POSIX filesystem semantics and spawn workers remain required. Process
termination is tested. Durable marker writing does not make all destination
stores atomic across power loss, filesystem failure, or hostile rewriting.

## Validation

A GPT-6 Luna agent prepared the guard and fault-injection tests. Coordinator
review added real spawned-process termination after receipt write, Glyph creation
and final replay commit, and reviewed journal-prefix validation.

Fifteen new cases pass, including three actual process-death scenarios.
Full local suite: **655 passed, 2 pre-existing dependency warnings in 25.19s**,
Python 3.12 / Linux. Independent Python 3.11/3.12 CI results are recorded on the
PR after publication. No live external research was run.
