from dataclasses import asdict
from pathlib import Path

import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_roam import (
    MethodLedger,
    OutcomeMetrics,
    ResearchMethodLearner,
    ResearchQuestion,
    RetrievedItem,
    RoamLimits,
    RoamRuntime,
    SearchStep,
    SelectionConfig,
    SourcePolicy,
    SourceRegistry,
    SynRoam,
    UtilityWeights,
    make_method,
    score_outcome,
)


class StaticAdapter:
    def __init__(self, items):
        self.items = tuple(items)
        self.calls = []

    def search(self, *, query, max_items):
        self.calls.append((query, max_items))
        return self.items[:max_items]


def build(tmp_path, *, items=None, limits=None, exploration=0.0, require_counter=True):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    security = AegisSecurityGraph(graph)
    registry = SourceRegistry()
    registry.register(
        SourcePolicy(
            source_id="web",
            source_type="web",
            domains=("science", "*"),
            max_items_per_query=3,
            external_untrusted=True,
        )
    )
    adapter = StaticAdapter(
        items
        or (
            RetrievedItem(
                "https://example.test/a",
                "A",
                "content A",
                "web",
                1.0,
            ),
            RetrievedItem(
                "https://example.test/b",
                "B",
                "content B",
                "web",
                1.0,
            ),
        )
    )
    runtime = RoamRuntime(
        graph=graph,
        aura=aura,
        security_graph=security,
        source_registry=registry,
        adapters={"web": adapter},
        limits=limits
        or RoamLimits(
            max_steps_per_session=4,
            max_items_per_session=10,
            max_budget_units=10.0,
        ),
    )
    ledger = MethodLedger(tmp_path / "method_outcomes.jsonl")
    learner = ResearchMethodLearner(
        ledger=ledger,
        config=SelectionConfig(
            exploration_strength=exploration,
            require_counter_search_for_hypothesis=require_counter,
        ),
    )
    weights = UtilityWeights(
        verified_yield=1.0,
        novelty_yield=1.0,
        contradiction_yield=1.0,
        calibration_gain=1.0,
        predictive_value=1.0,
        redundancy_penalty=1.0,
        cost_penalty=1.0,
    )
    roam = SynRoam(
        learner=learner,
        runtime=runtime,
        utility_weights=weights,
    )
    return roam, learner, runtime, graph, security, adapter, ledger


def method(name, perspective="challenge"):
    return make_method(
        name=name,
        domain="science",
        created_by="test",
        steps=(
            SearchStep(
                source_id="web",
                perspective=perspective,
                query_template="{question} :: {hypothesis}",
                max_items=2,
            ),
        ),
    )


def question(hypothesis="H"):
    return ResearchQuestion.create(
        domain="science",
        question="What evidence bears on H?",
        hypothesis=hypothesis,
    )


def metrics(
    *,
    verified=0.5,
    novelty=0.5,
    contradiction=0.5,
    calibration=0.5,
    predictive=0.5,
    redundancy=0.0,
    cost=0.0,
):
    return OutcomeMetrics(
        verified_yield=verified,
        novelty_yield=novelty,
        contradiction_yield=contradiction,
        calibration_gain=calibration,
        predictive_value=predictive,
        redundancy=redundancy,
        normalized_cost=cost,
    )


def test_outcome_score_rewards_counterevidence_discovery():
    weights = UtilityWeights(
        verified_yield=0.0,
        novelty_yield=0.0,
        contradiction_yield=2.0,
        calibration_gain=0.0,
        predictive_value=0.0,
        redundancy_penalty=0.0,
        cost_penalty=0.0,
    )
    low = metrics(contradiction=0.1)
    high = metrics(contradiction=0.9)
    assert score_outcome(high, weights) > score_outcome(low, weights)


def test_hypothesis_requires_method_with_challenge_step(tmp_path):
    roam, learner, *_ = build(tmp_path, require_counter=True)
    learner.register(method("confirm-only", perspective="support"))
    with pytest.raises(ValueError, match="no eligible research method"):
        learner.select(question("H"))


def test_question_without_hypothesis_can_use_exploratory_method(tmp_path):
    roam, learner, *_ = build(tmp_path, require_counter=True)
    exploratory = method("explore", perspective="explore")
    learner.register(exploratory)
    selected = learner.select(question(None))
    assert selected.method_id == exploratory.method_id


def test_roam_ingests_evidence_and_marks_external_taint(tmp_path):
    roam, learner, runtime, graph, security, adapter, ledger = build(tmp_path)
    m = method("skeptical")
    learner.register(m)

    session = roam.research_once(question("H"))
    assert session.status == "completed"
    assert session.total_items == 2
    assert len(session.executions) == 1

    for evidence_id in session.executions[0].evidence_ids:
        glyph = graph.ledger.find_by_external_ref(
            evidence_id,
            glyph_type="evidence",
        )[-1]
        assert "external_untrusted" in security.active_taints(glyph.glyph_id)


