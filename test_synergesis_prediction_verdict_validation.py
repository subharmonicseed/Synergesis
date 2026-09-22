import pytest

from synergesis_prediction import PredictionEngine, PredictionLedger, StaticPredictionProvider
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from test_synergesis_prediction import context, fake_reality, proposal


def setup_engine(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    engine = PredictionEngine(
        graph=graph, provider=StaticPredictionProvider(0.8), ledger=ledger,
    )
    return graph, ledger, engine


def prepared(tmp_path):
    graph, ledger, engine = setup_engine(tmp_path)
    p = proposal()
    action = graph.create(
        "action", actor="executor", content={"proposal_id": p.proposal_id, "action_type": p.action_type},
        external_refs=(p.proposal_id,),
    )
    engine.predict_before_action(context=context(), proposal=p, action_glyph_id=action.glyph_id)
    return graph, ledger, engine, p, action


def test_foreign_or_malformed_verdict_is_rejected_before_learning(tmp_path):
    graph, ledger, engine, p, action = prepared(tmp_path)
    verdict = graph.create("decision", actor="untrusted", content={"kind": "other"})
    graph.relate(verdict.glyph_id, action.glyph_id, "evaluates", actor="untrusted")
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    with pytest.raises(ValueError, match="reality verdict"):
        engine.settle(proposal=p, reality=reality)
    assert not ledger.records()
    assert not [g for g in graph.ledger.glyphs() if g.glyph_type == "learning"]


def test_verdict_must_evaluate_prediction_action(tmp_path):
    graph, ledger, engine, p, action = prepared(tmp_path)
    foreign = graph.create("action", actor="executor", content={"proposal_id": "foreign"})
    verdict = graph.create("decision", actor="untrusted", content={
        "kind": "reality_verdict", "proposal_id": p.proposal_id,
        "action_type": p.action_type, "status": "confirmed", "effect_observed": True,
    })
    graph.relate(verdict.glyph_id, foreign.glyph_id, "evaluates", actor="untrusted")
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    with pytest.raises(ValueError, match="evaluates"):
        engine.settle(proposal=p, reality=reality)


def test_unverified_verdict_cannot_claim_true_effect(tmp_path):
    graph, ledger, engine, p, action = prepared(tmp_path)
    verdict = graph.create("decision", actor="untrusted", content={
        "kind": "reality_verdict", "proposal_id": p.proposal_id,
        "action_type": p.action_type, "status": "unverified", "effect_observed": True,
    })
    graph.relate(verdict.glyph_id, action.glyph_id, "evaluates", actor="untrusted")
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    with pytest.raises(ValueError, match="effect/status"):
        engine.settle(proposal=p, reality=reality)


@pytest.mark.parametrize('field,value', [
    ('proposal_id', 'foreign'), ('action_type', 'api.set'),
    ('effect_observed', 1), ('status', 'unknown'),
])
def test_verdict_contract_rejects_invalid_fields_without_writes(tmp_path, field, value):
    graph, ledger, engine, p, action = prepared(tmp_path)
    content = {'kind': 'reality_verdict', 'proposal_id': p.proposal_id,
               'action_type': p.action_type, 'status': 'confirmed', 'effect_observed': True}
    content[field] = value
    verdict = graph.create('decision', actor='SYN-REALITY', content=content)
    graph.relate(verdict.glyph_id, action.glyph_id, 'evaluates', actor='test')
    before = graph.ledger.verify().event_count
    with pytest.raises(ValueError):
        engine.settle(proposal=p, reality=fake_reality(
            proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True))
    assert graph.ledger.verify().event_count == before
    assert not ledger.records()


def test_observer_conflict_remains_unscored_after_restart(tmp_path):
    from dataclasses import replace
    graph, ledger, engine, p, action = prepared(tmp_path)
    verdict = graph.create('decision', actor='SYN-REALITY', content={
        'kind': 'reality_verdict', 'proposal_id': p.proposal_id,
        'action_type': p.action_type, 'status': 'observer_conflict', 'effect_observed': None})
    graph.relate(verdict.glyph_id, action.glyph_id, 'evaluates', actor='test')
    reality = replace(fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=None),
                      status='observer_conflict')
    first = engine.settle(proposal=p, reality=reality)
    _, new_ledger, rebuilt = setup_engine(tmp_path)
    assert rebuilt.settle(proposal=p, reality=reality) == first
    assert first.status == 'unscored'
    assert not new_ledger.records()


@pytest.mark.parametrize('field,value', [
    ('brier_score', .99), ('observed_effect', False),
    ('probability_effect_success', .3), ('strategy_key', 'foreign'),
])
def test_recovery_rejects_inconsistent_learning_before_calibration_repair(tmp_path, field, value):
    graph, ledger, engine, p, action = prepared(tmp_path)
    verdict = graph.create('decision', actor='SYN-REALITY', content={
        'kind': 'reality_verdict', 'proposal_id': p.proposal_id,
        'action_type': p.action_type, 'status': 'confirmed', 'effect_observed': True})
    graph.relate(verdict.glyph_id, action.glyph_id, 'evaluates', actor='test')
    prediction = next(g for g in graph.ledger.glyphs() if g.content.get('kind') == 'action_prediction')
    import math
    content = {'kind': 'prediction_error', 'prediction_id': prediction.content['prediction_id'],
               'proposal_id': p.proposal_id, 'action_type': p.action_type, 'strategy_key': p.strategy_key,
               'probability_effect_success': .8, 'observed_effect': True, 'status': 'scored',
               'brier_score': (.8 - 1) ** 2, 'absolute_error': abs(.8 - 1),
               'surprise_bits': -math.log2(.8), 'settled_at': prediction.created_at}
    content[field] = value
    graph.create('learning', actor='test', content=content,
                 derived_from=(prediction.glyph_id, verdict.glyph_id))
    with pytest.raises(ValueError):
        setup_engine(tmp_path)
    assert not ledger.records()
