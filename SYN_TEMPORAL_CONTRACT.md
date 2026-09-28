# Fusion and provisional belief temporal contract

## Fusion boundary

Fusion always checks the configured maximum span between captures. Absolute
freshness checks are opt-in: without `now_fn`, the fusion consumer does not
claim that a capture is current, future, or stale. This preserves archive and
fixture replay behavior. Supplying `now_fn` (a callable returning an aware
`datetime`) rejects a set whose newest capture is after that reference time.
`FusionPolicy.max_observation_age_seconds` additionally rejects sets whose
oldest capture is older than the configured age. The default is `None`, so
the clock alone does not impose an age limit. Temporal rejection leaves support
and provenance intact and produces an unresolved decision with an explicit
`future_observation` or `stale_observation` reason.

## Provisional belief expiry and conflict

The expiry boundary is inclusive: a provisional belief is expired when
`now >= expires_at`. Expiry is a view over the original immutable revision; it
does not rewrite or relabel that event. Expired claims do not veto newer
contradictory supported evidence, including same-capture-time conflicts. A
same-capture-time conflict stays suspended across later arrivals, so arrival
order cannot select a winner. A fresh fusion still needs to pass the ordinary independent-group, support,
margin, and observation-order rules. An exact replay remains idempotent and
does not renew the TTL. Suspended or rejected revisions retain their recorded
statuses and do not become provisional through expiry.

## Receipt and replay transition

New fusion inference glyphs carry `fusion_identity_version: 2` and a
`configuration_fingerprint` over the fusion policy, sorted source profiles,
and whether an absolute clock boundary was enabled. Receipts also include
`evaluated_at`, the exact UTC instant used for temporal adjudication (or `null`
when no clock is configured). Both are included in the fusion identity, so
replays at the same instant remain idempotent and changed time-dependent
adjudications have distinct identities. Existing glyphs retain their
stored content and IDs; there is no backfill or relabeling. Readers should
interpret glyphs without `fusion_identity_version` as historical v1 receipts
whose identity did not attest to this configuration fingerprint. Replaying old
inputs after upgrading can therefore create a v2 inference alongside its v1
record. Consumers must select by version/configuration and provenance rather
than assuming a historical identifier will be regenerated under new rules.

ROAM's new `research_method_outcome` glyphs similarly carry
`configuration_version` and a fingerprint of selection configuration, utility
weights, and method ID. The fingerprint is additive to the glyph; method-ledger
outcome IDs, semantic equality, and existing ledger replay behavior remain
unchanged. Older method outcome glyphs remain readable without migration.

## Audit disposition

- COG-07: closed for the audited fusion consumer contract and explicit-clock
  tests; freshness remains intentionally disabled unless configured.
- COG-08: closed; inclusive expiry and expired-belief conflict behavior are
  implemented and covered, and old revisions remain immutable.
- COG-09: closed for new fusion and ROAM outcome receipts. Fingerprints identify
  the stated configuration inputs; they do not fingerprint external data or
  arbitrary callable implementations behind `now_fn`.
- OPS-10: closed for these fusion receipts: v1 history stays readable, v2 is
  explicit, and replay implications are documented. No historical events are
  migrated or rewritten.
