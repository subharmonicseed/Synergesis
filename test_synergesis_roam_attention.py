import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_roam import (
    MethodLedger,
    ResearchMethodLearner,
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
from synergesis_roam_attention import (
    AttentionMeasurements,
    AttentionWeights,
    ResearchAgenda,
    ResearchNeed,
    RoamAttentionController,
    SeleneRoamBridge,
    score_attention,
)


class Adapter:
    def search(self, *, query, max_items):
        return (
            RetrievedItem(
                "https://example.test/x",
                "X",
                "body",
                "web",
                0.1,
            ),
        )[:max_items]


def stack(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    security = AegisSecurityGraph(graph)
    sources = SourceRegistry()
    sources.register(
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
        security_graph=security,
        source_registry=sources,
        adapters={"web": Adapter()},
        limits=RoamLimits(2, 4, 2.0),
    )
    learner = ResearchMethodLearner(
        ledger=MethodLedger(tmp_path / "methods.jsonl"),
        config=SelectionConfig(
            exploration_strength=0.0,
            require_counter_search_for_hypothesis=True,
        ),
    )
    learner.register(
        make_method(
            name="skeptic",
            domain="science",
            created_by="test",
            steps=(
                SearchStep(
                    "web",
                    "challenge",
                    "{question} {hypothesis}",
                    1,
                ),
            ),
        )
    )
    roam = SynRoam(
        learner=learner,
        runtime=runtime,
        utility_weights=UtilityWeights(
            1, 1, 1, 1, 1, 1, 1
        ),
    )
    agenda = ResearchAgenda(
        tmp_path / "agenda.jsonl",
        graph=graph,
        weights=AttentionWeights(
            uncertainty=1.0,
            expected_impact=2.0,
            staleness=1.0,
            novelty_gap=1.0,
        ),
    )
    return graph, agenda, RoamAttentionController(agenda=agenda, roam=roam)


def need(question, impact, uncertainty=0.5):
    return ResearchNeed.create(
        domain="science",
        question=question,
        hypothesis="H",
        reason="knowledge gap",
        measurements=AttentionMeasurements(
            uncertainty=uncertainty,
            expected_impact=impact,
            staleness=0.2,
            novelty_gap=0.4,
        ),
    )


def test_attention_score_uses_explicit_measurements():
    m = AttentionMeasurements(1.0, 0.0, 0.0, 0.0)
    w = AttentionWeights(2.0, 1.0, 1.0, 0.0)
    assert score_attention(m, w) == pytest.approx(0.5)


def test_agenda_selects_highest_scored_pending_need(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    low = agenda.add(need("low", 0.1))
    high = agenda.add(need("high", 0.9))
    assert agenda.select_next().need.need_id == high.need.need_id


def test_one_tick_launches_at_most_one_research_session(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    a = agenda.add(need("A", 0.9))
    b = agenda.add(need("B", 0.8))
    tick = controller.tick_once()
    assert tick.status == "researched"
    assert tick.need_id == a.need.need_id
    assert agenda.get(a.need.need_id).status == "researched"
    assert agenda.get(b.need.need_id).status == "pending"


def test_idle_tick_when_no_pending_need(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    tick = controller.tick_once()
    assert tick.status == "idle"
    assert tick.need_id is None
    assert tick.session is None


def test_need_history_is_versioned_in_glyph_graph(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    state = agenda.add(need("history", 0.7))
    tick = controller.tick_once()
    versions = graph.ledger.find_by_external_ref(
        state.need.need_id,
        glyph_type="goal",
    )
    assert [g.content["status"] for g in versions] == [
        "pending",
        "researched",
    ]


def test_bad_provenance_reference_does_not_append_partial_need_glyph(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    n = ResearchNeed.create(
        domain="science",
        question="bad provenance",
        hypothesis="H",
        reason="test",
        measurements=AttentionMeasurements(0.5, 0.5, 0.5, 0.5),
        source_glyph_ids=("g:missing",),
    )
    before = graph.ledger.verify().event_count
    with pytest.raises(KeyError, match="unknown glyph"):
        agenda.add(n)
    after = graph.ledger.verify().event_count
    assert after == before


def test_deferred_need_is_not_selected(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    a = agenda.add(need("defer", 1.0))
    b = agenda.add(need("keep", 0.2))
    agenda.defer(a.need.need_id, reason="waiting for prerequisite")
    assert agenda.select_next().need.need_id == b.need.need_id


def test_evaluation_closes_need_loop_and_updates_method_stats(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    state = agenda.add(need("evaluate me", 0.8))
    tick = controller.tick_once()
    outcome = controller.evaluate_need(
        need_id=state.need.need_id,
        session=tick.session,
        metrics=__import__("synergesis_roam").OutcomeMetrics(
            verified_yield=0.8,
            novelty_yield=0.7,
            contradiction_yield=0.6,
            calibration_gain=0.5,
            predictive_value=0.4,
            redundancy=0.1,
            normalized_cost=0.2,
        ),
    )
    assert agenda.get(state.need.need_id).status == "evaluated"
    assert outcome.method_id == tick.session.method_id
    assert controller.roam.learner.ledger.stats(outcome.method_id).observations == 1


def test_selene_gap_bridge_enqueues_only_missing_predicates(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    core = controller.roam.runtime.aura.core
    core.remember(
        "system",
        "known_predicate",
        "present",
        source="test",
        confidence=1.0,
        evidence_id="known-1",
    )

    class Provider:
        def build_need(self, predicate):
            return ResearchNeed.create(
                domain="science",
                question=f"Find evidence for predicate {predicate}",
                hypothesis=None,
                reason=f"SELENE gap: {predicate}",
                measurements=AttentionMeasurements(
                    uncertainty=1.0,
                    expected_impact=0.5,
                    staleness=0.0,
                    novelty_gap=1.0,
                ),
            )

    bridge = SeleneRoamBridge(
        core=core,
        agenda=agenda,
        provider=Provider(),
    )
    states = bridge.scan_once(["known_predicate", "missing_predicate"])
    assert len(states) == 1
    assert states[0].need.reason == "SELENE gap: missing_predicate"


def test_evaluation_rejects_wrong_session_for_need(tmp_path):
    graph, agenda, controller = stack(tmp_path)
    first = agenda.add(need("first", 0.9))
    second = agenda.add(need("second", 0.8))
    tick1 = controller.tick_once()
    tick2 = controller.tick_once()
    assert tick1.need_id == first.need.need_id
    assert tick2.need_id == second.need.need_id

    with pytest.raises(ValueError, match="does not belong"):
        controller.evaluate_need(
            need_id=first.need.need_id,
            session=tick2.session,
            metrics=__import__("synergesis_roam").OutcomeMetrics(
                verified_yield=0.5,
                novelty_yield=0.5,
                contradiction_yield=0.5,
                calibration_gain=0.5,
                predictive_value=0.5,
                redundancy=0.1,
                normalized_cost=0.1,
            ),
        )
