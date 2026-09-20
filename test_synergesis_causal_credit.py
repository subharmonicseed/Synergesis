from dataclasses import replace
import json
import math
import pytest
from synergesis_agent_loop_v2 import ActionProposal
from synergesis_causal_credit import CausalHypothesis, CausalModel, install_causal_credit
from test_synergesis_world_revision import setup
from test_synergesis_prediction import context, fake_reality


def configured(tmp_path, responses=((0.1, 0.9), (0.9, 0.1))):
    graph, core, world, engine = setup(tmp_path)
    a = core.remember('system', 'possible_fault', 'storage', 'operator', 0.5, 'belief:storage')
    b = core.remember('system', 'possible_fault', 'network', 'operator', 0.5, 'belief:network')
    hypotheses = tuple(CausalHypothesis(f.evidence_id, 0.5, (('check', ps[0]), ('repair', ps[1])))
                       for f, ps in zip((a, b), responses))
    model = CausalModel('file.write', 'diagnose', 'intervention', 'probe:state', 'intervention', hypotheses)
    bridge = install_causal_credit(engine=engine, core=core, models=(model,))
    return graph, core, world, engine, bridge, model


def prepare(graph, engine, intervention='check', strategy='diagnose'):
    proposal = ActionProposal.create('file.write', {'intervention': intervention},
        rationale='registered experiment', expected_outcome='effect exists', strategy_key=strategy)
    action = graph.create('action', actor='test', content={'proposal_id': proposal.proposal_id})
    prediction = engine.predict_before_action(context=context(), proposal=proposal, action_glyph_id=action.glyph_id)
    return proposal, action, prediction


def settle(graph, engine, prepared, effect, observed_intervention='check', foreign=False):
    proposal, action, _ = prepared
    parents = []
    if observed_intervention is not None:
        observation = graph.create('observation', actor='observer:probe:state', content={
            'kind': 'runtime_reality_observation', 'observer_id': 'probe:state',
            'facts': {'intervention': observed_intervention}})
        observed_action = graph.create('action', actor='test', content={}) if foreign else action
        graph.relate(observation.glyph_id, observed_action.glyph_id, 'observes', actor='SYN-REALITY')
        parents.append(observation.glyph_id)
    verdict = graph.create('decision', actor='SYN-REALITY', content={
        'kind': 'reality_verdict', 'proposal_id': proposal.proposal_id,
        'status': 'confirmed' if effect is True else 'contradicted' if effect is False else 'unverified',
        'effect_observed': effect}, derived_from=parents)
    return engine.settle(proposal=proposal, reality=fake_reality(
        proposal=proposal, verdict_glyph_id=verdict.glyph_id, effect=effect))


def receipts(graph):
    return [g for g in graph.ledger.glyphs() if g.content.get('kind') == 'causal_credit']


def test_analytic_bayes_targeted_update_and_next_prediction(tmp_path):
    graph, core, world, engine, bridge, model = configured(tmp_path)
    other = core.remember('other', 'value', 'unchanged', 'operator', 0.7)
    prepared = prepare(graph, engine)
    assert prepared[2].probability_effect_success == pytest.approx(0.5)
    settle(graph, engine, prepared, True)
    assert bridge.posterior('file.write', 'diagnose') == pytest.approx({'belief:storage': 0.1, 'belief:network': 0.9})
    assert prepare(graph, engine)[2].probability_effect_success == pytest.approx(0.82)
    assert core.memory.query(subject='other') == [other]
    assert receipts(graph)[-1].content['causal_responsibility'] == 'conditional_on_registered_models'
    assert any(f.predicate == bridge.predicate for f in core.world.snapshot().facts)
    assert core.memory.query(subject='system')[0].confidence == 0.5  # Source facts preserved.


def test_ambiguous_failure_remains_indeterminate(tmp_path):
    graph, _, _, engine, bridge, _ = configured(tmp_path, ((0.2, 0.9), (0.2, 0.1)))
    settle(graph, engine, prepare(graph, engine), False)
    assert receipts(graph)[-1].content['status'] == 'indeterminate'
    assert list(bridge.posterior('file.write', 'diagnose').values()) == [0.5, 0.5]
    settle(graph, engine, prepare(graph, engine, 'repair'), True, 'repair')
    assert bridge.posterior('file.write', 'diagnose')['belief:storage'] == pytest.approx(0.9)


@pytest.mark.parametrize('observed', [None, 'repair', 'unregistered'])
def test_unconfirmed_intervention_does_not_change_beliefs(tmp_path, observed):
    graph, _, _, engine, bridge, _ = configured(tmp_path)
    settle(graph, engine, prepare(graph, engine), True, observed)
    assert receipts(graph)[-1].content['status'] == 'intervention_unverified'
    assert list(bridge.posterior('file.write', 'diagnose').values()) == [0.5, 0.5]


def test_all_models_wrong_abstains(tmp_path):
    graph, _, _, engine, bridge, _ = configured(tmp_path, ((0., 1.), (0., 0.)))
    settle(graph, engine, prepare(graph, engine), True)
    assert receipts(graph)[-1].content['status'] == 'model_conflict'
    assert list(bridge.posterior('file.write', 'diagnose').values()) == [0.5, 0.5]


