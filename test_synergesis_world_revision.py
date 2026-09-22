from dataclasses import replace
import pytest
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_prediction import EmpiricalPredictionProvider, PredictionEngine, PredictionLedger
from synergesis_world_revision import WorldModelPredictionBridge
from test_synergesis_prediction import proposal, context, fake_reality


def setup(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / 'glyphs.jsonl'))
    core = GlyphAuditedCognitiveCore(tmp_path / 'memory.jsonl', graph=graph)
    estimator = EmpiricalPredictionProvider(ledger=PredictionLedger(tmp_path / 'predictions.jsonl'))
    bridge = WorldModelPredictionBridge(core=core, estimator=estimator)
    engine = PredictionEngine(graph=graph, provider=bridge, ledger=estimator.ledger,
                              settlement_sinks=(bridge,))
    return graph, core, bridge, engine


def cycle(graph, engine, effect, strategy='s'):
    p = proposal(strategy=strategy)
    action = graph.create('action', actor='test', content={'proposal_id': p.proposal_id})
    prediction = engine.predict_before_action(context=context(), proposal=p, action_glyph_id=action.glyph_id)
    verdict = graph.create('decision', actor='SYN-REALITY', content={
        'kind': 'reality_verdict', 'proposal_id': p.proposal_id,
        'action_type': p.action_type, 'resource': 'action:file.write',
        'effect_observed': effect,
        'status': 'confirmed' if effect is True else 'contradicted' if effect is False else 'unverified'})
    graph.relate(verdict.glyph_id, action.glyph_id, 'evaluates', actor='SYN-REALITY')
    settlement = engine.settle(proposal=p, reality=fake_reality(
        proposal=p, verdict_glyph_id=verdict.glyph_id, effect=effect))
    return prediction, settlement


def test_revision_changes_next_prediction_and_preserves_history(tmp_path):
    graph, core, bridge, engine = setup(tmp_path)
    prior, settled = cycle(graph, engine, True)
    updated = bridge.current_belief('file.write', 's')
    assert float(updated.object) > prior.probability_effect_success
    next_prediction, _ = cycle(graph, engine, False)
    assert next_prediction.probability_effect_success == float(updated.object)
    assert float(bridge.current_belief('file.write', 's').object) < float(updated.object)
    assert updated in core.world.snapshot().facts
    revision = [g for g in graph.ledger.glyphs() if g.content.get('kind') == 'world_model_revision'][0]
    assert revision.content['causal_responsibility'] == 'not_identified'
    parents = {e.target for e in graph.ledger.edges_from(revision.glyph_id)}
    assert {settled.learning_glyph_id, settled.reality_verdict_glyph_id, settled.prediction_glyph_id} <= parents


def test_unverified_has_no_revision(tmp_path):
    graph, core, bridge, engine = setup(tmp_path)
    cycle(graph, engine, None)
    assert not any(g.content.get('kind') == 'world_model_revision' for g in graph.ledger.glyphs())


def test_replay_after_restart_is_idempotent(tmp_path):
    graph, core, bridge, engine = setup(tmp_path)
    _, settlement = cycle(graph, engine, True)
    count = core.memory.count()
    _, core2, bridge2, _ = setup(tmp_path)
    bridge2.on_prediction_settlement(settlement)
    assert core2.memory.count() == count
    assert bridge2.current_belief('file.write', 's') == bridge.current_belief('file.write', 's')


@pytest.mark.parametrize('field,value', [('proposal_id', 'other'), ('observed_effect', False),
                                         ('probability_effect_success', 0.99), ('brier_score', 0.99)])
def test_mismatched_settlement_rejected(tmp_path, field, value):
    graph, core, bridge, engine = setup(tmp_path)
    _, settlement = cycle(graph, engine, True)
    count = core.memory.count()
    with pytest.raises(ValueError):
        bridge.on_prediction_settlement(replace(settlement, **{field: value}))
    assert core.memory.count() == count


def test_unrelated_facts_and_strategy_unchanged(tmp_path):
    graph, core, bridge, engine = setup(tmp_path)
    other = core.remember('server', 'location', 'local', 'operator', 0.8)
    cycle(graph, engine, True, strategy='a')
    belief_a = bridge.current_belief('file.write', 'a')
    cycle(graph, engine, False, strategy='b')
    assert bridge.current_belief('file.write', 'a') == belief_a
    assert core.memory.query(subject='server') == [other]
