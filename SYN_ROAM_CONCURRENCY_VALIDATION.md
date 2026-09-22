# Shared-agenda scheduling and receipt serialization

Date: 2026-09-22. Base: `18660aee70b8eac2c97c803333a5d03da2c90501`
(PR 37, 612 tests). Draft review branch; no merge or deployment.

## Change

Concurrent schedulers could select the same pending need or manipulate the same
attempt file simultaneously. The existing crash-recovery markers assumed one
writer and were not themselves a scheduling lock.

ResearchAgenda now resolves its path once and uses the shared PathTransaction
lock. Initialization holds the lock while recovering pending intents and checking
history. Public reads, lifecycle checks and writes use the same reentrant lock.
RoamAttentionController holds it across reconciliation, hooks, selection, research
and agenda settlement; evaluate_need holds it across its check/evaluate/mark path.

RoamServiceLedger serializes reads, sequence assignment and appends. SynRoamService
holds that ledger lock across reconciliation, intent, controller call, completed
receipt and final append. The lock order is service -> agenda -> Glyph. No new
locking implementation or dependency is introduced.

Two services sharing an agenda serialize even if their service-ledger paths differ.
The lock is intentionally held during research: a second caller either waits and
observes updated state or times out before entering the protected operation.

## Validation

One GPT-5.6 Luna agent implemented the wrapping and five process-concurrency cases.
Coordinator review strengthened graph/receipt assertions, added real process-exit
and bounded-contention checks, then ran the full suite.

Eight new cases cover:
- Two spawned schedulers sharing one agenda, with either the same or separate
  service ledgers: one research call, one researched tick and one idle tick.
- Concurrent agenda additions preserve both rows and their provenance edges.
- Conflicting cancel/research transitions accept only one terminal state.
- Concurrent service appends preserve sequence and digest chaining.
- Actual os._exit during controller and service calls releases the OS lock but
  retains the unknown-outcome receipt, preventing a replay.
- A contending controller times out without altering the active receipt.

Both scheduler cases fail against PR 37 with receipt-file races. Their new-version
results verify both one source invocation and coherent agenda/service histories.
The research adapters are deterministic fixtures; no live Internet run is claimed.

Full local suite: **620 passed, 2 pre-existing warnings in 12.29s**, Python 3.12.14,
Linux. GitHub Python 3.11/3.12 results are recorded on the PR after publication.

## Boundaries and operation

Local cooperating POSIX writers only. Native Windows is unsupported. Use spawned
workers and keep `.lock` sidecars in place while processes run. Do not write raw
files, replace paths, or alias them through hard links during operation. Shared
agendas must use consistent graph paths, actor and policy configuration.

The lock acquisition timeout remains 10 seconds by default. A long active research
can make another caller time out; it does not terminate the active call. With a
separate service ledger, a timeout inside its controller may conservatively leave
that service's pre-call marker unknown. It then requires the same explicit review
as other uncertain attempts; no automatic reset erases it.

Do not acquire service locks while holding agenda/Glyph locks or recursively launch
services from callbacks. Waiting on a background thread that needs the same held
agenda can likewise time out. These locks serialize work, not roll it back.

Different agendas must not independently write a shared method/learning ledger.
Those stores and arbitrary whole-agent loops still require a single writer. This
lot does not promise cross-store atomicity, crash-safe evaluation, exactly-once
network effects, power-loss recovery or a globally concurrent agent workspace.
Existing interrupted-call receipts and pending intents remain part of backups.
