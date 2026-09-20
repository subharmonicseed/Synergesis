import pytest

from synergesis_causal_credit import (
    CausalHypothesis,
    CausalModel,
    install_causal_credit,
)
from synergesis_causal_experiment import CausalExperimentSelector
from synergesis_experiment_utility import (
    ExperimentImpactProfile,
    ExperimentUtilityGate,
    ExperimentUtilityPolicy,
)
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_prediction import (
    PredictionEngine,
    PredictionLedger,
    StaticPredictionProvider,
)


def setup(
    tmp_path,
    *,
    responses=(
        (("high", 0.95), ("low", 0.8)),
        (("high", 0.05), ("low", 0.2)),
    ),
):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    a = core.remember(
        "system", "possible_fault", "a", "operator", 0.5, "belief:a"
    )
    b = core.remember(
        "system", "possible_fault", "b", "operator", 0.5, "belief:b"
    )
    model = CausalModel(
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention_parameter="intervention",
        observer_id="probe:diagnostic",
        observed_intervention_fact="applied_intervention",
        hypotheses=(
            CausalHypothesis(a.evidence_id, 0.5, tuple(responses[0])),
            CausalHypothesis(b.evidence_id, 0.5, tuple(responses[1])),
        ),
    )
    engine = PredictionEngine(
        graph=graph,
        provider=StaticPredictionProvider(0.5),
        ledger=PredictionLedger(tmp_path / "prediction.jsonl"),
    )
    credit = install_causal_credit(
        engine=engine,
        core=core,
        models=(model,),
    )
    selector = CausalExperimentSelector(
        graph=graph,
        causal_credit=credit,
    )
    return graph, selector


def policy(**overrides):
    values = dict(
        risk_weight=1.0,
        cost_weight=1.0,
        irreversibility_weight=1.0,
        minimum_utility=0.01,
        minimum_information_gain_bits=1e-9,
        maximum_risk=1.0,
        maximum_irreversibility=1.0,
        tie_tolerance=1e-12,
    )
    values.update(overrides)
    return ExperimentUtilityPolicy(**values)


def profile(intervention, *, risk=0.0, cost=0.0, irreversibility=0.0):
    return ExperimentImpactProfile(
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention=intervention,
        risk=risk,
        cost=cost,
        irreversibility=irreversibility,
    )


def test_utility_can_prefer_less_informative_but_safer_intervention(tmp_path):
    graph, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    scores = {
        score.intervention: score.information_gain_bits
        for score in recommendation.scores
    }
    assert scores["high"] > scores["low"]

    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(
            profile("high", risk=0.9),
            profile("low", risk=0.0),
        ),
        policy=policy(maximum_risk=1.0),
    )
    decision = gate.evaluate(recommendation)

    assert decision.status == "approved"
    assert decision.selected_intervention == "low"
    by_name = {c.intervention: c for c in decision.candidates}
    assert by_name["high"].information_gain_bits > by_name["low"].information_gain_bits
    assert by_name["high"].utility < by_name["low"].utility


def test_hard_risk_limit_overrides_information_gain(tmp_path):
    graph, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(
            profile("high", risk=0.8),
            profile("low", risk=0.1),
        ),
        policy=policy(maximum_risk=0.5, risk_weight=0.0),
    )
    decision = gate.evaluate(recommendation)

    assert decision.status == "approved"
    assert decision.selected_intervention == "low"
    high = {c.intervention: c for c in decision.candidates}["high"]
    assert high.eligible is False
    assert "risk_above_policy_maximum" in high.block_reasons


def test_missing_profile_is_not_silently_treated_as_zero_impact(tmp_path):
    graph, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(profile("low"),),
        policy=policy(),
    )
    decision = gate.evaluate(recommendation)

    high = {c.intervention: c for c in decision.candidates}["high"]
    assert high.eligible is False
    assert high.utility is None
    assert high.risk is None
    assert high.block_reasons == ("missing_trusted_impact_profile",)


def test_no_safe_candidate_yields_no_selection(tmp_path):
    graph, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(
            profile("high", risk=0.9),
            profile("low", risk=0.8),
        ),
        policy=policy(maximum_risk=0.5),
    )
    decision = gate.evaluate(recommendation)

    assert decision.status == "no_safe_candidate"
    assert decision.selected_intervention is None


def test_below_minimum_utility_yields_no_selection(tmp_path):
    graph, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(
            profile("high", cost=0.9),
            profile("low", cost=0.9),
        ),
        policy=policy(minimum_utility=0.2),
    )
    decision = gate.evaluate(recommendation)

    assert decision.status == "below_minimum_utility"
    assert decision.selected_intervention is None


def test_utility_breaks_information_gain_tie_using_lower_cost(tmp_path):
    graph, selector = setup(
        tmp_path,
        responses=(
            (("x", 0.9), ("y", 0.9)),
            (("x", 0.1), ("y", 0.1)),
        ),
    )
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    assert recommendation.status == "ambiguous_best"

    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(
            profile("x", cost=0.2),
            profile("y", cost=0.0),
        ),
        policy=policy(),
    )
    decision = gate.evaluate(recommendation)
    assert decision.status == "approved"
    assert decision.selected_intervention == "y"


def test_equal_total_utility_does_not_force_choice(tmp_path):
    graph, selector = setup(
        tmp_path,
        responses=(
            (("x", 0.9), ("y", 0.9)),
            (("x", 0.1), ("y", 0.1)),
        ),
    )
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(profile("x"), profile("y")),
        policy=policy(),
    )
    decision = gate.evaluate(recommendation)

    assert decision.status == "ambiguous_best"
    assert decision.selected_intervention is None


def test_uninformative_experiments_are_rejected_even_if_free(tmp_path):
    graph, selector = setup(
        tmp_path,
        responses=(
            (("x", 0.2), ("y", 0.8)),
            (("x", 0.2), ("y", 0.8)),
        ),
    )
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(profile("x"), profile("y")),
        policy=policy(),
    )
    decision = gate.evaluate(recommendation)

    assert decision.status == "uninformative"
    assert decision.selected_intervention is None


def test_utility_decision_is_audited_and_has_no_authorization_effect(tmp_path):
    graph, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    gate = ExperimentUtilityGate(
        graph=graph,
        profiles=(profile("high"), profile("low")),
        policy=policy(),
    )
    decision = gate.evaluate(recommendation)
    glyph = graph.ledger.get(decision.decision_glyph_id)

    assert glyph.glyph_type == "decision"
    assert glyph.content["kind"] == "causal_experiment_utility_decision"
    assert glyph.content["impact_source"] == "trusted_configuration"
    assert glyph.content["authorization_effect"] == "none"
    assert recommendation.recommendation_glyph_id in {
        g.glyph_id for g in graph.upstream(glyph.glyph_id, max_depth=2).glyphs
    }


def test_invalid_or_duplicate_trusted_profiles_are_rejected(tmp_path):
    graph, selector = setup(tmp_path)
    with pytest.raises(ValueError):
        ExperimentImpactProfile(
            "diagnostic.run", "diagnose", "x", 1.1, 0, 0
        )
    p = profile("x")
    with pytest.raises(ValueError, match="duplicate"):
        ExperimentUtilityGate(
            graph=graph,
            profiles=(p, p),
            policy=policy(),
        )
    with pytest.raises(ValueError):
        ExperimentUtilityPolicy(
            risk_weight=1,
            cost_weight=1,
            irreversibility_weight=1,
            minimum_utility=0,
            minimum_information_gain_bits=0,
            maximum_risk=1.1,
            maximum_irreversibility=1,
        )
