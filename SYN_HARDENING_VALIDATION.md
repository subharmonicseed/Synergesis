# Network, prediction recovery and installation hardening

Base: `0732743d11ff964d6d72a830fc92c9e2fe92f310` (draft PR 32).
Validation date: 2026-09-21. This is an incremental review branch; main is unchanged.

## Changes

- SEC-01: remove Authorization, Cookie and Proxy-Authorization on cross-origin
  redirects, comparing scheme/host/effective port. Credentialed Requests sessions
  are conservatively blocked from cross-origin redirection because session defaults
  could otherwise reinsert secrets. Custom transports remain trusted adapters.
- SEC-02: use streamed decoded chunks, reject oversized responses and close the
  response on success or failure. The default transport receives the policy cap.
- SEC-03: finite policy numbers, capped server retry delays and a cooperative
  request-time budget covering pacing/retries/redirects, checked after transport.
- COG-01/02: preserve pending predictions for the same action, reconstruct the
  latest prediction per proposal from linked durable glyphs, reject conflicting
  settlement replays and avoid duplicate calibration rows. Repeated intentional
  executions after a settled prediction can still produce a new prediction.
- Sink delivery has durable started/completed glyphs. Completed deliveries are
  skipped after restart, including when sinks are registered after construction.
  An exception or restart with uncertain delivery raises an explicit recovery
  error rather than repeating potentially completed effects. Calibration append
  failure is repaired idempotently on replay/reconstruction.
- Packaging: explicit maintained modules, test extras, a CPython 3.12 dependency
  constraint snapshot, current README and a Python 3.11/3.12 CI workflow. The
  legacy prototype that downloads spaCy at import is excluded from the package.

## Executed validation

- Original manifest: 155 entries matched before changes.
- Original suite rerun: 527 passed, 2 dependency deprecation warnings.
- New regression modules against the old source: 23 failures (including new
  API parameters absent in the baseline); against the corrected source: pass.
- Final full local suite in the newly installed dependency environment:
  `550 passed, 2 warnings in 3.44s`.
- A new virtual environment installed `.[test]` successfully; 58 packaged modules
  imported from outside the checkout. A truncated local NumPy binary was detected
  during import validation and reinstalled before the successful full-suite run.
- Python 3.12.14 / Linux used locally. Python 3.11 is configured in CI but has not
  been executed locally. No remote CI result is claimed here.

Regression coverage includes fresh graph/engine reconstruction before settlement,
completed sink receipts after restart, late sink registration, callback uncertainty,
failed calibration append with and without restart, mismatched reality identities,
cross-origin credentials, port changes, oversized/read-failed streams and deadlines.

## Boundaries and remaining backlog

- Journals remain single-writer; this change does not make cross-file writes atomic.
- Requests timeouts are not hard real-time cancellation. Cooperative checks cannot
  interrupt a socket read, DNS call or decompressor already blocked internally.
  The cap concerns retained decoded body content, not a strict global memory/CPU
  or compressed-wire budget. Strict isolation needs a separate worker boundary.
- Sink identities currently include class and registration index. Keep sink order
  stable when reopening state. Legacy settlements without receipts, changed sink
  registrations and interrupted deliveries may require explicit reconciliation.
  There is no automatic reconciliation command or exactly-once external-effect
  guarantee. Neither missing receipts nor uncertainty are silently treated as success.
- Recovery uses the latest prediction per proposal, matching the sequential agent
  loop. Multiple concurrent in-flight executions of one proposal are unsupported.
- Basic proposal/action identity is checked, but the full COG-03 verdict content,
  authority and action-link validation contract remains to be implemented.
- Agenda/graph transaction recovery, multi-writer risk reservations, probe race
  hardening, runner portability and restoration review remain separate backlog items.
- Existing historical validation files (including the 519 snapshot receipt) are
  preserved. This document records this iteration; the current manifest records its
  bytes. No long live-web run, deployment or merge is claimed.

Three GPT-5.6 Luna agents prepared network, prediction and packaging changes.
The coordinating model reviewed and corrected integration/recovery edge cases,
extended the regression tests and executed the final validation.
