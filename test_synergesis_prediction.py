from datetime import datetime, timezone
from pathlib import Path

import pytest

from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentContext,
    AgentObservation,
    Goal,
)
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_prediction import (
    ActionPrediction,
    EmpiricalPredictionProvider,
    PredictionAuditService,
    PredictionEngine,
    PredictionLedger,
    PredictionSettlement,
    StaticPredictionProvider,
)
from synergesis_reality import RealityAssessment


def proposal(*, strategy="s"):
    return ActionProposal.create(
        "file.write",
        {"path": "x.txt", "content": "x"},
        rationale="prediction test",
        expected_outcome="effect exists",
        strategy_key=strategy,
    )


def context():
    return AgentContext(
        goal=Goal.create("test prediction"),
        observation=AgentObservation("test", {"x": 1}, "user"),
        facts=(),
        gaps=(),
        evidence=(),
    )


def fake_reality(
    *,
    proposal,
    verdict_glyph_id,
    effect,
):
    effective = ActionResult(
        proposal.action_type,
        bool(effect) if effect is not None else False,
        {},
        None if effect else "not_observed",
    )
    if effect is None:
        effective = ActionResult(
            proposal.action_type,
            False,
            {},
            "unverified",
        )
    return RealityAssessment(
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        resource="action:file.write",
        status="confirmed" if effect is True else "contradicted" if effect is False else "unverified",
        effect_observed=effect,
        executor_claim_matches_reality=True if effect is not None else None,
        raw_result=ActionResult(proposal.action_type, bool(effect), {}),
        effective_result=effective,
        observer_evaluations=(),
        observation_glyph_ids=(),
        executor_outcome_glyph_id="g:executor",
        verdict_glyph_id=verdict_glyph_id,
        effective_outcome_glyph_id="g:effective",
    )


def engine(tmp_path, probability):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    return (
        graph,
        ledger,
        PredictionEngine(
            graph=graph,
            provider=StaticPredictionProvider(probability),
            ledger=ledger,
        ),
    )


def prepare(graph, engine, p):
    action = graph.create(
        "action",
        actor="ZÆL-0",
        content={"action_type": p.action_type},
        external_refs=(p.proposal_id,),
    )
    prediction = engine.predict_before_action(
        context=context(),
        proposal=p,
        action_glyph_id=action.glyph_id,
    )
    verdict = graph.create(
        "decision",
        actor="SYN-REALITY",
        content={"kind": "reality_verdict"},
        derived_from=(action.glyph_id,),
    )
    return prediction, verdict


def test_brier_score_for_success_is_exact(tmp_path):
    graph, ledger, prediction_engine = engine(tmp_path, 0.8)
    p = proposal()
    prediction, verdict = prepare(graph, prediction_engine, p)
    settlement = prediction_engine.settle(
        proposal=p,
        reality=fake_reality(
            proposal=p,
            verdict_glyph_id=verdict.glyph_id,
            effect=True,
        ),
    )
    assert settlement.status == "scored"
    assert settlement.brier_score == pytest.approx(0.04)
    assert settlement.absolute_error == pytest.approx(0.2)
    assert settlement.observed_effect is True


def test_brier_score_for_failure_is_exact(tmp_path):
    graph, ledger, prediction_engine = engine(tmp_path, 0.8)
    p = proposal()
    prediction, verdict = prepare(graph, prediction_engine, p)
    settlement = prediction_engine.settle(
        proposal=p,
        reality=fake_reality(
            proposal=p,
            verdict_glyph_id=verdict.glyph_id,
            effect=False,
        ),
    )
    assert settlement.brier_score == pytest.approx(0.64)
    assert settlement.absolute_error == pytest.approx(0.8)
    assert settlement.observed_effect is False


def test_unverified_reality_does_not_poison_calibration_ledger(tmp_path):
    graph, ledger, prediction_engine = engine(tmp_path, 0.7)
    p = proposal()
    _, verdict = prepare(graph, prediction_engine, p)
    settlement = prediction_engine.settle(
        proposal=p,
        reality=fake_reality(
            proposal=p,
            verdict_glyph_id=verdict.glyph_id,
            effect=None,
        ),
    )
    assert settlement.status == "unscored"
    assert settlement.brier_score is None
    assert ledger.records() == ()


def test_prediction_is_recorded_as_auditable_hypothesis(tmp_path):
    graph, ledger, prediction_engine = engine(tmp_path, 0.6)
    p = proposal()
    prediction, verdict = prepare(graph, prediction_engine, p)
    glyph = graph.ledger.find_by_external_ref(
        prediction.prediction_id,
        glyph_type="hypothesis",
    )[-1]
    assert glyph.content["kind"] == "action_prediction"
    assert glyph.content["probability_effect_success"] == pytest.approx(0.6)


