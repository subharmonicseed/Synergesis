# Idempotent method learning and coherent selection

Publication preparation: 2026-09-27. Base:
`ba2f7bb5b0fbfa7e079ef642de68f250ce5f1964` (PR 38, 620 tests).
Draft review branch; no merge or deployment.

## Change

MethodLedger previously appended every evaluation, including repeated evaluations
of the same session. Its sequence/head check also had no concurrent-writer lock.
Retries could therefore inflate a method's observation count, and concurrent writes
could break the digest chain.

The ledger now uses the existing canonical-path PathTransaction. Check, duplicate
lookup and append are serialized. A retry with the same outcome fields except
`evaluated_at` returns the original stored outcome and timestamp without another
row. A changed result for the same session, or reuse of an outcome ID for another
result, is rejected before writing. Identifiers must be nonempty strings; utility
must be finite numeric and not boolean; metrics retain their existing validation.
Ledger sequences must be integers, not boolean/float equivalents.

Legacy clean histories remain readable. Duplicate/conflicting session or outcome
identities in old histories fail with a reconciliation error. No rows are silently
dropped, recounted or rewritten. Preserve a backup and review such histories before
resuming learning; no automated historical correction policy is introduced.

Base learner candidate statistics and adaptive learner score/selection operations
use one locked ledger snapshot. They cannot mix counts from before a concurrent
append with utilities from after it. Register methods and configure learners before
concurrent use; registration/configuration changes are not made transactional.

Existing SynRoam.evaluate graph deduplication now combines with ledger idempotency:
a retry after the outcome commit can finish the graph/agenda projection without
counting the observation again. It does not reconstruct missing caller metrics or
silently accept a different evaluation on retry.

## Validation

One GPT-6 Luna agent prepared the ledger implementation and initial tests.
Coordinator review tightened sequence validation, removed redundant decoding,
protected adaptive snapshots and added integrated retry checks.

Fourteen new cases cover distinct and duplicate spawned-process appends,
conflicting/malformed outcomes, restart replay preserving the first timestamp,
legacy semantic duplicates and damaged chains, invalid sequence/utility types,
interrupted graph and agenda updates, and concurrent adaptive snapshot reads.
The process cases synchronize four workers and widen the hash/append window.

Three selected regressions fail against PR 38: an identical retry returns a new
timestamp, distinct concurrent writes break the sequence, and concurrent duplicate
sessions return four separate records rather than one stored result.

Full local suite before publication: **634 passed, 2 pre-existing dependency
warnings in 21.30s**, Python 3.12.14 / Linux. GitHub's independent Python 3.11/3.12
results are recorded on the PR after publication. No live Internet research is
part of these deterministic tests.

## Boundaries

Cooperating API writers on local POSIX filesystems only; native Windows remains
unsupported. Spawn workers and keep lock sidecars in place. Shared ledgers require
consistent session identifiers and evaluation conventions. No hostile-writer
protection, power-loss repair or multi-store atomic commit is claimed.

A session has one accepted outcome. A genuinely revised evaluation needs an
explicit future revision policy; changing timestamps alone is not new evidence.
These metrics are supplied by the caller, not independently authenticated truths.
The audit digest detects corruption but does not prove metric correctness.

Lock ordering for research flows is service -> agenda -> method -> Glyph. Avoid
callbacks that acquire an earlier lock while holding a later one. Reads may wait
or time out while another process holds the ledger. Different whole-agent loops
still share other stores that remain single-writer; this change does not make the
entire workspace safe for arbitrary concurrent agents.
