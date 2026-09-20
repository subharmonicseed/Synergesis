import pytest

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_roam import (
    MethodLedger,
    OutcomeMetrics,
    ResearchMethodLearner,
    ResearchQuestion,
    RoamSession,
    SearchExecution,
    SelectionConfig,
    UtilityWeights,
    SearchStep,
    make_method,
)
from synergesis_roam_adaptive import (
    AdaptiveResearchMethodLearner,
    AdaptiveSelectionConfig,
)


def method(name):
    return make_method(
        name=name,
        domain="science",
        created_by="test",
        steps=(SearchStep("web", "challenge", "{question}", 1),),
    )


def question(n):
    return ResearchQuestion.create(
        domain="science",
        question=f"Q{n}",
        hypothesis="H",
    )


def fake_session(m, n):
    return RoamSession(
        session_id=f"s:{m.method_id}:{n}",
        question=question(n),
        method_id=m.method_id,
        executions=(),
        total_items=0,
        total_cost_units=0.0,
        status="completed",
        plan_glyph_id=f"g:{'0'*32}",
    )


def metrics(value):
    return OutcomeMetrics(
        verified_yield=value,
        novelty_yield=value,
        contradiction_yield=value,
        calibration_gain=value,
        predictive_value=value,
        redundancy=0.0,
        normalized_cost=0.0,
    )


def weights():
    return UtilityWeights(1, 1, 1, 1, 1, 0, 0)


def build(tmp_path, max_gap=3, window=3, graph=None, half_life=1e9):
    learner = AdaptiveResearchMethodLearner(
        ledger=MethodLedger(tmp_path / "outcomes.jsonl"),
        config=SelectionConfig(
            exploration_strength=0.0,
            require_counter_search_for_hypothesis=True,
        ),
        adaptive_config=AdaptiveSelectionConfig(
            rolling_window_per_method=window,
            max_selection_gap=max_gap,
            exploration_strength=0.0,
            decay_half_life_events=half_life,
        ),
        graph=graph,
    )
    return learner


def test_cold_start_samples_all_methods(tmp_path):
    learner = build(tmp_path)
    a, b = method("a"), method("b")
    learner.register(a); learner.register(b)
    first = learner.select(question(1))
    learner.record_outcome(
        session=fake_session(first, 1),
        metrics=metrics(0.5),
        weights=weights(),
    )
    second = learner.select(question(2))
    assert second.method_id != first.method_id


def test_stale_bad_method_is_eventually_retested(tmp_path):
    learner = build(tmp_path, max_gap=2)
    a, b = method("a"), method("b")
    learner.register(a); learner.register(b)

    # Cold-start A bad, B good.
    first = learner.select(question(1))
    learner.record_outcome(
        session=fake_session(first, 1),
        metrics=metrics(0.1),
        weights=weights(),
    )
    second = learner.select(question(2))
    learner.record_outcome(
        session=fake_session(second, 2),
        metrics=metrics(0.9),
        weights=weights(),
    )

    chosen3 = learner.select(question(3))
    learner.record_outcome(
        session=fake_session(chosen3, 3),
        metrics=metrics(0.9),
        weights=weights(),
    )
    chosen4 = learner.select(question(4))
    assert chosen4.method_id == first.method_id


def test_rolling_window_forgets_old_regime(tmp_path):
    learner = build(tmp_path, max_gap=100, window=2)
    a = method("a")
    learner.register(a)
    for i, value in enumerate([0.1, 0.1, 0.9, 0.9], start=1):
        learner.record_outcome(
            session=fake_session(a, i),
            metrics=metrics(value),
            weights=weights(),
        )
    score = learner._score_snapshot((a,))[0]
    assert score.observations_total == 4
    assert score.observations_window == 2
    assert score.recent_mean_utility == pytest.approx(4.5)


def test_selection_decision_is_audited(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    learner = build(tmp_path, graph=graph)
    a = method("a")
    learner.register(a)
    learner.select(question(1))
    decisions = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "decision"
        and g.content.get("kind") == "adaptive_research_method_selection"
    ]
    assert len(decisions) == 1
    assert decisions[0].content["forced_exploration"] is True


def test_invalid_adaptive_config_is_rejected():
    with pytest.raises(ValueError):
        AdaptiveSelectionConfig(0, 1, 0.1)
    with pytest.raises(ValueError):
        AdaptiveSelectionConfig(1, 0, 0.1)
    with pytest.raises(ValueError):
        AdaptiveSelectionConfig(1, 1, -0.1)
    with pytest.raises(ValueError):
        AdaptiveSelectionConfig(1, 1, 0.1, 0.0)


def test_old_regime_decays_in_global_event_time(tmp_path):
    learner = build(tmp_path, max_gap=100, window=8, half_life=2.0)
    a, b = method("a"), method("b")
    learner.register(a); learner.register(b)

    # Old poor A observation.
    learner.record_outcome(
        session=fake_session(a, 1),
        metrics=metrics(0.1),
        weights=weights(),
    )

    # Many B observations advance global event time.
    for i in range(2, 9):
        learner.record_outcome(
            session=fake_session(b, i),
            metrics=metrics(0.5),
            weights=weights(),
        )

    # New good A result should dominate its stale bad history.
    learner.record_outcome(
        session=fake_session(a, 9),
        metrics=metrics(0.9),
        weights=weights(),
    )

    score = learner._score_snapshot((a,))[0]
    assert score.recent_mean_utility > 4.0
