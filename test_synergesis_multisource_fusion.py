import json

import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_multisource_fusion import (
    FusionPolicy,
    FusionSourceProfile,
    MultisourcePerceptionFusion,
    PerceptionReliabilityLedger,
)
from synergesis_perception_bus import (
    NormalizedPercept,
    PerceptionBus,
    PerceptionSourcePolicy,
    RawPercept,
)
from synergesis_roam_attention import (
    AttentionMeasurements,
    AttentionWeights,
    ResearchAgenda,
)


class Adapter:
    def __init__(self, confidence=0.9):
        self.confidence = confidence

    def normalize(self, percept):
        return NormalizedPercept(
            observation_kind="device_state",
            facts={
                "device": percept.payload["device"],
                "state": percept.payload["state"],
            },
            confidence=self.confidence,
        )


def policy(**overrides):
    values = dict(
        observation_kind="device_state",
        subject_fact="device",
        object_fact="state",
        minimum_origin_rank=2,
        max_time_span_seconds=5.0,
        minimum_independent_groups=2,
        minimum_support=1.0,
        minimum_support_margin=0.2,
        reliability_prior_alpha=1.0,
        reliability_prior_beta=1.0,
        minimum_reliability_observations=2,
        minimum_adjudication_origin_rank=5,
        research_on_unresolved=True,
        research_domain="operations",
        research_question_template=(
            "Resolve multisource state for {subject}: claims={claims}; reason={reason}"
        ),
        research_measurements=AttentionMeasurements(
            uncertainty=0.9,
            expected_impact=0.6,
            staleness=0.1,
            novelty_gap=0.8,
        ),
    )
    values.update(overrides)
    return FusionPolicy(**values)


def setup(
    tmp_path,
    *,
    profiles=None,
    authorities=None,
    fusion_policy=None,
):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    profiles = tuple(
        profiles
        or (
            FusionSourceProfile("sensor:a", "group:a", 0.8),
            FusionSourceProfile("sensor:b", "group:b", 0.8),
            FusionSourceProfile("sensor:c", "group:c", 0.8),
        )
    )
    authorities = authorities or {
        profile.source_id: "trusted_observation"
        for profile in profiles
    }
    source_policies = tuple(
        PerceptionSourcePolicy(
            profile.source_id,
            ("state",),
            authorities[profile.source_id],
        )
        for profile in profiles
    )
    bus = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=source_policies,
        adapters={
            (profile.source_id, "state"): Adapter()
            for profile in profiles
        },
    )
    agenda = ResearchAgenda(
        tmp_path / "agenda.jsonl",
        graph=graph,
        weights=AttentionWeights(1, 1, 1, 1),
    )
    reliability = PerceptionReliabilityLedger(
        tmp_path / "reliability.jsonl"
    )
    fusion = MultisourcePerceptionFusion(
        graph=graph,
        security_graph=security,
        profiles=profiles,
        policy=fusion_policy or policy(),
        reliability_ledger=reliability,
        agenda=agenda,
    )
    return graph, security, bus, agenda, reliability, fusion


def ingest(
    bus,
    source_id,
    state,
    *,
    external_id=None,
    captured_at="2026-09-12T12:00:00+00:00",
):
    return bus.ingest(
        RawPercept(
            source_id=source_id,
            modality="state",
            payload={"device": "node:A", "state": state},
            captured_at=captured_at,
            external_id=external_id or f"{source_id}:{state}:{captured_at}",
        )
    )


def adjudication(graph, security, record, *, correct, authority="runtime_attested"):
    glyph = graph.create(
        "observation",
        actor="reference-observer",
        content={
            "kind": "perception_reference_adjudication",
            "normalized_glyph_id": record.normalized_glyph_id,
            "correct": correct,
        },
    )
    security.bind_origin(
        glyph.glyph_id,
        authority_class=authority,
        reason="independent reference adjudication",
    )
    graph.relate(
        glyph.glyph_id,
        record.normalized_glyph_id,
        "evaluates",
        actor="reference-observer",
    )
    return glyph


def test_two_sources_same_independence_group_do_not_count_as_two_witnesses(tmp_path):
    profiles = (
        FusionSourceProfile("sensor:a", "shared", 0.9),
        FusionSourceProfile("sensor:b", "shared", 0.8),
    )
    _, _, bus, agenda, _, fusion = setup(
        tmp_path,
        profiles=profiles,
    )
    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "on"),
            ingest(bus, "sensor:b", "on"),
        )
    )
    assert result.status == "unresolved"
    assert result.reason == "insufficient_independent_groups"
    assert result.support_by_claim["on"] == pytest.approx(0.9)
    assert result.independent_groups_supporting_winner == 1
    assert len(agenda.pending()) == 1


