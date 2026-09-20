"""Audited empirical belief revisions; predictive dependency is not causal proof.

Single-writer, like SemanticMemory. Historical estimates remain in snapshots;
current_belief returns the latest estimate for an action/strategy pair.
Only beliefs actually used by this provider are eligible for revision.
"""
from __future__ import annotations

import json
from hashlib import sha256

from synergesis_cognitive_core import Fact
from synergesis_prediction import ActionPrediction, EmpiricalPredictionProvider


class WorldModelPredictionBridge:
    predicate = "estimated_effect_success_probability"
    actor = "SYN-WORLD-REVISION"

    def __init__(self, *, core, estimator: EmpiricalPredictionProvider):
        self.core = core
        self.graph = core.graph
        self.estimator = estimator

    @staticmethod
    def subject(action_type, strategy_key):
        key = json.dumps([action_type, strategy_key], separators=(",", ":"))
        return "action-belief:" + sha256(key.encode()).hexdigest()

    def current_belief(self, action_type, strategy_key):
        facts = self.core.memory.query(
            subject=self.subject(action_type, strategy_key), predicate=self.predicate)
        return facts[-1] if facts else None

    def _record(self, *, evidence_id, action_type, strategy_key, probability,
                observed_at, parents, kind, details):
        existing = [f for f in self.core.memory.query() if f.evidence_id == evidence_id]
        if existing:
            fact = existing[0]
            return fact, self.core.ensure_fact_glyph(fact)
        previous = self.current_belief(action_type, strategy_key)
        trace = self.graph.create(
            "learning" if kind == "world_model_revision" else "hypothesis",
            actor=self.actor,
            content={"kind": kind, "action_type": action_type,
                     "strategy_key": strategy_key, "probability": probability,
                     "supersedes_evidence_id": previous.evidence_id if previous else None,
                     "attribution": "predictive_dependency_only",
                     "causal_responsibility": "not_identified", **details},
            external_refs=(evidence_id + ":trace",),
            derived_from=tuple(parents), dedupe_external_ref=evidence_id + ":trace")
        fact = Fact(self.subject(action_type, strategy_key), self.predicate,
                    repr(probability), self.actor, 1.0, observed_at, evidence_id)
        # Confidence describes the recorded estimate, not certainty of success.
        self.core.memory.add(fact)
        glyph = self.core.ensure_fact_glyph(fact, derived_from=(trace.glyph_id,))
        return fact, glyph

    def predict(self, *, context, proposal):
        prediction = self.estimator.predict(context=context, proposal=proposal)
        fact, glyph = self._record(
            evidence_id="belief-input:" + prediction.prediction_id,
            action_type=proposal.action_type, strategy_key=proposal.strategy_key,
            probability=prediction.probability_effect_success,
            observed_at=prediction.created_at, parents=(),
            kind="world_model_prediction_basis", details={"estimator": dict(prediction.basis)})
        return ActionPrediction.create(
            proposal=proposal,
            probability_effect_success=prediction.probability_effect_success,
            basis={**prediction.basis, "world_belief_evidence_id": fact.evidence_id,
                   "world_belief_glyph_id": glyph.glyph_id})

    def on_prediction_settlement(self, settlement):
        if settlement.status != "scored":
            return
        prediction = self.graph.ledger.get(settlement.prediction_glyph_id)
        error = self.graph.ledger.get(settlement.learning_glyph_id)
        verdict = self.graph.ledger.get(settlement.reality_verdict_glyph_id)
        for glyph in (prediction, error, verdict):
            if glyph.content.get("proposal_id") != settlement.proposal_id:
                raise ValueError("revision provenance: proposal mismatch")
        if (verdict.content.get("kind") != "reality_verdict"
                or verdict.content.get("status") in {"unverified", "observer_conflict"}
                or type(verdict.content.get("effect_observed")) is not bool
                or verdict.content["effect_observed"] != settlement.observed_effect):
            raise ValueError("revision requires a binary independent reality verdict")
        if (error.content.get("kind") != "prediction_error"
                or error.content.get("prediction_id") != settlement.prediction_id
                or prediction.content.get("prediction_id") != settlement.prediction_id):
            raise ValueError("revision prediction identity mismatch")
        for field in ("action_type", "strategy_key", "probability_effect_success"):
            if prediction.content.get(field) != getattr(settlement, field):
                raise ValueError("prediction content mismatch")
        for field in ("action_type", "strategy_key", "probability_effect_success",
                      "observed_effect", "status", "brier_score", "absolute_error", "surprise_bits"):
            if error.content.get(field) != getattr(settlement, field):
                raise ValueError("prediction error content mismatch")
        parents = {e.target for e in self.graph.ledger.edges_from(error.glyph_id, relation="derived_from")}
        if not {prediction.glyph_id, verdict.glyph_id} <= parents:
            raise ValueError("prediction error provenance edges missing")
        basis = prediction.content.get("basis", {})
        evidence_id = basis.get("world_belief_evidence_id")
        if evidence_id is None:
            return  # Another provider supplied no explicit world-model dependency.
        facts = [f for f in self.core.memory.query() if f.evidence_id == evidence_id]
        if len(facts) != 1:
            raise ValueError("unknown prediction belief")
        fact = facts[0]
        if (fact.subject != self.subject(settlement.action_type, settlement.strategy_key)
                or fact.predicate != self.predicate
                or float(fact.object) != settlement.probability_effect_success):
            raise ValueError("prediction belief mismatch")
        belief_glyph = self.graph.ledger.get(basis["world_belief_glyph_id"])
        if fact.evidence_id not in belief_glyph.external_refs:
            raise ValueError("belief glyph identity mismatch")
        records = self.estimator.ledger.records()
        matches = [r for r in records if r.prediction_id == settlement.prediction_id]
        if len(matches) != 1 or matches[0].observed_effect != settlement.observed_effect:
            raise ValueError("settlement absent or duplicated in verified prediction ledger")
        # Replaying an old settlement cannot overwrite a newer estimate.
        revision_id = "belief-revision:" + settlement.prediction_id
        if any(f.evidence_id == revision_id for f in self.core.memory.query()):
            return
        matching = [r for r in records if r.action_type == settlement.action_type
                    and r.strategy_key == settlement.strategy_key]
        if matches[0].sequence != matching[-1].sequence:
            raise ValueError("out-of-order belief revision")
        probability, successes, failures = self.estimator._estimate(
            matching, current_sequence=len(records) + 1)
        self._record(
            evidence_id=revision_id, action_type=settlement.action_type,
            strategy_key=settlement.strategy_key, probability=probability,
            observed_at=settlement.settled_at,
            parents=(settlement.prediction_glyph_id, settlement.learning_glyph_id,
                     settlement.reality_verdict_glyph_id, basis["world_belief_glyph_id"]),
            kind="world_model_revision",
            details={"prediction_id": settlement.prediction_id,
                     "tested_belief_evidence_id": evidence_id,
                     "previous_probability": settlement.probability_effect_success,
                     "observed_effect": settlement.observed_effect,
                     "brier_score": settlement.brier_score,
                     "weighted_success": successes, "weighted_failure": failures})
