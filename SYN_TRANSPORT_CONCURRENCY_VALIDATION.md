# Serialized provenance imports

Base: `bf3c3794ef202a06e4779ba52380fd89dd2b7e0e` (PR 40).
Prepared 2026-09-27 as a review draft, with no merge or deployment.

## Problem and change

The replay check and final replay record were separated by persistent receipt,
Glyph and origin writes. Two simultaneous imports could both pass the initial
check. Locking only the final append would still allow the rejected contender to
perform these earlier mutations.

ProvenanceReplayLedger now uses the shared canonical-path PathTransaction for
reads, replay checks, append and verification. The importer holds this same
reentrant transaction from signature/freshness validation through the final
replay append. Cooperating importers sharing that ledger serialize their entire
check-and-import operation. The second copy is rejected before destination
receipt, Glyph or origin mutation. Distinct accepted imports retain an intact
replay chain. Freshness is checked after acquiring the lock, so queueing cannot
preserve an earlier freshness decision.

Existing sender allowlists, signatures, receipt chains, authority filters and
nonce/bundle identity checks remain in place. Imported content remains
`remote_signed_claim`, `remote_transport`, `runtime_local=False`.
No remote claim is promoted to a local runtime fact.

## Validation

A GPT-6 Luna agent implemented the targeted change and concurrency regressions.
Coordinator review adds expiry-during-lock-wait and lock-timeout checks, including
absence of destination writes and successful retry after timeout.

Six new cases cover duplicate and distinct signed imports through separate
importer/replay-ledger instances, direct nonce collision, eight spawned ledger
writers, expiration during lock wait and timeout/retry. Duplicate tests count
receipt-append and origin-binding calls, so deduplication cannot hide repeated
side effects. Race windows are widened without disabling verification.

Two regressions fail against the unchanged PR 40 implementation: eight copies
cause 16 receipt-append calls instead of two, and concurrent distinct appends
produce a replay-ledger sequence failure.

Full local suite: **640 passed, 2 pre-existing dependency warnings in 26.55s**,
Python 3.12 / Linux. Remote Python 3.11/3.12 results are recorded on the PR after
publication. No live Internet research was executed in this test run.

## Boundaries

This is serialization, not rollback or a multi-file atomic commit. A process
failure after receipt/Glyph/origin writes but before replay append can leave
partial state; automatic crash recovery for that interval is not introduced.
Do not interpret this change as exactly-once execution across crashes.

All cooperating importers writing the same destination stores must use the same
replay ledger and compatible configuration. Direct writes to the receipt store,
identity configuration changes, or imports using a different replay ledger are
outside this lock. Configure identities/policies before concurrent operation.

Local POSIX filesystems only, using spawn rather than inherited fork state.
Retain lock sidecars, avoid replacing/aliasing active ledger files, and do not use
this protocol as protection against hostile writers or network filesystem races.
Lock order is replay ledger then Glyph journal; do not acquire replay locks from
callbacks already holding the Glyph lock. Contention may wait or time out before
import. Native Windows and arbitrary whole-workspace concurrency remain unsupported.