def test_two_independent_sources_can_resolve_when_thresholds_are_met(tmp_path):
    _, _, bus, agenda, _, fusion = setup(tmp_path)
    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "on"),
            ingest(bus, "sensor:b", "on"),
        )
    )
    assert result.status == "resolved"
    assert result.selected_claim == "on"
    assert result.winner_support == pytest.approx(1.6)
    assert result.independent_groups_supporting_winner == 2
    assert result.research_need_id is None
    assert agenda.pending() == ()


def test_source_count_does_not_beat_one_more_reliable_independent_source(tmp_path):
    profiles = (
        FusionSourceProfile("sensor:a", "group:a", 0.3),
        FusionSourceProfile("sensor:b", "group:b", 0.3),
        FusionSourceProfile("sensor:c", "group:c", 0.9),
    )
    _, _, bus, _, _, fusion = setup(
        tmp_path,
        profiles=profiles,
        fusion_policy=policy(
            minimum_independent_groups=1,
            minimum_support=0.5,
            minimum_support_margin=0.2,
        ),
    )
    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "on"),
            ingest(bus, "sensor:b", "on"),
            ingest(bus, "sensor:c", "off"),
        )
    )
    assert result.status == "resolved"
    assert result.selected_claim == "off"
    assert result.support_by_claim == pytest.approx(
        {"off": 0.9, "on": 0.6}
    )


def test_authority_is_eligibility_only_not_weight(tmp_path):
    profiles = (
        FusionSourceProfile("sensor:a", "group:a", 0.99),
        FusionSourceProfile("sensor:b", "group:b", 0.8),
        FusionSourceProfile("sensor:c", "group:c", 0.8),
    )
    authorities = {
        "sensor:a": "external_untrusted",
        "sensor:b": "trusted_observation",
        "sensor:c": "trusted_observation",
    }
    _, _, bus, _, _, fusion = setup(
        tmp_path,
        profiles=profiles,
        authorities=authorities,
    )
    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "off"),
            ingest(bus, "sensor:b", "on"),
            ingest(bus, "sensor:c", "on"),
        )
    )
    assert result.status == "resolved"
    assert result.selected_claim == "on"
    a = {
        item.source_id: item
        for item in result.source_contributions
    }["sensor:a"]
    assert a.eligible is False
    assert a.reason == "origin_rank_below_minimum"


def test_equal_independent_support_is_left_unresolved(tmp_path):
    _, _, bus, agenda, _, fusion = setup(
        tmp_path,
        fusion_policy=policy(
            minimum_independent_groups=1,
            minimum_support=0.5,
        ),
    )
    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "on"),
            ingest(bus, "sensor:b", "off"),
        )
    )
    assert result.status == "unresolved"
    assert result.reason == "support_tie"
    assert result.selected_claim is None
    assert result.research_need_id is not None
    assert agenda.get(result.research_need_id).status == "pending"


def test_conflict_inside_one_independence_group_contributes_no_support(tmp_path):
    profiles = (
        FusionSourceProfile("sensor:a", "shared", 0.9),
        FusionSourceProfile("sensor:b", "shared", 0.9),
        FusionSourceProfile("sensor:c", "independent", 0.9),
    )
    _, _, bus, _, _, fusion = setup(
        tmp_path,
        profiles=profiles,
        fusion_policy=policy(
            minimum_independent_groups=1,
            minimum_support=0.5,
        ),
    )
    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "on"),
            ingest(bus, "sensor:b", "off"),
            ingest(bus, "sensor:c", "on"),
        )
    )
    shared = {
        item.independence_group: item
        for item in result.group_contributions
    }["shared"]
    assert shared.status == "internal_conflict"
    assert shared.support == pytest.approx(0.0)
    assert result.support_by_claim == pytest.approx({"on": 0.9})


def test_empirical_reliability_requires_separate_high_authority_adjudication(tmp_path):
    graph, security, bus, _, ledger, fusion = setup(
        tmp_path,
        fusion_policy=policy(
            minimum_reliability_observations=2,
            minimum_independent_groups=1,
            minimum_support=0.1,
            minimum_support_margin=0.1,
        ),
    )
    records = (
        ingest(bus, "sensor:a", "on", external_id="a:1"),
        ingest(bus, "sensor:a", "on", external_id="a:2"),
    )
    for record in records:
        adj = adjudication(
            graph,
            security,
            record,
            correct=False,
        )
        fusion.adjudicate(
            record=record,
            adjudication_glyph_id=adj.glyph_id,
        )

    estimate = fusion.reliability("sensor:a")
    assert estimate.observations == 2
    assert estimate.source == "empirical"
    assert estimate.posterior_mean == pytest.approx(0.25)
    assert estimate.effective_reliability == pytest.approx(0.25)
    assert ledger.verify()[0] == 2


