import math

import pytest

from synergesis_causal_credit import (
    CausalHypothesis,
    CausalModel,
    install_causal_credit,
)
from synergesis_causal_experiment import (
    CausalExperimentPolicy,
    CausalExperimentSelector,
)
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_prediction import (
    PredictionEngine,
    PredictionLedger,
    StaticPredictionProvider,
)


def setup(tmp_path, *, responses=None, priors=(0.5, 0.5)):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    a = core.remember("system", "possible_fault", "a", "operator", 0.5, "belief:a")
    b = core.remember("system", "possible_fault", "b", "operator", 0.5, "belief:b")
    responses = responses or (
        (("check", 0.2), ("repair", 0.9)),
        (("check", 0.2), ("repair", 0.1)),
    )
    model = CausalModel(
        action_type="diagnostic.run",
        strategy_key="diagnose",
        intervention_parameter="intervention",
        observer_id="probe:diagnostic",
        observed_intervention_fact="applied_intervention",
        hypotheses=(
            CausalHypothesis(a.evidence_id, priors[0], tuple(responses[0])),
            CausalHypothesis(b.evidence_id, priors[1], tuple(responses[1])),
        ),
    )
    ledger = PredictionLedger(tmp_path / "prediction.jsonl")
    engine = PredictionEngine(
        graph=graph,
        provider=StaticPredictionProvider(0.5),
        ledger=ledger,
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
    return graph, core, credit, model, selector


def score_by_name(recommendation):
    return {score.intervention: score for score in recommendation.scores}


def test_selects_intervention_that_separates_hypotheses(tmp_path):
    graph, core, credit, model, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    scores = score_by_name(recommendation)
    assert recommendation.status == "informative"
    assert recommendation.selected_intervention == "repair"
    assert scores["check"].information_gain_bits == pytest.approx(0.0)
    assert scores["repair"].information_gain_bits > 0.5
    assert scores["repair"].predicted_success_probability == pytest.approx(0.5)
    assert scores["repair"].success_posterior["belief:a"] == pytest.approx(0.9)
    assert scores["repair"].success_posterior["belief:b"] == pytest.approx(0.1)


def test_equal_uninformative_interventions_do_not_force_choice(tmp_path):
    graph, core, credit, model, selector = setup(
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
    assert recommendation.status == "uninformative"
    assert recommendation.selected_intervention is None
    assert set(recommendation.tied_interventions) == {"x", "y"}
    assert all(
        score.information_gain_bits == pytest.approx(0.0)
        for score in recommendation.scores
    )


def test_equal_informative_interventions_report_ambiguous_best(tmp_path):
    graph, core, credit, model, selector = setup(
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
    assert recommendation.selected_intervention is None
    assert recommendation.tied_interventions == ("x", "y")


def test_information_gain_shrinks_after_one_hypothesis_dominates(tmp_path):
    graph, core, credit, model, selector = setup(tmp_path)
    before = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    repair_before = score_by_name(before)["repair"].information_gain_bits

    # Materialize a 90/10 posterior directly through the same atomic semantic
    # representation used by CausalCreditBridge. This isolates selector math.
    import json
    from synergesis_cognitive_core import Fact

    logs = [math.log(0.9), math.log(0.1)]
    fact = Fact(
        model.model_id,
        credit.predicate,
        json.dumps(logs, separators=(",", ":")),
        credit.actor,
        1.0,
        "2026-09-12T00:00:00+00:00",
        "test:posterior-90-10",
    )
    core.memory.add(fact)
    core.ensure_fact_glyph(fact)

    after = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    repair_after = score_by_name(after)["repair"].information_gain_bits
    assert repair_after < repair_before
    assert after.current_posterior["belief:a"] == pytest.approx(0.9)
    assert after.current_posterior["belief:b"] == pytest.approx(0.1)


def test_recommendation_is_audited_and_has_no_authorization_effect(tmp_path):
    graph, core, credit, model, selector = setup(tmp_path)
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    glyph = graph.ledger.get(recommendation.recommendation_glyph_id)
    assert glyph.glyph_type == "decision"
    assert glyph.content["kind"] == "causal_experiment_recommendation"
    assert glyph.content["authorization_effect"] == "none"
    assert glyph.content["causal_validity"] == "conditional_on_registered_models"


def test_selector_rejects_unregistered_model(tmp_path):
    graph, core, credit, model, selector = setup(tmp_path)
    with pytest.raises(ValueError, match="no registered causal model"):
        selector.recommend(action_type="other", strategy_key="diagnose")


def test_selector_refuses_while_model_prediction_is_pending(tmp_path):
    graph, core, credit, model, selector = setup(tmp_path)
    credit.pending[model.model_id] = "pred:pending"
    with pytest.raises(ValueError, match="settle the pending"):
        selector.recommend(
            action_type="diagnostic.run",
            strategy_key="diagnose",
        )


def test_policy_can_require_meaningful_information_gain(tmp_path):
    graph, core, credit, model, _ = setup(tmp_path)
    selector = CausalExperimentSelector(
        graph=graph,
        causal_credit=credit,
        policy=CausalExperimentPolicy(
            minimum_information_gain_bits=0.9,
            tie_tolerance_bits=1e-12,
        ),
    )
    recommendation = selector.recommend(
        action_type="diagnostic.run",
        strategy_key="diagnose",
    )
    assert recommendation.status == "uninformative"
    assert recommendation.selected_intervention is None


def test_invalid_policy_rejected():
    with pytest.raises(ValueError):
        CausalExperimentPolicy(minimum_information_gain_bits=-1)
    with pytest.raises(ValueError):
        CausalExperimentPolicy(tie_tolerance_bits=float("nan"))
