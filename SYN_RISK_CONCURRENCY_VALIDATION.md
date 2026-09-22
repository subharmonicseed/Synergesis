# Risk budget concurrency validation

Date: 2026-09-22. Base: `24dada181cc733a1484d75416d3a50089974ec27`
(PR 34, 573 tests). Separate draft review branch; no merge or deployment.

## Change

A canonical-path reentrant thread lock and POSIX advisory sidecar lock cover
read/check/append for reservations and terminal events. Ledger reads and direct
appends also take the lock. State is reloaded under lock, including nested calls,
so two manager instances cannot spend the same available balance. Lock acquisition
has a 10-second timeout across thread and process acquisition. Exceptions unwind
locks; the OS releases a process lock when its holder exits.

Terminal writes validate the reservation's directive, amount, action, strategy,
intervention and original event ID before changing the ledger. A graph-write
failure after reservation leaves the exposure reserved, conservatively.

## Tests and review

One GPT-5.6 Luna agent prepared the implementation and initial tests. Coordinator
review corrected nested lock ownership, bounded thread waits, exception cleanup,
canonical paths, fork handling and added regression tests.

Thirteen new cases cover simultaneous spawned processes, duplicate directives
across threads, release/consume contention, process lock timeout and forced holder
termination, nested instances and exception release, altered reservation identity,
unsupported locking, inherited fork state, thread timeout and graph-write failure.
The process test synchronizes four workers and widens the read/write window.
Each worker uses a separate Glyph graph, sharing only the budget journal.

Five regression cases were run against the preceding source and all failed as
expected: the contention run accepted three reservations where only two fit, and
four altered reservation identity fields were not rejected.

Final local full suite: **586 passed, 2 pre-existing dependency warnings in 5.63s**
(Python 3.12.14 / Linux). Remote Python 3.11/3.12 CI results are recorded on the PR
after publication, independently of this local receipt.

## Boundaries

- Local POSIX filesystem with working `fcntl.flock`, cooperating users of this
  ledger API, identical policy configuration for a shared epoch. Native Windows
  explicitly fails closed; multiprocessing workers must use spawn. Fork-inherited
  module state is rejected before touching inherited locks.
- Keep the sidecar `.lock` in place while processes run. Do not unlink/replace the
  ledger or lock, alias it through hard links, or bypass this API. Network filesystem
  locking and hostile direct filesystem writers are outside this contract.
- The lock does not protect other Glyph writers or make the complete agent stack
  concurrently writable. Shared graph and other journals still need single writers.
- No transaction spans the budget journal and graph. A graph failure may leave an
  unmatched reserved exposure requiring review; it cannot free budget automatically.
- No torn-write/power-loss repair or policy-epoch configuration binding is added.
  Corrupt journals fail validation. Existing history and epoch semantics are kept.
