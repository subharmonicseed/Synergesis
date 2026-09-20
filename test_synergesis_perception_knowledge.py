import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_perception_bus import (
    NormalizedPercept,
    PerceptionBus,
    PerceptionSourcePolicy,
    RawPercept,
)
from synergesis_perception_knowledge import (
    PerceptionKnowledgeBridge,
    PerceptionKnowledgeRule,
)
from synergesis_roam_attention import (
    AttentionMeasurements,
    AttentionWeights,
    ResearchAgenda,
)
from synergesis_world_belief_view import VersionedBeliefView


class Adapter:
    def __init__(self, *, confidence=0.9):
        self.confidence = confidence

    def normalize(self, percept):
        return NormalizedPercept(
            observation_kind="device_temperature",
            facts={
                "device": percept.payload["device"],
                "celsius": percept.payload["celsius"],
            },
            confidence=self.confidence,
        )


def rule(**overrides):
    values = dict(
        observation_kind="device_temperature",
        domain="operations",
        subject_fact="device",
        predicate="temperature_c",
        object_fact="celsius",
        versioned=True,
        allow_world_commit=True,
        minimum_confidence=0.8,
        change_semantics="contradiction",
        research_on_contradiction=True,
        research_question_template=(
            "Why did {subject} {predicate} change from {old} to {new}?"
        ),
        research_measurements=AttentionMeasurements(
            uncertainty=0.8,
            expected_impact=0.6,
            staleness=0.1,
            novelty_gap=0.7,
        ),
    )
    values.update(overrides)
    return PerceptionKnowledgeRule(**values)


def setup(tmp_path, *, confidence=0.9, rules=None, versioned=("temperature_c",)):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    bus = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=(
            PerceptionSourcePolicy(
                "sensor:temperature",
                ("temperature",),
                "trusted_observation",
            ),
        ),
        adapters={
            ("sensor:temperature", "temperature"): Adapter(
                confidence=confidence
            ),
        },
    )
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    world = VersionedBeliefView(
        core.memory,
        versioned_predicates=versioned,
    )
    agenda = ResearchAgenda(
        tmp_path / "agenda.jsonl",
        graph=graph,
        weights=AttentionWeights(
            uncertainty=1,
            expected_impact=1,
            staleness=1,
            novelty_gap=1,
        ),
    )
    selector = LexicalContextSelector(
        budget=ContextBudget(max_facts=4, max_evidence=4),
        k1=1.2,
        b=0.75,
    )
    bridge = PerceptionKnowledgeBridge(
        graph=graph,
        core=core,
        aura=aura,
        world_beliefs=world,
        agenda=agenda,
        context_selector=selector,
        rules=tuple(rules or (rule(),)),
    )
    return graph, bus, core, aura, world, agenda, bridge


def ingest(
    bus,
    *,
    value=20.0,
    external_id="t:1",
    captured_at="2026-09-12T12:00:00+00:00",
):
    return bus.ingest(
        RawPercept(
            source_id="sensor:temperature",
            modality="temperature",
            payload={"device": "reactor:A", "celsius": value},
            captured_at=captured_at,
            external_id=external_id,
        )
    )


def test_percept_always_becomes_evidence_before_optional_world_admission(tmp_path):
    graph, bus, core, aura, world, agenda, bridge = setup(
        tmp_path,
        rules=(rule(allow_world_commit=False),),
    )
    record = ingest(bus)
    result = bridge.process(record)

    assert result.admission_status == "evidence_only"
    assert core.memory.count() == 0
    evidence = aura.research.store.get(result.evidence_id)
    assert evidence.source_type == "perception"
    evidence_glyph = graph.ledger.get(result.evidence_glyph_id)
    assert any(
        edge.source == evidence_glyph.glyph_id
        and edge.target == record.normalized_glyph_id
        and edge.relation == "derived_from"
        for edge in graph.ledger.edges_from(evidence_glyph.glyph_id)
    )


def test_missing_confidence_is_not_fabricated_into_world_fact(tmp_path):
    _, bus, core, _, _, _, bridge = setup(
        tmp_path,
        confidence=None,
    )
    result = bridge.process(ingest(bus))
    assert result.admission_status == "confidence_unavailable"
    assert result.fact_evidence_id is None
    assert core.memory.count() == 0