def test_prediction_error_is_learning_glyph_linked_to_reality(tmp_path):
    graph, ledger, prediction_engine = engine(tmp_path, 0.6)
    p = proposal()
    prediction, verdict = prepare(graph, prediction_engine, p)
    settlement = prediction_engine.settle(
        proposal=p,
        reality=fake_reality(
            proposal=p,
            verdict_glyph_id=verdict.glyph_id,
            effect=True,
        ),
    )
    learning = graph.ledger.get(settlement.learning_glyph_id)
    assert learning.glyph_type == "learning"
    assert learning.content["kind"] == "prediction_error"
    upstream = graph.upstream(learning.glyph_id, max_depth=3)
    ids = {g.glyph_id for g in upstream.glyphs}
    assert settlement.prediction_glyph_id in ids
    assert verdict.glyph_id in ids


def scored_settlement(p, probability, observed, n):
    outcome = 1.0 if observed else 0.0
    brier = (probability - outcome) ** 2
    absolute = abs(probability - outcome)
    import math
    surprise = -math.log2(
        max(probability if observed else 1.0 - probability, 1e-12)
    )
    return PredictionSettlement(
        prediction_id=f"pred:{n}",
        proposal_id=f"proposal:{n}",
        action_type=p.action_type,
        strategy_key=p.strategy_key,
        probability_effect_success=probability,
        observed_effect=observed,
        status="scored",
        brier_score=brier,
        absolute_error=absolute,
        surprise_bits=surprise,
        reality_verdict_glyph_id=f"g:v{n}",
        prediction_glyph_id=f"g:p{n}",
        learning_glyph_id=f"g:l{n}",
        settled_at=datetime.now(timezone.utc).isoformat(),
    )


def test_empirical_provider_learns_verified_success_rate(tmp_path):
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    p = proposal(strategy="adaptive")
    for i, observed in enumerate([True, True, True, False], start=1):
        ledger.append(scored_settlement(p, 0.5, observed, i))

    provider = EmpiricalPredictionProvider(
        ledger=ledger,
        prior_alpha=1,
        prior_beta=1,
        half_life_events=1e9,
    )
    pred = provider.predict(context=context(), proposal=p)
    # Beta(1+3, 1+1) -> 4/6
    assert pred.probability_effect_success == pytest.approx(4 / 6, rel=1e-6)
    assert pred.basis["scope"] == "action_and_strategy"


def test_recency_weighting_can_reverse_old_belief(tmp_path):
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    p = proposal(strategy="changing-world")

    # Old regime: repeated failure.
    n = 0
    for _ in range(8):
        n += 1
        ledger.append(scored_settlement(p, 0.5, False, n))

    provider = EmpiricalPredictionProvider(
        ledger=ledger,
        prior_alpha=1,
        prior_beta=1,
        half_life_events=2.0,
    )
    before = provider.predict(context=context(), proposal=p)

    # New regime: repeated verified success.
    for _ in range(8):
        n += 1
        ledger.append(scored_settlement(p, 0.5, True, n))

    after = provider.predict(context=context(), proposal=p)
    assert after.probability_effect_success > before.probability_effect_success
    assert after.probability_effect_success > 0.7


def test_prediction_stats_keep_calibration_separate_from_success(tmp_path):
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    p = proposal()
    ledger.append(scored_settlement(p, 0.9, True, 1))
    ledger.append(scored_settlement(p, 0.9, False, 2))

    stats = ledger.stats(
        action_type=p.action_type,
        strategy_key=p.strategy_key,
    )
    assert stats.observations == 2
    assert stats.empirical_success_rate == pytest.approx(0.5)
    assert stats.mean_predicted_probability == pytest.approx(0.9)
    assert stats.mean_brier_score == pytest.approx((0.01 + 0.81) / 2)
    assert stats.calibration_gap == pytest.approx(0.4)


def test_prediction_ledger_detects_tampering(tmp_path):
    ledger = PredictionLedger(tmp_path / "predictions.jsonl")
    p = proposal()
    ledger.append(scored_settlement(p, 0.7, True, 1))
    raw = ledger.path.read_text(encoding="utf-8")
    ledger.path.write_text(
        raw.replace(
            '"probability_effect_success":0.7',
            '"probability_effect_success":0.2',
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.verify()


def test_prediction_audit_service_reports_glyphs_and_stats(tmp_path):
    graph, ledger, prediction_engine = engine(tmp_path, 0.75)
    p = proposal()
    _, verdict = prepare(graph, prediction_engine, p)
    prediction_engine.settle(
        proposal=p,
        reality=fake_reality(
            proposal=p,
            verdict_glyph_id=verdict.glyph_id,
            effect=True,
        ),
    )
    audit = PredictionAuditService(graph=graph, ledger=ledger)
    assert len(audit.prediction_glyphs()) == 1
    assert len(audit.error_glyphs()) == 1
    assert audit.stats(
        p.action_type,
        strategy_key=p.strategy_key,
    ).observations == 1
