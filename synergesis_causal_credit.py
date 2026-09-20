"""Conditional causal credit from explicitly registered intervention models.

Candidates are mutually exclusive explanations, not arbitrary independent facts.
Likelihoods and intervention semantics are trusted configuration, never learned
from executor claims. Results are conditional on that model family, not causal
proof. Single writer; one pending prediction per model. No action authorization.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from synergesis_cognitive_core import Fact
from synergesis_prediction import ActionPrediction


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class CausalHypothesis:
    belief_evidence_id: str
    prior: float
    # Immutable pairs: intervention label, P(effect=True | hypothesis, intervention)
    responses: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class CausalModel:
    action_type: str
    strategy_key: str
    intervention_parameter: str
    observer_id: str
    observed_intervention_fact: str
    hypotheses: tuple[CausalHypothesis, ...]

    def __post_init__(self):
        for name in ('action_type', 'strategy_key', 'intervention_parameter',
                     'observer_id', 'observed_intervention_fact'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError('model names must be nonempty strings')
        if not isinstance(self.hypotheses, tuple) or not 2 <= len(self.hypotheses) <= 64:
            raise ValueError('provide 2 to 64 immutable candidate hypotheses')
        ids, labels = set(), None
        for h in self.hypotheses:
            if not h.belief_evidence_id or h.belief_evidence_id in ids:
                raise ValueError('candidate evidence IDs must be unique')
            ids.add(h.belief_evidence_id)
            if isinstance(h.prior, bool) or not math.isfinite(h.prior) or h.prior <= 0:
                raise ValueError('candidate priors must be finite and positive')
            if not isinstance(h.responses, tuple) or not h.responses:
                raise ValueError('immutable intervention responses required')
            keys = set()
            for pair in h.responses:
                if not isinstance(pair, tuple) or len(pair) != 2:
                    raise ValueError('response must be an immutable pair')
                key, p = pair
                if not isinstance(key, str) or not key or key in keys:
                    raise ValueError('intervention labels must be unique')
                if isinstance(p, bool) or not math.isfinite(p) or not 0 <= p <= 1:
                    raise ValueError('invalid response probability')
                keys.add(key)
            if labels is not None and keys != labels:
                raise ValueError('every candidate must cover the same interventions')
            labels = keys
        if not math.isclose(sum(h.prior for h in self.hypotheses), 1.0, abs_tol=1e-12):
            raise ValueError('mutually exclusive candidate priors must sum to one')

    @property
    def model_id(self):
        return 'causal-model:' + sha256(_canonical(asdict(self)).encode()).hexdigest()


class CausalCreditBridge:
    """Provider/sink wrapper. Unregistered action/strategy pairs use fallback."""
    predicate = 'conditional_causal_posterior'
    actor = 'SYN-CAUSAL-CREDIT'

    def __init__(self, *, core, prediction_ledger, fallback, models):
        self.core, self.graph = core, core.graph
        self.ledger, self.fallback = prediction_ledger, fallback
        self.models = {}
        self.pending = {}
        for model in models:
            key = (model.action_type, model.strategy_key)
            if key in self.models:
                raise ValueError('duplicate action/strategy model')
            facts = {f.evidence_id: f for f in core.memory.query()}
            if any(h.belief_evidence_id not in facts for h in model.hypotheses):
                raise ValueError('candidate belief missing from World Model')
            self.models[key] = model

    def _state(self, model):
        facts = self.core.memory.query(subject=model.model_id, predicate=self.predicate)
        if facts:
            return json.loads(facts[-1].object), facts[-1].evidence_id
        return [math.log(h.prior) for h in model.hypotheses], None

    def posterior(self, action_type, strategy_key):
        model = self.models[(action_type, strategy_key)]
        logs, _ = self._state(model)
        return {h.belief_evidence_id: math.exp(v) if v is not None else 0.0
                for h, v in zip(model.hypotheses, logs)}

    def predict(self, *, context, proposal):
        model = self.models.get((proposal.action_type, proposal.strategy_key))
        if model is None:
            return self.fallback.predict(context=context, proposal=proposal)
        if model.model_id in self.pending:
            raise ValueError('settle the pending model prediction first')
        intervention = proposal.parameters.get(model.intervention_parameter)
        if not isinstance(intervention, str) or intervention not in dict(model.hypotheses[0].responses):
            raise ValueError('intervention is not registered')
        logs, revision = self._state(model)
        probabilities = [dict(h.responses)[intervention] for h in model.hypotheses]
        mixture = sum((math.exp(v) if v is not None else 0.0) * p
                      for v, p in zip(logs, probabilities))
        prediction = ActionPrediction.create(
            proposal=proposal, probability_effect_success=min(1.0, max(0.0, mixture)),
            basis={'kind': 'registered_causal_mixture', 'model_id': model.model_id,
                   'intervention': intervention, 'log_weights': logs,
                   'base_revision': revision,
                   'belief_evidence_ids': [h.belief_evidence_id for h in model.hypotheses],
                   'success_likelihoods': probabilities})
        self.pending[model.model_id] = prediction.prediction_id
        return prediction

    def on_prediction_settlement(self, s):
        prediction = self.graph.ledger.get(s.prediction_glyph_id)
        basis = prediction.content.get('basis', {})
        if basis.get('kind') != 'registered_causal_mixture':
            return
        model = self.models.get((s.action_type, s.strategy_key))
        if model is None or basis.get('model_id') != model.model_id:
            raise ValueError('causal model identity mismatch')
        error = self.graph.ledger.get(s.learning_glyph_id)
        verdict = self.graph.ledger.get(s.reality_verdict_glyph_id)
        for field in ('prediction_id', 'proposal_id', 'action_type', 'strategy_key',
                      'probability_effect_success'):
            if prediction.content.get(field) != getattr(s, field) or error.content.get(field) != getattr(s, field):
                raise ValueError('prediction identity or probability mismatch')
        for field in ('observed_effect', 'status', 'brier_score', 'absolute_error', 'surprise_bits'):
            if error.content.get(field) != getattr(s, field):
                raise ValueError('settlement does not match error glyph')
        if error.content.get('kind') != 'prediction_error' or verdict.content.get('kind') != 'reality_verdict':
            raise ValueError('unexpected evidence type')
        parents = {e.target for e in self.graph.ledger.edges_from(error.glyph_id, relation='derived_from')}
        if not {prediction.glyph_id, verdict.glyph_id} <= parents:
            raise ValueError('missing error provenance')
        if verdict.content.get('proposal_id') != s.proposal_id:
            raise ValueError('verdict proposal mismatch')
        receipt_id = 'causal-credit:' + s.prediction_id
        receipts = self.graph.ledger.find_by_external_ref(receipt_id)
        if receipts:
            self._materialize(model, receipts[-1])
            if self.pending.get(model.model_id) == s.prediction_id:
                self.pending.pop(model.model_id, None)
            return
        logs, revision = self._state(model)
        if basis.get('base_revision') != revision or basis.get('log_weights') != logs:
            raise ValueError('stale belief snapshot; causal revision rejected')
        intervention = basis['intervention']
        likelihoods = [dict(h.responses).get(intervention) for h in model.hypotheses]
        if (None in likelihoods or likelihoods != basis.get('success_likelihoods')
                or basis.get('belief_evidence_ids') != [h.belief_evidence_id for h in model.hypotheses]):
            raise ValueError('model basis was altered')
        mixture = sum((math.exp(v) if v is not None else 0.0) * p
                      for v, p in zip(logs, likelihoods))
        if not math.isclose(s.probability_effect_success, mixture, abs_tol=1e-12):
            raise ValueError('prediction is not the registered mixture')
        if s.status == 'unscored' and (s.observed_effect is not None or verdict.content.get('effect_observed') is not None):
            raise ValueError('unscored settlement contains an observed outcome')
        status, posterior_logs = 'unverified', logs
        observed = verdict.content.get('effect_observed')
        if s.status == 'scored':
            if (type(observed) is not bool or observed != s.observed_effect
                    or verdict.content.get('status') != ('confirmed' if observed else 'contradicted')):
                raise ValueError('no consistent binary reality verdict')
            records = [r for r in self.ledger.records() if r.prediction_id == s.prediction_id]
            if len(records) != 1 or records[0].observed_effect != observed:
                raise ValueError('verified prediction ledger mismatch')
            action_ids = {e.target for e in self.graph.ledger.edges_from(prediction.glyph_id, relation='derived_from')}
            observation_values = []
            for edge in self.graph.ledger.edges_from(verdict.glyph_id, relation='derived_from'):
                observation = self.graph.ledger.get(edge.target)
                c = observation.content
                if c.get('kind') != 'runtime_reality_observation' or c.get('observer_id') != model.observer_id:
                    continue
                observed_actions = {e.target for e in self.graph.ledger.edges_from(observation.glyph_id, relation='observes')}
                if (observation.actor != 'observer:' + model.observer_id
                        or not action_ids.intersection(observed_actions)):
                    raise ValueError('intervention observation belongs to another action')
                observation_values.append(c.get('facts', {}).get(model.observed_intervention_fact))
            if not observation_values or any(v != intervention for v in observation_values):
                status = 'intervention_unverified'
            else:
                likelihoods = [p if observed else 1 - p for p in likelihoods]
                updated = [v + math.log(p) if v is not None and p > 0 else None
                           for v, p in zip(logs, likelihoods)]
                finite = [v for v in updated if v is not None]
                if not finite:
                    status = 'model_conflict'
                elif len({p for v, p in zip(logs, likelihoods) if v is not None}) == 1:
                    status = 'indeterminate'
                else:
                    maximum = max(finite)
                    norm = maximum + math.log(sum(math.exp(v - maximum) for v in finite))
                    posterior_logs = [v - norm if v is not None else None for v in updated]
                    status = 'conditional_update'
        dispositions = []
        for h, before, after in zip(model.hypotheses, logs, posterior_logs):
            prior_weight = math.exp(before) if before is not None else 0.0
            weight = math.exp(after) if after is not None else 0.0
            disposition = ('unchanged' if math.isclose(prior_weight, weight, abs_tol=1e-12)
                           else 'strengthened' if weight > prior_weight else 'weakened')
            dispositions.append({'belief_evidence_id': h.belief_evidence_id,
                                 'prior': prior_weight, 'posterior': weight,
                                 'disposition': disposition})
        candidate_ids = {h.belief_evidence_id for h in model.hypotheses}
        candidate_glyphs = tuple(self.core.ensure_fact_glyph(f).glyph_id
                                for f in self.core.memory.query() if f.evidence_id in candidate_ids)
        receipt = self.graph.create(
            'learning', actor=self.actor,
            content={'kind': 'causal_credit', 'model_id': model.model_id,
                     'prediction_id': s.prediction_id, 'status': status,
                     'causal_responsibility': 'conditional_on_registered_models' if status == 'conditional_update' else 'not_identified',
                     'belief_evidence_ids': basis['belief_evidence_ids'], 'credits': dispositions,
                     'prior_log_weights': logs, 'posterior_log_weights': posterior_logs,
                     'intervention': intervention, 'observed_effect': observed,
                     'settled_at': s.settled_at},
            external_refs=(receipt_id,), dedupe_external_ref=receipt_id,
            derived_from=(prediction.glyph_id, error.glyph_id, verdict.glyph_id, *candidate_glyphs))
        self._materialize(model, receipt)
        self.pending.pop(model.model_id, None)

    def _materialize(self, model, receipt):
        if receipt.content['status'] != 'conditional_update':
            return
        evidence_id = receipt.external_refs[0] + ':posterior'
        existing = [f for f in self.core.memory.query() if f.evidence_id == evidence_id]
        if not existing:
            # One fact stores all candidate weights atomically with respect to append.
            fact = Fact(model.model_id, self.predicate,
                        _canonical(receipt.content['posterior_log_weights']), self.actor,
                        1.0, receipt.content['settled_at'], evidence_id)
            self.core.memory.add(fact)
        else:
            fact = existing[0]
        self.core.ensure_fact_glyph(fact, derived_from=(receipt.glyph_id,))


def install_causal_credit(*, engine, core, models):
    """Attach after stack construction; existing settlement sinks remain installed."""
    if engine is None or engine.graph is not core.graph:
        raise ValueError('prediction and World Model must share their audit graph')
    if isinstance(engine.provider, CausalCreditBridge):
        raise ValueError('causal credit already installed')
    bridge = CausalCreditBridge(core=core, prediction_ledger=engine.ledger,
                               fallback=engine.provider, models=tuple(models))
    engine.provider = bridge
    engine.add_settlement_sink(bridge)
    return bridge