def test_below_threshold_perception_remains_evidence_only(tmp_path):
    _, bus, core, aura, _, _, bridge = setup(
        tmp_path,
        confidence=0.6,
    )
    result = bridge.process(ingest(bus))
    assert result.admission_status == "confidence_below_threshold"
    assert core.memory.count() == 0
    assert aura.research.store.get(result.evidence_id)


def test_admitted_perception_enters_world_and_bounded_context(tmp_path):
    graph, bus, core, aura, world, agenda, bridge = setup(tmp_path)
    result = bridge.process(ingest(bus, value=21.5))
    assert result.admission_status == "committed"

    fact = world.current(
        subject="reactor:A",
        predicate="temperature_c",
    )
    assert fact is not None
    assert fact.object == "21.5"
    assert fact.confidence == pytest.approx(0.9)
    assert fact.observed_at == "2026-09-12T12:00:00+00:00"

    selection = bridge.select_context(query="reactor temperature 21.5")
    assert any(f.evidence_id == fact.evidence_id for f in selection.facts)
    assert any(
        e.evidence_id == result.evidence_id
        for e in selection.evidence
    )


def test_conflicting_perception_creates_critique_and_research_need(tmp_path):
    graph, bus, core, aura, world, agenda, bridge = setup(tmp_path)
    first = bridge.process(ingest(bus, value=20.0, external_id="t:1"))
    second = bridge.process(
        ingest(
            bus,
            value=25.0,
            external_id="t:2",
            captured_at="2026-09-12T12:01:00+00:00",
        )
    )

    assert first.admission_status == "committed"
    assert second.admission_status == "committed_with_contradiction"
    assert second.contradiction_glyph_id is not None
    assert second.research_need_id is not None

    contradiction = graph.ledger.get(second.contradiction_glyph_id)
    assert contradiction.glyph_type == "critique"
    assert contradiction.content["kind"] == "perception_world_contradiction"
    assert contradiction.content["prior_objects"] == ["20.0"]
    assert contradiction.content["observed_object"] == "25.0"
    assert contradiction.content["authorization_effect"] == "none"

    state = agenda.get(second.research_need_id)
    assert state.status == "pending"
    assert state.need.measurements == rule().research_measurements
    assert "20.0" in state.need.question
    assert "25.0" in state.need.question

    history = world.history(
        subject="reactor:A",
        predicate="temperature_c",
    )
    assert [fact.object for fact in history] == ["20.0", "25.0"]
    assert world.current(
        subject="reactor:A",
        predicate="temperature_c",
    ).object == "25.0"


def test_same_value_new_observation_is_not_marked_contradiction(tmp_path):
    _, bus, _, _, world, agenda, bridge = setup(tmp_path)
    bridge.process(ingest(bus, value=20.0, external_id="t:1"))
    second = bridge.process(
        ingest(
            bus,
            value=20.0,
            external_id="t:2",
            captured_at="2026-09-12T12:01:00+00:00",
        )
    )
    assert second.admission_status == "committed"
    assert second.contradiction_glyph_id is None
    assert second.research_need_id is None
    assert agenda.pending() == ()
    assert len(world.history(
        subject="reactor:A",
        predicate="temperature_c",
    )) == 2


def test_context_uses_current_versioned_head_not_stale_history(tmp_path):
    _, bus, _, _, world, _, bridge = setup(tmp_path)
    bridge.process(ingest(bus, value=20.0, external_id="t:1"))
    bridge.process(
        ingest(
            bus,
            value=25.0,
            external_id="t:2",
            captured_at="2026-09-12T12:01:00+00:00",
        )
    )

    selection = bridge.select_context(query="reactor temperature")
    temperature_facts = [
        f for f in selection.facts
        if f.subject == "reactor:A" and f.predicate == "temperature_c"
    ]
    assert len(temperature_facts) == 1
    assert temperature_facts[0].object == "25.0"
    assert len(world.history(
        subject="reactor:A",
        predicate="temperature_c",
    )) == 2


def test_versioned_rule_requires_predicate_in_world_belief_view(tmp_path):
    _, bus, _, _, _, _, bridge = setup(
        tmp_path,
        versioned=("other_predicate",),
    )
    with pytest.raises(ValueError, match="absent from world belief view"):
        bridge.process(ingest(bus))


