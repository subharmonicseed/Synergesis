# Synergesis Glyph Protocol v1

## Status

`synergesis.glyph.v1`

This document defines the first production audit protocol for Synergesis.

A glyph is **not** a claim that the private internal reasoning of a language
model has been exposed. It is an immutable, machine-readable record of an
observable system-level state or transition.

## Foundational invariant

> No consequential state transition without an auditable trace.

A model may remain internally opaque. Any information that influences a
consequential Synergesis decision must cross a typed interface and may then be
recorded as a glyph.

## Why glyphs exist

Glyphs provide a model-independent continuity layer. A reasoning model may be
replaced without deleting:

- observations,
- source evidence,
- hypotheses declared by the model,
- decisions,
- policy checks,
- proposed actions,
- executor outcomes,
- learning signals,
- goals and plans,
- causal/provenance relationships.

The Glyph Graph is therefore an audit and provenance substrate, not a substitute
for the LLM itself.

## Glyph types

- `observation`: externally supplied or sensor-derived observation.
- `evidence`: sourced material admitted into the audit graph.
- `fact`: a validated semantic fact.
- `hypothesis`: a declared proposition that is not yet a fact.
- `decision`: a consequential system-level choice or no-action decision.
- `policy`: the result of a permission/safety check.
- `action`: a proposed or executed tool/action representation.
- `outcome`: an observed result of an action.
- `learning`: a bounded update derived from an observed outcome.
- `goal`: an explicit objective.
- `plan`: a proposed or accepted multi-step plan.
- `step`: one plan step.
- `concept`: an abstraction or concept node.
- `critique`: an explicit criticism of another glyph/claim.
- `inference`: a declared rule-based inference.
- `cycle`: a complete Syn agent-cycle audit anchor.

## Relations

Relations are directed.

- `derived_from`: source glyph depends on target glyph.
- `supports`: source provides support for target.
- `contradicts`: source contradicts target.
- `motivates`: source motivates target.
- `proposes`: source proposes target.
- `authorizes`: source policy glyph authorizes target action.
- `denies`: source policy glyph denies target action.
- `produces`: source action produces target outcome.
- `evaluates`: source learning/evaluation evaluates target.
- `updates`: source produces an explicit update to target.
- `supersedes`: source replaces a prior target while preserving history.
- `critiques`: source critiques target.
- `part_of`: source is part of target.
- `targets`: source targets target.
- `observes`: source explicitly observes target.

`derived_from` is the principal provenance relation used for recursive trace
queries.

## Immutability

Glyphs and edges are append-only. Corrections are represented by new glyphs and
relations such as `supersedes` or `contradicts`; prior records are not rewritten.

## Integrity

Every ledger event contains:

1. a monotonic sequence number,
2. the previous event digest,
3. its payload,
4. its own SHA-256 digest.

Therefore deletion, reordering, or modification of historical events is
detectable.

A checkpoint also exposes a Merkle root over the ledger event digests.

The current implementation is a tamper-*evident* local ledger. It is not by
itself a remote timestamp authority or hardware-backed signature system.

## Provenance versus private reasoning

Glyph Protocol records:

`inputs -> declared hypotheses -> declared decision -> policy -> action -> outcome -> learning`

It deliberately does **not** store or request hidden chain-of-thought.

A `rationale` field is an explicit model/system output intended for audit. It
must not be described as a faithful dump of internal neural reasoning.

## Missing data

Missing data must be omitted or represented explicitly as unavailable. A glyph
must never receive fabricated numerical defaults merely to satisfy a schema.

This is why historical Synergesis fields such as arbitrary symbolic frequency,
alignment and pseudo-entropy are not part of Glyph Protocol v1.

## External references

`external_refs` connect a glyph to identifiers maintained by another subsystem,
for example:

- evidence ID,
- goal ID,
- action proposal ID,
- cycle ID,
- sensor observation digest.

They allow the graph to preserve interoperability without copying entire source
documents into the audit ledger.

## Evidence minimization

The default Synergesis adapter stores source identity, metadata, and a content
digest for external evidence rather than duplicating full evidence content into
the audit graph.

This separates provenance from data retention.

## Canonical decision trace

A typical audited cycle is:

```text
Goal
  ^
  |
Observation ----> Hypothesis <---- Evidence
                       |
                    motivates
                       v
                    Decision
                       |
                    proposes
                       v
                     Action
                       ^
                       |
                 Policy authorizes/denies

Action --produces--> Outcome
Learning --evaluates--> Outcome

all components --derived_from--> Cycle
```

Exact edges may differ when no action is proposed, policy denies execution, or
no outcome exists.

## Required queries

A conforming implementation should be able to answer at minimum:

1. **Why was this decision recorded?**
   Traverse upstream `derived_from` provenance from a decision glyph.

2. **What depends on this evidence?**
   Traverse downstream provenance from an evidence glyph.

3. **Was the ledger modified?**
   Verify sequence, hash chain, payload digests, and referential integrity.

4. **What was the auditable state at checkpoint T?**
   Persist or export the checkpoint chain head and Merkle root.

## Security boundary

Glyph Protocol provides auditability. It does not grant authority.

Permissions remain outside the glyph graph and are enforced by the immutable
Synergesis `PermissionPolicy` / safety gateway. A glyph that *claims* an action
is authorized cannot authorize that action by itself.

## Interoperability

The normative machine schema is:

`glyph_protocol_v1.schema.json`

Any model or service may emit objects conforming to the schema. Synergesis still
validates authorization, provenance references and ledger integrity before
treating them as trusted system state.
