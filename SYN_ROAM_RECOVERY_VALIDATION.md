# ROAM interrupted-call recovery

Date: 2026-09-22. Base: `1b626c87c1058193ef88c0a3dbe8b242c937ad4e`
(PR 35, 586 tests). Separate draft review branch; no merge or deployment.

## Problem and change

Previously a research session could finish before its agenda update, leaving a
pending need eligible for another external call. A service tick could also finish
before its ledger append, losing the service receipt entirely.

Both boundaries now write a started receipt before invoking the effectful call.
A returned result is captured in a completed receipt before local bookkeeping.
Receipt files are written through a temporary file, flushed, fsynced and atomically
replaced. The schema and digest are checked on every operation boundary.

A controller completion binds the need payload, original per-need sequence and
session ID. Recovery marks a still-pending need researched or recognizes an
already-researched/evaluated matching state without calling research again.
The service completion carries the exact intended ledger row, its sequence and
previous digest. Recovery appends it once or checks that the existing row matches.
Invalid row digests, sequences, identities and conflicting history fail closed.

Reconciliation happens before hooks or a new tick. The new explicit tick may
then run normally. Recovery repairs metadata; it does not reconstruct or return
an old full RoamSession object, nor rerun evaluation automatically.

## Unknown outcomes and operation

A started receipt without a completed result means the external call may have
happened. Reusing the same object or reconstructing it raises an explicit operator
review error before another call. This also covers ordinary exceptions: the system
cannot assume that an exception means no external effect occurred.

Keep the agenda, its `.pending` directory, the service ledger, graph and adjacent
`.roam-attempt.json` files together in backups. Do not delete an uncertain receipt
just to restart. Preserve a copy and compare the recorded sequence/need, graph
traces, source/tool records and any known session result. An operator must decide
whether the outcome can be reconciled or a new research attempt is justified.
There is no automatic retry/reset or generic operator-resolution API in this lot.
A wrapper's unknown outcome remains blocked even if the inner controller's state
can independently be repaired; no cross-layer inference silently clears it.

## Validation

One GPT-5.6 Luna agent prepared the changes and initial tests. Coordinator review
moved service intent before controller execution, corrected committed/evaluated
sequence handling, validated inner ledger records, and added failure cases plus
actual integrated-stack tests with a counted deterministic source adapter.

19 new tests cover missing/completed/uncertain/corrupt/conflicting receipts,
invalid sequence values, interruptions after agenda and service commits, receipt
creation failure before effects, recovery before hooks, and integrated source-call
counts. Both integrated regressions fail against PR 35: one loses the researched
receipt; the other re-enters research after an unknown outcome.

Full local suite: **605 passed, 2 pre-existing warnings in 5.74s**, Python 3.12.14,
Linux. Remote Python 3.11/3.12 CI results are recorded on the PR after publication.
No live Internet research is part of these deterministic tests.

## Limits

This protocol requires one writer per agenda/service/graph. It does not provide
concurrent scheduling, cross-store atomic commits or exactly-once network effects.
Checksums detect accidental corruption; they do not authenticate a hostile local
writer. Marker replacement and journal writes are tested for process interruptions,
not power failure or torn filesystem writes. Legacy clean histories work; missing
receipts from interruptions before this change cannot be reconstructed reliably.