def test_unknown_observation_kind_is_rejected(tmp_path):
    graph, bus, core, aura, world, agenda, _ = setup(tmp_path)
    bridge = PerceptionKnowledgeBridge(
        graph=graph,
        core=core,
        aura=aura,
        world_beliefs=world,
        agenda=agenda,
        context_selector=LexicalContextSelector(
            budget=ContextBudget(2, 2),
            k1=1.2,
            b=0.75,
        ),
        rules=(
            PerceptionKnowledgeRule(
                observation_kind="other_kind",
                domain="ops",
                subject_fact="device",
                predicate="temperature_c",
                object_fact="celsius",
                versioned=True,
                allow_world_commit=False,
                minimum_confidence=0.5,
            ),
        ),
    )
    with pytest.raises(ValueError, match="no perception knowledge rule"):
        bridge.process(ingest(bus))


def test_research_configuration_must_be_explicit():
    with pytest.raises(ValueError, match="question template"):
        rule(
            research_on_contradiction=True,
            research_question_template=None,
        )
    with pytest.raises(ValueError, match="measurements"):
        rule(
            research_on_contradiction=True,
            research_measurements=None,
        )


def test_state_update_change_does_not_invent_contradiction(tmp_path):
    _, bus, _, _, world, agenda, bridge = setup(
        tmp_path,
        rules=(
            rule(
                change_semantics="state_update",
                research_on_contradiction=False,
                research_question_template=None,
                research_measurements=None,
            ),
        ),
    )
    first = bridge.process(
        ingest(
            bus,
            value=20.0,
            external_id="t:1",
            captured_at="2026-09-12T12:00:00+00:00",
        )
    )
    second = bridge.process(
        ingest(
            bus,
            value=24.0,
            external_id="t:2",
            captured_at="2026-09-12T12:01:00+00:00",
        )
    )
    assert first.admission_status == "committed"
    assert second.admission_status == "committed"
    assert second.contradiction_glyph_id is None
    assert agenda.pending() == ()
    assert world.current(
        subject="reactor:A",
        predicate="temperature_c",
    ).object == "24.0"


def test_stale_observation_is_evidence_but_cannot_replace_current_head(tmp_path):
    graph, bus, core, aura, world, agenda, bridge = setup(
        tmp_path,
        rules=(
            rule(
                change_semantics="state_update",
                research_on_contradiction=False,
                research_question_template=None,
                research_measurements=None,
            ),
        ),
    )
    bridge.process(
        ingest(
            bus,
            value=24.0,
            external_id="newer",
            captured_at="2026-09-12T12:02:00+00:00",
        )
    )
    stale = bridge.process(
        ingest(
            bus,
            value=18.0,
            external_id="older",
            captured_at="2026-09-12T12:01:00+00:00",
        )
    )
    assert stale.admission_status == "stale_observation"
    assert stale.fact_evidence_id is None
    assert stale.contradiction_glyph_id is not None
    assert world.current(
        subject="reactor:A",
        predicate="temperature_c",
    ).object == "24.0"
    assert len(world.history(
        subject="reactor:A",
        predicate="temperature_c",
    )) == 1
    assert len(aura.research.store.all()) == 2
    critique = graph.ledger.get(stale.contradiction_glyph_id)
    assert critique.content["kind"] == "stale_perception_observation"


def test_simultaneous_incompatible_perceptions_do_not_choose_a_head_silently(tmp_path):
    graph, bus, _, _, world, agenda, bridge = setup(tmp_path)
    bridge.process(
        ingest(
            bus,
            value=20.0,
            external_id="a",
            captured_at="2026-09-12T12:00:00+00:00",
        )
    )
    conflict = bridge.process(
        ingest(
            bus,
            value=25.0,
            external_id="b",
            captured_at="2026-09-12T12:00:00+00:00",
        )
    )
    assert conflict.admission_status == "simultaneous_conflict"
    assert conflict.fact_evidence_id is None
    assert conflict.contradiction_glyph_id is not None
    assert conflict.research_need_id is not None
    assert world.current(
        subject="reactor:A",
        predicate="temperature_c",
    ).object == "20.0"
    assert len(world.history(
        subject="reactor:A",
        predicate="temperature_c",
    )) == 1
    critique = graph.ledger.get(conflict.contradiction_glyph_id)
    assert critique.content["kind"] == "simultaneous_perception_conflict"
    assert len(agenda.pending()) == 1