def test_roam_is_bounded_by_item_budget(tmp_path):
    items = tuple(
        RetrievedItem(f"src:{i}", f"T{i}", f"C{i}", "web", 0.1)
        for i in range(5)
    )
    limits = RoamLimits(
        max_steps_per_session=4,
        max_items_per_session=1,
        max_budget_units=10.0,
    )
    roam, learner, *_ = build(tmp_path, items=items, limits=limits)
    learner.register(method("bounded"))
    session = roam.research_once(question())
    assert session.total_items == 1
    assert session.status in {"completed", "budget_exhausted"}


def test_roam_is_bounded_by_cost_budget(tmp_path):
    items = (
        RetrievedItem("a", "A", "A", "web", 0.6),
        RetrievedItem("b", "B", "B", "web", 0.6),
    )
    limits = RoamLimits(
        max_steps_per_session=4,
        max_items_per_session=10,
        max_budget_units=1.0,
    )
    roam, learner, *_ = build(tmp_path, items=items, limits=limits)
    learner.register(method("cost-bounded"))
    session = roam.research_once(question())
    assert session.total_items == 1
    assert session.total_cost_units == pytest.approx(0.6)
    assert session.status == "budget_exhausted"


def test_adapter_cannot_return_more_than_requested(tmp_path):
    class BadAdapter:
        def search(self, *, query, max_items):
            return tuple(
                RetrievedItem(f"s:{i}", str(i), str(i), "web", 0.0)
                for i in range(max_items + 1)
            )

    roam, learner, runtime, *_ = build(tmp_path)
    runtime.adapters["web"] = BadAdapter()
    learner.register(method("bad-adapter"))
    with pytest.raises(ValueError, match="more items than requested"):
        roam.research_once(question())


def test_method_learner_prefers_empirically_better_method(tmp_path):
    roam, learner, runtime, graph, security, adapter, ledger = build(
        tmp_path,
        exploration=0.0,
    )
    a = method("A")
    b = method("B")
    learner.register(a)
    learner.register(b)

    # Explicitly evaluate one session per method.
    session_a = runtime.run(question=question("A"), method=a)
    learner.record_outcome(
        session=session_a,
        metrics=metrics(
            verified=0.1,
            novelty=0.1,
            contradiction=0.1,
            calibration=0.1,
            predictive=0.1,
            redundancy=0.8,
            cost=0.8,
        ),
        weights=roam.utility_weights,
    )
    session_b = runtime.run(question=question("B"), method=b)
    learner.record_outcome(
        session=session_b,
        metrics=metrics(
            verified=0.9,
            novelty=0.9,
            contradiction=0.9,
            calibration=0.9,
            predictive=0.9,
            redundancy=0.0,
            cost=0.1,
        ),
        weights=roam.utility_weights,
    )

    assert learner.select(question("C")).method_id == b.method_id


def test_evaluation_creates_learning_glyph(tmp_path):
    roam, learner, runtime, graph, *_ = build(tmp_path)
    m = method("learn")
    learner.register(m)
    session = roam.research_once(question())
    outcome = roam.evaluate(session, metrics())
    matches = graph.ledger.find_by_external_ref(
        outcome.outcome_id,
        glyph_type="learning",
    )
    assert len(matches) == 1
    assert matches[0].content["method_id"] == m.method_id


def test_method_ledger_detects_tampering(tmp_path):
    roam, learner, runtime, graph, security, adapter, ledger = build(tmp_path)
    m = method("tamper")
    learner.register(m)
    session = roam.research_once(question())
    learner.record_outcome(
        session=session,
        metrics=metrics(),
        weights=roam.utility_weights,
    )

    raw = ledger.path.read_text(encoding="utf-8")
    ledger.path.write_text(
        raw.replace('"utility":2.5', '"utility":999.0'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.events()


def test_disabled_source_is_rejected(tmp_path):
    roam, learner, runtime, *_ = build(tmp_path)
    runtime.source_registry._policies["web"] = SourcePolicy(
        source_id="web",
        source_type="web",
        domains=("science",),
        max_items_per_query=3,
        external_untrusted=True,
        enabled=False,
    )
    learner.register(method("disabled"))
    with pytest.raises(ValueError, match="source disabled"):
        roam.research_once(question())


def test_method_over_step_limit_is_rejected_before_search(tmp_path):
    limits = RoamLimits(
        max_steps_per_session=1,
        max_items_per_session=10,
        max_budget_units=10.0,
    )
    roam, learner, runtime, graph, security, adapter, ledger = build(
        tmp_path,
        limits=limits,
    )
    m = make_method(
        name="too-many",
        domain="science",
        created_by="test",
        steps=(
            SearchStep("web", "challenge", "{question}", 1),
            SearchStep("web", "explore", "{question}", 1),
        ),
    )
    learner.register(m)
    with pytest.raises(ValueError, match="max_steps_per_session"):
        roam.research_once(question())
    assert adapter.calls == []
