# Shared audit journal concurrency

Date: 2026-09-22. Base: `5c0dd8fee961385813cb23cd074f4e95eccecabf`
(PR 36, 605 tests). Separate draft review branch; no merge or deployment.

## Change

GlyphLedger previously checked its cached head, chose the next sequence, and
appended without a writer lock. Concurrent processes could produce duplicate
sequence numbers or duplicate glyph/edge records after the same dedupe check.

Ledger reads, appends, lookup/dedupe and verification now hold a shared canonical
path lock. Graph creation and traversals keep that lock across their constituent
operations. Incremental indexes remain enabled: another cooperating append changes
the file size and triggers reload under lock; explicit verify always rehashes disk.

The bounded reentrant POSIX locking code introduced for the risk budget is now in
`synergesis_storage_lock.PathTransaction`; both journals reuse it. The new module
is included explicitly in the package. The risk budget's previous contention,
shutdown, timeout, identity and fork checks remain in the suite.

## Validation

One GPT-5.6 Luna agent prepared Glyph integration and initial tests. Coordinator
work extracted the common lock, reviewed operation boundaries, widened process
races with a synchronized delayed-clock fixture, and added reader and cross-module
integration checks.

Seven new cases cover six spawned writers producing distinct glyphs, shared-ref
and edge deduplication, 24 writes from threads with separate ledger instances,
rejection of an invalid private event, a reader waiting for a writer's complete
event, and two risk-budget workers sharing their graph with an independent writer.
The last test preserves both chains and the cumulative budget limit.

Three concurrency regressions were run against PR 36: all failed with duplicate
sequence numbers. The invalid-event case also passes the prior version and is a
compatibility guard, not evidence of a newly fixed bug.

Full local suite: **612 passed, 2 pre-existing dependency warnings in 10.07s**,
Python 3.12.14 / Linux. Remote Python 3.11/3.12 results are recorded on the PR after
publication. No external research or autonomous actions were run.

## Operational contract

- Local POSIX filesystem with working advisory `flock`, cooperating API users.
  Native Windows is unsupported and fails closed when locking is attempted.
  Start workers with spawn; inherited fork state is explicitly rejected.
- Keep lock sidecars in place while processes run. Do not replace ledger files,
  access the same file through hard-link aliases, or write outside the protocol.
  A writable lock directory is required even for coordinated ledger reads.
  Network filesystems and hostile direct writers are outside this guarantee.
- Lock acquisition is bounded to 10 seconds by default. The OS releases locks
  on process exit; no custom stale-lock deletion is needed.
- The lock serializes access; it provides no rollback. A graph operation interrupted
  after a glyph but before its edges can still leave partial higher-level work.
  Existing recovery mechanisms remain necessary. No power-loss/torn-write repair
  or exactly-once execution guarantee is introduced.
- Other journals and higher-level controllers still require a single writer.
  Reading several stores is not an atomic snapshot. This does not authorize
  concurrent agent loops over the same complete workspace.
- The risk manager acquires budget then Glyph locks. Do not add a caller that holds
  a Glyph lock while acquiring a budget lock: opposing orders can cause timeouts.
- The earlier risk validation note described shared Glyph writing as unsupported;
  this lot extends only that storage-level boundary. Other exclusions still apply.
