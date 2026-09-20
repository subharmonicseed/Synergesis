import json
from dataclasses import replace

import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_prediction import PredictionSettlement
from synergesis_risk_learning import (
    RiskLearningEngine,
    RiskLearningPolicy,
    RiskLedger,
    RiskObservationContract,
)


def contract():
    return RiskObservationContract(
        action_type="diagnostic.run",
        strategy_key="diagnose",
        observer_id="probe:risk",
        adverse_event_fact="adverse_event",
    )


def setup(tmp_path, *, adverse_values=(False,), settlement_status="scored"):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    action = graph.create(
        "action",
        actor="ZÆL-0",
        content={
            "kind": "action_proposal",
            "proposal_id": "proposal:1",
            "action_type": "diagnostic.run",
        },
    )
    prediction = graph.create(
        "hypothesis",
        actor="SYN-PREDICT",
        content={
            "kind": "action_prediction",
            "prediction_id": "pred:1",
            "proposal_id": "proposal:1",
            "action_type": "diagnostic.run",
            "strategy_key": "diagnose",
            "probability_effect_success": 0.8,
            "basis": {
                "kind": "registered_causal_mixture",
                "model_id": "causal:model",
                "intervention": "repair",
            },
        },
        derived_from=(action.glyph_id,),
    )

    observation_ids = []
    for index, value in enumerate(adverse_values, start=1):
        observation = graph.create(
            "observation",
            actor="observer:probe:risk",
            content={
                "kind": "runtime_reality_observation",
                "observer_id": "probe:risk",
                "channel": "runtime",
                "resource": "diagnostic:1",
                "facts": {"adverse_event": value},
            },
            external_refs=(f"risk-observation:{index}",),
        )
        graph.relate(
            observation.glyph_id,
            action.glyph_id,
            "observes",
            actor="SYN-REALITY",
        )
        observation_ids.append(observation.glyph_id)

    verdict = graph.create(
        "decision",
        actor="SYN-REALITY",
        content={
            "kind": "reality_verdict",
            "proposal_id": "proposal:1",
            "action_type": "diagnostic.run",
            "status": "confirmed",
            "effect_observed": True,
        },
        derived_from=tuple(observation_ids),
    )
    learning = graph.create(
        "learning",
        actor="SYN-PREDICT",
        content={
            "kind": "prediction_error",
            "prediction_id": "pred:1",
        },
        derived_from=(prediction.glyph_id, verdict.glyph_id),
    )

    settlement = PredictionSettlement(
        prediction_id="pred:1",
        proposal_id="proposal:1",
        action_type="diagnostic.run",
        strategy_key="diagnose",
        probability_effect_success=0.8,
        observed_effect=True if settlement_status == "scored" else None,
        status=settlement_status,
        brier_score=0.04 if settlement_status == "scored" else None,
        absolute_error=0.2 if settlement_status == "scored" else None,
        surprise_bits=0.321928 if settlement_status == "scored" else None,
        reality_verdict_glyph_id=verdict.glyph_id,
        prediction_glyph_id=prediction.glyph_id,
        learning_glyph_id=learning.glyph_id,
        settled_at="2026-09-12T12:00:00+00:00",
    )
    ledger = RiskLedger(tmp_path / "risk.jsonl")
    engine = RiskLearningEngine(
        graph=graph,
        ledger=ledger,
        contracts=(contract(),),
        policy=RiskLearningPolicy(
            prior_alpha=1,
            prior_beta=1,
            half_life_events=4,
            uncertainty_margin_weight=0.5,
        ),
    )
    return graph, ledger, engine, settlement


def test_scored_adverse_event_enters_hash_chained_ledger(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(True,),
    )
    engine.on_prediction_settlement(settlement)

    records = ledger.records()
    assert len(records) == 1
    record = records[0]
    assert record.adverse_event is True
    assert record.intervention == "repair"
    assert record.observer_id == "probe:risk"
    assert ledger.verify()[0] == 1

    glyphs = [
        glyph for glyph in graph.ledger.glyphs()
        if glyph.content.get("kind") == "risk_calibration_outcome"
    ]
    assert glyphs[-1].content["status"] == "scored"
    assert glyphs[-1].content["adverse_event"] is True
    assert glyphs[-1].content["authorization_effect"] == "none"


