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
)
from synergesis_roam_evolution import (
    EvolutionPolicy,
    MethodEvolutionLedger,
    MethodEvolutionManager,
    ResearchMethodDraft,
)


class Adapter:
    def search(self, *, query, max_items):
        return (
            RetrievedItem("src:a", "A", "body", "web", 0.1),
        )[:max_items]


def build(tmp_path, *, min_trials=1, margin=0.2):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    source_registry = SourceRegistry()
    source_registry.register(
        SourcePolicy(
            "web",
            "web",
            ("science",),
            2,
            True,
        )
    )
    runtime = RoamRuntime(
        graph=graph,
        aura=aura,
        security_graph=AegisSecurityGraph(graph),
        source_registry=source_registry,
        adapters={"web": Adapter()},
        limits=RoamLimits(3, 4, 3.0),
    )
    outcome_ledger = MethodLedger(tmp_path / "method_outcomes.jsonl")
    learner = ResearchMethodLearner(
        ledger=outcome_ledger,
        config=SelectionConfig(
            exploration_strength=0.0,
            require_counter_search_for_hypothesis=True,
        ),
    )
    baseline = make_method(
        name="baseline",
        domain="science",
        created_by="test",
        steps=(
            SearchStep("web", "challenge", "{question}", 1),
        ),
    )
    learner.register(baseline)
    weights = UtilityWeights(1, 1, 1, 1, 1, 1, 1)
    manager = MethodEvolutionManager(
        graph=graph,
        source_registry=source_registry,
        learner=learner,
        outcome_ledger=outcome_ledger,
        evolution_ledger=MethodEvolutionLedger(tmp_path / "evolution.jsonl"),
        policy=EvolutionPolicy(
            max_steps_per_method=3,
            min_trials_per_method=min_trials,
            promotion_margin=margin,
            require_counter_search=True,
        ),
    )
    return graph, runtime, learner, baseline, weights, manager, outcome_ledger


def draft(name="candidate", *, source="web", perspective="challenge", template="{question}"):
    return ResearchMethodDraft(
        name=name,
        domain="science",
        steps=(
            SearchStep(source, perspective, template, 1),
        ),
        rationale="Try a different research angle.",
    )


def q(label):
    return ResearchQuestion.create(
        domain="science",
        question=f"Question {label}",
        hypothesis="H",
    )


def good():
    return OutcomeMetrics(0.9, 0.9, 0.9, 0.9, 0.9, 0.0, 0.1)


def bad():
    return OutcomeMetrics(0.1, 0.1, 0.1, 0.1, 0.1, 0.8, 0.8)


def test_candidate_cannot_introduce_unknown_source(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(tmp_path)
    with pytest.raises(KeyError, match="unknown source"):
        manager.propose(
            baseline=baseline,
            draft=draft(source="secret-backdoor"),
            created_by="model",
        )


def test_candidate_query_template_is_strict(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(tmp_path)
    with pytest.raises(ValueError, match="unsupported fields"):
        manager.propose(
            baseline=baseline,
            draft=draft(template="{question} {system_prompt}"),
            created_by="model",
        )


def test_candidate_must_preserve_counter_search(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(tmp_path)
    with pytest.raises(ValueError, match="challenge step"):
        manager.propose(
            baseline=baseline,
            draft=draft(perspective="support"),
            created_by="model",
        )


def test_candidate_is_not_active_before_empirical_promotion(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(tmp_path)
    candidate = manager.propose(
        baseline=baseline,
        draft=draft(),
        created_by="model",
    )
    selected = learner.select(q("cold"))
    assert selected.method_id == baseline.method_id
    assert candidate.method.method_id != baseline.method_id


def test_insufficient_trials_do_not_promote_candidate(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(
        tmp_path,
        min_trials=2,
    )
    candidate = manager.propose(
        baseline=baseline,
        draft=draft(),
        created_by="model",
    )
    decision = manager.decide(candidate.candidate_id)
    assert decision.decision == "insufficient_data"
    assert manager.get(candidate.candidate_id).status == "experimental"


def test_better_candidate_is_promoted_after_trials(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(
        tmp_path,
        min_trials=1,
        margin=0.5,
    )
    candidate = manager.propose(
        baseline=baseline,
        draft=draft(name="better"),
        created_by="model",
    )

    baseline_session = runtime.run(question=q("baseline"), method=baseline)
    learner.record_outcome(
        session=baseline_session,
        metrics=bad(),
        weights=weights,
    )

    candidate_session = runtime.run(
        question=q("candidate"),
        method=candidate.method,
    )
    manager.record_trial(
        candidate_id=candidate.candidate_id,
        session=candidate_session,
        metrics=good(),
        weights=weights,
    )

    decision = manager.decide(candidate.candidate_id)
    assert decision.decision == "promote"
    assert manager.get(candidate.candidate_id).status == "promoted"
    assert learner.select(q("after")).method_id == candidate.method.method_id


def test_worse_candidate_is_rejected(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(
        tmp_path,
        min_trials=1,
        margin=0.1,
    )
    candidate = manager.propose(
        baseline=baseline,
        draft=draft(name="worse"),
        created_by="model",
    )

    baseline_session = runtime.run(question=q("baseline"), method=baseline)
    learner.record_outcome(
        session=baseline_session,
        metrics=good(),
        weights=weights,
    )
    candidate_session = runtime.run(
        question=q("candidate"),
        method=candidate.method,
    )
    manager.record_trial(
        candidate_id=candidate.candidate_id,
        session=candidate_session,
        metrics=bad(),
        weights=weights,
    )

    decision = manager.decide(candidate.candidate_id)
    assert decision.decision == "reject"
    assert manager.get(candidate.candidate_id).status == "rejected"
    assert learner.select(q("after")).method_id == baseline.method_id


def test_evolution_decision_is_audited_as_glyph(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(tmp_path)
    candidate = manager.propose(
        baseline=baseline,
        draft=draft(name="audit"),
        created_by="model",
    )
    decision = manager.decide(candidate.candidate_id)
    glyphs = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "decision"
        and g.content.get("kind") == "research_method_evolution"
    ]
    assert glyphs
    assert glyphs[-1].content["candidate_id"] == candidate.candidate_id
    assert glyphs[-1].content["decision"] == "insufficient_data"


def test_evolution_state_survives_manager_restart(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(tmp_path)
    candidate = manager.propose(
        baseline=baseline,
        draft=draft(name="persist"),
        created_by="model",
    )

    restored = MethodEvolutionManager(
        graph=graph,
        source_registry=runtime.source_registry,
        learner=learner,
        outcome_ledger=ledger,
        evolution_ledger=manager.evolution_ledger,
        policy=manager.policy,
    )
    assert restored.get(candidate.candidate_id).method.method_id == candidate.method.method_id
    assert restored.get(candidate.candidate_id).status == "experimental"


def test_evolution_ledger_detects_tampering(tmp_path):
    graph, runtime, learner, baseline, weights, manager, ledger = build(tmp_path)
    manager.propose(
        baseline=baseline,
        draft=draft(name="tamper"),
        created_by="model",
    )
    path = manager.evolution_ledger.path
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace("candidate_proposed", "candidate_hacked"), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity failure"):
        manager.evolution_ledger.events()
