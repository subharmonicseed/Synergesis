from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
import pytest
from synergesis_prediction import PredictionEngine, PredictionLedger, StaticPredictionProvider

from test_synergesis_prediction import context, fake_reality, proposal


class Sink:
    def __init__(self):
        self.values = []

    def on_prediction_settlement(self, settlement):
        self.values.append(settlement)


def setup(tmp_path, sink=()):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    engine = PredictionEngine(
        graph=graph,
        provider=StaticPredictionProvider(0.8),
        ledger=ledger,
        settlement_sinks=sink,
    )
    return graph, ledger, engine


def prepare(graph, engine, p):
    action = graph.create(
        "action", actor="test", content={"proposal_id": p.proposal_id},
    )
    engine.predict_before_action(
        context=context(), proposal=p, action_glyph_id=action.glyph_id,
    )
    verdict = graph.create("decision", actor="SYN-REALITY", content={"kind": "reality_verdict"})
    return verdict


def test_rebuild_recovers_prediction_and_settlement(tmp_path):
    graph, ledger, engine = setup(tmp_path)
    p = proposal()
    verdict = prepare(graph, engine, p)
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    first = engine.settle(proposal=p, reality=reality)

    rebuilt = PredictionEngine(
        graph=graph, provider=StaticPredictionProvider(0.8), ledger=ledger,
    )
    replay = rebuilt.settle(proposal=p, reality=reality)
    assert replay == first
    assert len(ledger.records()) == 1
    assert len([g for g in graph.ledger.glyphs() if g.glyph_type == "learning"]) == 1


def test_identical_replay_calls_sink_once_and_conflict_is_rejected(tmp_path):
    sink = Sink()
    graph, ledger, engine = setup(tmp_path, (sink,))
    p = proposal()
    verdict = prepare(graph, engine, p)
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    first = engine.settle(proposal=p, reality=reality)
    assert engine.settle(proposal=p, reality=reality) == first
    assert sink.values == [first]
    other = graph.create("decision", actor="SYN-REALITY", content={"kind": "reality_verdict"})
    conflicting = fake_reality(proposal=p, verdict_glyph_id=other.glyph_id, effect=False)
    import pytest
    with pytest.raises(ValueError, match="conflicting"):
        engine.settle(proposal=p, reality=conflicting)
    assert len(ledger.records()) == 1


def test_rebuild_rejects_prediction_with_wrong_action_link(tmp_path):
    graph, ledger, engine = setup(tmp_path)
    p = proposal()
    verdict = prepare(graph, engine, p)
    # Corrupt the durable relationship by adding a second action parent.  A
    # restarted engine must fail closed instead of guessing which action ran.
    foreign = graph.create("action", actor="test", content={"proposal_id": "foreign"})
    pred = graph.ledger.find_by_external_ref(
        next(g.content["prediction_id"] for g in graph.ledger.glyphs() if g.glyph_type == "hypothesis"),
        glyph_type="hypothesis",
    )[0]
    graph.relate(pred.glyph_id, foreign.glyph_id, "derived_from", actor="test")
    import pytest
    with pytest.raises(ValueError, match="action link"):
        PredictionEngine(graph=graph, provider=StaticPredictionProvider(0.8), ledger=ledger)


def test_pending_prediction_survives_fresh_graph_and_engine(tmp_path):
    graph, ledger, engine = setup(tmp_path)
    p = proposal()
    verdict = prepare(graph, engine, p)
    sink = Sink()
    graph2, ledger2, rebuilt = setup(tmp_path, (sink,))
    settled = rebuilt.settle(proposal=p, reality=fake_reality(
        proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True))
    assert settled.probability_effect_success == 0.8
    assert len(ledger2.records()) == 1
    assert sink.values == [settled]


def test_completed_delivery_survives_restart_and_late_sink_registration(tmp_path):
    sink = Sink()
    graph, ledger, engine = setup(tmp_path, (sink,))
    p = proposal()
    verdict = prepare(graph, engine, p)
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    first = engine.settle(proposal=p, reality=reality)
    graph2, ledger2, rebuilt = setup(tmp_path)
    new_sink = Sink()
    rebuilt.add_settlement_sink(new_sink)
    assert rebuilt.settle(proposal=p, reality=reality) == first
    assert new_sink.values == []
    assert len(ledger2.records()) == 1


def test_retry_prediction_preserves_original_for_same_action(tmp_path):
    graph, ledger, engine = setup(tmp_path)
    p = proposal()
    action = graph.create('action', actor='test', content={'proposal_id': p.proposal_id})
    first = engine.predict_before_action(context=context(), proposal=p, action_glyph_id=action.glyph_id)
    engine.provider = StaticPredictionProvider(0.1)
    assert engine.predict_before_action(context=context(), proposal=p, action_glyph_id=action.glyph_id) == first
    assert len([g for g in graph.ledger.glyphs() if g.content.get('kind') == 'action_prediction']) == 1


def test_callback_error_does_not_repeat_uncertain_side_effect(tmp_path):
    class FailingSink(Sink):
        def on_prediction_settlement(self, settlement):
            super().on_prediction_settlement(settlement)
            raise OSError('after side effect')
    sink = FailingSink()
    graph, ledger, engine = setup(tmp_path, (sink,))
    p = proposal()
    verdict = prepare(graph, engine, p)
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    with pytest.raises(OSError):
        engine.settle(proposal=p, reality=reality)
    with pytest.raises(RuntimeError, match='uncertain'):
        engine.settle(proposal=p, reality=reality)
    graph2, ledger2, rebuilt = setup(tmp_path, (sink,))
    with pytest.raises(RuntimeError, match='uncertain'):
        rebuilt.settle(proposal=p, reality=reality)
    assert len(sink.values) == 1
    assert len(ledger2.records()) == 1


@pytest.mark.parametrize('restart', [False, True])
def test_retry_repairs_failed_calibration_append(tmp_path, monkeypatch, restart):
    graph, ledger, engine = setup(tmp_path)
    p = proposal()
    verdict = prepare(graph, engine, p)
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    append = ledger.append
    def fail(_):
        raise OSError('disk write')
    monkeypatch.setattr(ledger, 'append', fail)
    with pytest.raises(OSError):
        engine.settle(proposal=p, reality=reality)
    if restart:
        graph, ledger, engine = setup(tmp_path)
    else:
        monkeypatch.setattr(ledger, 'append', append)
    engine.settle(proposal=p, reality=reality)
    assert len(ledger.records()) == 1
    assert len([g for g in graph.ledger.glyphs() if g.content.get('kind') == 'prediction_error']) == 1


def test_foreign_reality_identity_is_rejected_before_learning(tmp_path):
    from dataclasses import replace
    graph, ledger, engine = setup(tmp_path)
    p = proposal()
    verdict = prepare(graph, engine, p)
    reality = fake_reality(proposal=p, verdict_glyph_id=verdict.glyph_id, effect=True)
    with pytest.raises(ValueError, match='identity'):
        engine.settle(proposal=p, reality=replace(reality, proposal_id='foreign'))
    assert not ledger.records()
    assert not [g for g in graph.ledger.glyphs() if g.content.get('kind') == 'prediction_error']