def test_missing_adverse_fact_is_unverified_and_not_scored(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(False,),
    )
    # Remove the fact by reconstructing a fresh setup with non-bool value.
    observation = [
        g for g in graph.ledger.glyphs()
        if g.content.get("kind") == "runtime_reality_observation"
    ][0]
    observation.content["facts"]["adverse_event"] = None

    engine.on_prediction_settlement(settlement)
    assert ledger.records() == ()
    outcome = [
        g for g in graph.ledger.glyphs()
        if g.content.get("kind") == "risk_calibration_outcome"
    ][-1]
    assert outcome.content["status"] == "unverified_risk_outcome"


def test_conflicting_runtime_risk_observations_do_not_create_record(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(True, False),
    )
    engine.on_prediction_settlement(settlement)
    assert ledger.records() == ()
    outcome = [
        g for g in graph.ledger.glyphs()
        if g.content.get("kind") == "risk_calibration_outcome"
    ][-1]
    assert outcome.content["status"] == "unverified_risk_outcome"


def test_unscored_prediction_does_not_train_risk_model(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(True,),
        settlement_status="unscored",
    )
    engine.on_prediction_settlement(settlement)
    assert ledger.records() == ()
    assert not any(
        g.content.get("kind") == "risk_calibration_outcome"
        for g in graph.ledger.glyphs()
    )


def test_replay_is_idempotent(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(True,),
    )
    engine.on_prediction_settlement(settlement)
    engine.on_prediction_settlement(settlement)
    assert len(ledger.records()) == 1


def test_risk_estimate_separates_mean_from_conservative_margin(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(False,),
    )
    engine.on_prediction_settlement(settlement)
    estimate = engine.estimate(
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention="repair",
    )
    assert estimate.observations == 1
    assert 0 < estimate.posterior_mean < 0.5
    assert estimate.conservative_risk > estimate.posterior_mean
    assert estimate.conservative_risk <= 1.0


def test_empty_history_has_no_learned_risk(tmp_path):
    graph, ledger, engine, settlement = setup(tmp_path)
    estimate = engine.estimate(
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention="never-observed",
    )
    assert estimate.observations == 0
    assert estimate.posterior_mean is None
    assert estimate.conservative_risk is None


def test_risk_ledger_detects_tampering(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(True,),
    )
    engine.on_prediction_settlement(settlement)
    raw = ledger.path.read_text(encoding="utf-8")
    ledger.path.write_text(
        raw.replace('"adverse_event":true', '"adverse_event":false'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.verify()


def test_contract_and_policy_validation(tmp_path):
    with pytest.raises(ValueError):
        RiskObservationContract("", "s", "o", "f")
    with pytest.raises(ValueError):
        RiskLearningPolicy(prior_alpha=0)
    with pytest.raises(ValueError):
        RiskLearningPolicy(uncertainty_margin_weight=-1)

    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger = RiskLedger(tmp_path / "risk.jsonl")
    c = contract()
    with pytest.raises(ValueError, match="duplicate"):
        RiskLearningEngine(
            graph=graph,
            ledger=ledger,
            contracts=(c, c),
        )


def test_observation_from_another_action_is_rejected(tmp_path):
    graph, ledger, engine, settlement = setup(
        tmp_path,
        adverse_values=(True,),
    )
    other = graph.create(
        "action",
        actor="ZÆL-0",
        content={"kind": "other_action"},
    )
    observation = [
        g for g in graph.ledger.glyphs()
        if g.content.get("kind") == "runtime_reality_observation"
    ][0]
    # Add a second observes edge but remove the correct one is not supported by
    # append-only graph; instead forge a settlement whose prediction points to a
    # different action, making the risk observation unrelated.
    prediction = graph.ledger.get(settlement.prediction_glyph_id)
    forged = graph.create(
        "hypothesis",
        actor="SYN-PREDICT",
        content=dict(prediction.content),
        derived_from=(other.glyph_id,),
    )
    forged_settlement = replace(
        settlement,
        prediction_glyph_id=forged.glyph_id,
    )
    with pytest.raises(ValueError, match="another action"):
        engine.on_prediction_settlement(forged_settlement)
