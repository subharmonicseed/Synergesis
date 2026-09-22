# Agenda recovery and structural REALITY validation

Date: 2026-09-22. Base: `f01e634598951f0b9a5bb6b867e06a2c7a8c0ee8`
(PR 33, 550 tests). This is a separate draft review branch; main is unchanged.

## Agenda process-crash recovery

ResearchAgenda validates source parents before creating an intent. Each intent
captures the complete lifecycle event, actor and attention score, then is written
through a temporary file, flushed, fsynced and renamed. The graph projection and
agenda row are completed idempotently before removing the intent. Reopening the
agenda replays pending intents in per-need sequence order.

Recovery recreates missing parent/supersedes edges without duplicating the goal or
agenda event. Conflicting payloads, non-contiguous sequences and invalid lifecycle
transitions are rejected before graph mutation. A stale already-committed intent
uses its exact predecessor, so it cannot link an old state to a newer state.
Configuration changes do not recalculate the score/actor of an interrupted event.

Valid legacy JSONL histories remain supported. Rows with no graph projection,
inconsistent content or missing provenance edges raise an explicit reconciliation
error. No automatic historical backfill is performed.

The `.pending` directory next to the agenda is part of its durable state: include
it with the agenda and graph in backups. Do not delete intents to suppress errors.
This is single-writer recovery after process interruption, not an atomic database,
multi-writer protocol or a guarantee against power loss/torn JSONL writes. There
is no automatic repair for corrupt legacy rows and no exactly-once guarantee for
the external research session itself (the ROAM tick/session receipt remains a
separate backlog item).

## Prediction input validation

Before settlement creates learning or updates calibration, the referenced glyph
must be a decision of kind `reality_verdict`, with explicit proposal, action,
status and effect fields. Booleans are strict: numeric 1 is not accepted as True.
Confirmed/contradicted map to True/False; unverified/observer_conflict map to None.
Exactly one evaluates edge must reference the prediction's action glyph, whose
proposal identity must also agree.

On reconstruction, the learning result must agree with the verdict and original
prediction. Scored/unscored status, strategy, probability and recalculated Brier,
absolute error and surprise are checked before that record repairs calibration.
Observer conflict remains unscored after restart.

This is structural consistency inside the trusted local graph. Actor names are
not authenticated identities, and this does not make an arbitrary writer to that
graph trustworthy. Producer authority/attestation policy remains a separate
boundary. Old malformed synthetic or stored records now fail closed and require
explicit review; no permissive compatibility bypass is included.

## Validation

- Two GPT-5.6 Luna agents prepared disjoint agenda and prediction changes.
  The coordinating model reviewed both, added recovery edge-case checks/tests
  and updated synthetic fixtures to the real decision/evaluates contract.
- Five targeted cases executed against the preceding source: four failures
  demonstrating the missing guards, one already-passing compatibility case.
- Final local suite: **573 passed, 2 warnings in 3.77s**, Python 3.12.14 / Linux.
  There are 23 new cases (11 agenda, 12 verdict). The two dependency warnings
  were already present in the baseline.
- Existing causal-credit, world revision and complete-stack tests remain enabled.
- CI now runs once per pull request update and on main pushes, with superseded
  runs cancelled. This avoids the previous duplicate push/PR matrices while
  preserving the Python 3.11 and 3.12 checks.
- Remote CI status is recorded on the PR after publication; the local result is
  not itself a remote CI receipt. No live Internet research, deployment or merge
  is part of this validation.