def test_unknown_effect_does_not_update(tmp_path):
    graph, _, _, engine, bridge, _ = configured(tmp_path)
    settle(graph, engine, prepare(graph, engine), None)
    assert receipts(graph)[-1].content['status'] == 'unverified'
    assert list(bridge.posterior('file.write', 'diagnose').values()) == [0.5, 0.5]


def test_foreign_observation_rejected(tmp_path):
    graph, core, _, engine, _, _ = configured(tmp_path)
    with pytest.raises(ValueError, match='another action'):
        settle(graph, engine, prepare(graph, engine), True, foreign=True)
    assert not core.memory.query(predicate='conditional_causal_posterior')


def test_restart_and_replay(tmp_path):
    graph, core, _, engine, bridge, model = configured(tmp_path)
    settlement = settle(graph, engine, prepare(graph, engine), True)
    graph2, core2, world2, engine2 = setup(tmp_path)
    restored = install_causal_credit(engine=engine2, core=core2, models=(model,))
    count = core2.memory.count()
    restored.on_prediction_settlement(settlement)
    assert core2.memory.count() == count
    assert restored.posterior('file.write', 'diagnose') == bridge.posterior('file.write', 'diagnose')


@pytest.mark.parametrize('field,value', [('brier_score', 0.9), ('observed_effect', False),
    ('prediction_id', 'foreign'), ('probability_effect_success', 0.99)])
def test_forged_settlement_rejected(tmp_path, field, value):
    graph, _, _, engine, bridge, _ = configured(tmp_path)
    settlement = settle(graph, engine, prepare(graph, engine), True)
    with pytest.raises(ValueError):
        bridge.on_prediction_settlement(replace(settlement, **{field: value}))


def test_registration_requires_grounded_candidates(tmp_path):
    graph, core, world, engine = setup(tmp_path)
    hs = tuple(CausalHypothesis(x, 0.5, (('check', 0.5),)) for x in ['missing:a', 'missing:b'])
    with pytest.raises(ValueError, match='missing'):
        install_causal_credit(engine=engine, core=core, models=(CausalModel('file.write','s','i','o','i',hs),))
    assert engine.provider is world


@pytest.mark.parametrize('p', [-0.1, 1.1, float('nan'), float('inf'), True])
def test_invalid_likelihood_rejected(p):
    hs = (CausalHypothesis('a', 0.5, (('x', p),)), CausalHypothesis('b', 0.5, (('x', 0.5),)))
    with pytest.raises(ValueError):
        CausalModel('file.write','s','i','o','i',hs)


def test_fallback_and_existing_sink_preserved(tmp_path):
    graph, core, world, engine, bridge, _ = configured(tmp_path)
    settle(graph, engine, prepare(graph, engine, strategy='other'), True)
    assert world.current_belief('file.write', 'other') is not None
    assert not receipts(graph)


def test_one_pending_and_unknown_intervention(tmp_path):
    graph, _, _, engine, _, _ = configured(tmp_path)
    with pytest.raises(ValueError, match='not registered'):
        prepare(graph, engine, 'unknown')
    prepared = prepare(graph, engine)
    with pytest.raises(ValueError, match='pending'):
        prepare(graph, engine)
    settle(graph, engine, prepared, True)
    prepare(graph, engine)


def test_real_file_observations_separate_hypotheses(tmp_path):
    graph, _, _, engine, bridge, _ = configured(tmp_path, ((0.2, 0.9), (0.2, 0.1)))
    # A controlled fixture writes actual state; independent reads supply the evidence.
    # This validates plumbing, not the likelihood model against a real population.
    state_path = tmp_path / 'observed_state.json'
    for intervention in ('check', 'repair'):
        prepared = prepare(graph, engine, intervention)
        state_path.write_text(json.dumps({'intervention': intervention, 'effect': intervention == 'repair'}))
        observed = json.loads(state_path.read_text())
        settle(graph, engine, prepared, observed['effect'], observed['intervention'])
    assert [r.content['status'] for r in receipts(graph)] == ['indeterminate', 'conditional_update']
    assert bridge.posterior('file.write', 'diagnose')['belief:storage'] == pytest.approx(0.9)


def test_old_replay_does_not_clear_new_pending(tmp_path):
    graph, _, _, engine, bridge, _ = configured(tmp_path)
    old = settle(graph, engine, prepare(graph, engine), True)
    prepare(graph, engine)
    bridge.on_prediction_settlement(old)
    with pytest.raises(ValueError, match='pending'):
        prepare(graph, engine)


def test_partial_distinguishability_preserves_equal_candidate_ratio(tmp_path):
    graph, core, world, engine = setup(tmp_path)
    hs = []
    for i, probability in enumerate((0.2, 0.2, 0.8)):
        core.remember('fault', 'candidate', str(i), 'operator', 1/3, f'belief:{i}')
        hs.append(CausalHypothesis(f'belief:{i}', 1/3, (('check', probability),)))
    model = CausalModel('file.write', 'diagnose', 'intervention', 'probe:state', 'intervention', tuple(hs))
    bridge = install_causal_credit(engine=engine, core=core, models=(model,))
    settle(graph, engine, prepare(graph, engine), True)
    weights = bridge.posterior('file.write', 'diagnose')
    assert weights['belief:0'] == weights['belief:1']
    assert weights['belief:2'] == pytest.approx(2/3)
    assert [c['disposition'] for c in receipts(graph)[-1].content['credits']] == ['weakened', 'weakened', 'strengthened']