def test_low_authority_or_unlinked_adjudication_cannot_train_reliability(tmp_path):
    graph, security, bus, _, ledger, fusion = setup(tmp_path)
    record = ingest(bus, "sensor:a", "on")

    low = adjudication(
        graph,
        security,
        record,
        correct=True,
        authority="trusted_observation",
    )
    with pytest.raises(ValueError, match="rank below"):
        fusion.adjudicate(
            record=record,
            adjudication_glyph_id=low.glyph_id,
        )
    assert ledger.records() == ()

    high = graph.create(
        "observation",
        actor="reference",
        content={
            "kind": "perception_reference_adjudication",
            "normalized_glyph_id": record.normalized_glyph_id,
            "correct": True,
        },
    )
    security.bind_origin(
        high.glyph_id,
        authority_class="runtime_attested",
        reason="reference",
    )
    with pytest.raises(ValueError, match="not linked"):
        fusion.adjudicate(
            record=record,
            adjudication_glyph_id=high.glyph_id,
        )
    assert ledger.records() == ()


def test_empirical_reliability_can_change_fusion_without_changing_authority(tmp_path):
    profiles = (
        FusionSourceProfile("sensor:a", "group:a", 0.9),
        FusionSourceProfile("sensor:b", "group:b", 0.6),
    )
    graph, security, bus, _, _, fusion = setup(
        tmp_path,
        profiles=profiles,
        fusion_policy=policy(
            minimum_reliability_observations=2,
            minimum_independent_groups=1,
            minimum_support=0.1,
            minimum_support_margin=0.1,
        ),
    )

    training = (
        ingest(bus, "sensor:a", "on", external_id="train:a1"),
        ingest(bus, "sensor:a", "on", external_id="train:a2"),
    )
    for record in training:
        adj = adjudication(graph, security, record, correct=False)
        fusion.adjudicate(record=record, adjudication_glyph_id=adj.glyph_id)

    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "on", external_id="live:a"),
            ingest(bus, "sensor:b", "off", external_id="live:b"),
        )
    )
    assert result.status == "resolved"
    assert result.selected_claim == "off"

    a = {
        item.source_id: item
        for item in result.source_contributions
    }["sensor:a"]
    assert a.reliability_source == "empirical"
    assert a.reliability == pytest.approx(0.25)
    # Origin authority remains the configured provenance label; learning only
    # changes reliability support.
    raw = bus.graph.ledger.get(
        ingest(bus, "sensor:a", "on", external_id="authority-check").raw_glyph_id
    )
    binding = security.origin_binding(raw.glyph_id)
    assert binding.content["authority_class"] == "trusted_observation"


def test_time_span_beyond_policy_is_unresolved(tmp_path):
    _, _, bus, _, _, fusion = setup(tmp_path)
    result = fusion.fuse(
        (
            ingest(
                bus,
                "sensor:a",
                "on",
                captured_at="2026-09-12T12:00:00+00:00",
            ),
            ingest(
                bus,
                "sensor:b",
                "on",
                captured_at="2026-09-12T12:01:00+00:00",
            ),
        )
    )
    assert result.status == "unresolved"
    assert result.reason == "time_span_exceeds_policy"


def test_fusion_glyph_explicitly_denies_truth_probability_semantics(tmp_path):
    graph, _, bus, _, _, fusion = setup(tmp_path)
    result = fusion.fuse(
        (
            ingest(bus, "sensor:a", "on"),
            ingest(bus, "sensor:b", "on"),
        )
    )
    glyph = graph.ledger.get(result.inference_glyph_id)
    assert glyph.glyph_type == "inference"
    assert glyph.content["authority_semantics"] == "eligibility_only"
    assert (
        glyph.content["support_semantics"]
        == "weighted_independent_support_not_truth_probability"
    )
    assert glyph.content["source_count_is_not_independence"] is True
    assert glyph.content["authorization_effect"] == "none"


def test_reliability_ledger_detects_tampering(tmp_path):
    graph, security, bus, _, ledger, fusion = setup(tmp_path)
    record = ingest(bus, "sensor:a", "on")
    adj = adjudication(graph, security, record, correct=True)
    fusion.adjudicate(record=record, adjudication_glyph_id=adj.glyph_id)

    raw = ledger.path.read_text(encoding="utf-8")
    ledger.path.write_text(
        raw.replace('"correct":true', '"correct":false'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.verify()


def test_fusion_policy_and_profile_reject_ambiguous_numeric_configuration():
    with pytest.raises(ValueError, match="configured_reliability"):
        FusionSourceProfile("sensor:x", "group:x", True)

    with pytest.raises(ValueError, match="minimum_origin_rank"):
        policy(minimum_origin_rank=1.5)

    with pytest.raises(ValueError, match="minimum_independent_groups"):
        policy(minimum_independent_groups=True)

    with pytest.raises(ValueError, match="reliability_prior_alpha"):
        policy(reliability_prior_alpha=float("nan"))

    with pytest.raises(ValueError, match="minimum_reliability_observations"):
        policy(minimum_reliability_observations=True)

    with pytest.raises(ValueError, match="minimum_adjudication_origin_rank"):
        policy(minimum_adjudication_origin_rank=4.5)
