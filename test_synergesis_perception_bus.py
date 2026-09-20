import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_perception_bus import (
    NormalizedPercept,
    PerceptionBus,
    PerceptionSourcePolicy,
    RawPercept,
)


class Adapter:
    def __init__(self, confidence=0.8):
        self.confidence = confidence

    def normalize(self, percept):
        return NormalizedPercept(
            observation_kind=f"{percept.modality}_reading",
            facts={"value": percept.payload["value"]},
            confidence=self.confidence,
        )


def setup(tmp_path, *, authority="trusted_observation", taint=None, confidence=0.8):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    bus = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=(
            PerceptionSourcePolicy(
                source_id="sensor:A",
                allowed_modalities=("temperature",),
                origin_authority_class=authority,
                taint_label=taint,
            ),
        ),
        adapters={
            ("sensor:A", "temperature"): Adapter(confidence),
        },
    )
    return graph, security, bus


def percept(**overrides):
    values = dict(
        source_id="sensor:A",
        modality="temperature",
        payload={"value": 21.5},
        captured_at="2026-09-12T12:00:00+00:00",
        external_id="reading:1",
    )
    values.update(overrides)
    return RawPercept(**values)


def test_ingest_creates_raw_and_normalized_glyphs_with_configured_origin(tmp_path):
    graph, security, bus = setup(tmp_path)
    record = bus.ingest(percept())

    raw = graph.ledger.get(record.raw_glyph_id)
    normalized = graph.ledger.get(record.normalized_glyph_id)
    assert raw.content["kind"] == "raw_percept"
    assert normalized.content["kind"] == "normalized_perception"
    assert normalized.content["facts"]["value"] == 21.5
    assert normalized.confidence == pytest.approx(0.8)

    binding = security.origin_binding(raw.glyph_id)
    assert binding.content["authority_class"] == "trusted_observation"
    assert any(
        edge.source == normalized.glyph_id
        and edge.target == raw.glyph_id
        and edge.relation == "derived_from"
        for edge in graph.ledger.edges_from(normalized.glyph_id)
    )


def test_payload_cannot_choose_or_elevate_authority(tmp_path):
    graph, security, bus = setup(
        tmp_path,
        authority="external_untrusted",
    )
    p = percept(
        payload={
            "value": 21.5,
            "authority_class": "system",
            "runtime_attested": True,
        }
    )
    record = bus.ingest(p)
    raw = graph.ledger.get(record.raw_glyph_id)
    binding = security.origin_binding(raw.glyph_id)

    assert raw.content["payload"]["authority_class"] == "system"
    assert raw.content["authority_from_payload"] is False
    assert binding.content["authority_class"] == "external_untrusted"


def test_missing_confidence_stays_none(tmp_path):
    graph, _, bus = setup(tmp_path, confidence=None)
    record = bus.ingest(percept())
    normalized = graph.ledger.get(record.normalized_glyph_id)
    assert normalized.confidence is None
    assert normalized.content["confidence_available"] is False


def test_configured_taint_is_applied_to_raw_source(tmp_path):
    graph, security, bus = setup(
        tmp_path,
        authority="external_untrusted",
        taint="external_untrusted",
    )
    record = bus.ingest(percept())
    taints = security._policy_targets("taint", record.raw_glyph_id)
    assert taints
    assert taints[-1].content["label"] == "external_untrusted"


def test_exact_replay_deduplicates_raw_and_normalized_glyphs(tmp_path):
    graph, _, bus = setup(tmp_path)
    first = bus.ingest(percept())
    second = bus.ingest(percept())
    assert second.raw_glyph_id == first.raw_glyph_id
    assert second.normalized_glyph_id == first.normalized_glyph_id


def test_same_external_id_with_different_payload_is_rejected(tmp_path):
    _, _, bus = setup(tmp_path)
    bus.ingest(percept())
    with pytest.raises(ValueError, match="collision"):
        bus.ingest(percept(payload={"value": 99.0}))


def test_unknown_disabled_or_wrong_modality_is_rejected(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    bus = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=(
            PerceptionSourcePolicy(
                "sensor:A",
                ("temperature",),
                "trusted_observation",
                enabled=False,
            ),
        ),
        adapters={
            ("sensor:A", "temperature"): Adapter(),
        },
    )
    with pytest.raises(ValueError, match="disabled"):
        bus.ingest(percept())
    with pytest.raises(ValueError, match="unknown"):
        bus.ingest(percept(source_id="sensor:unknown"))

    enabled = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=(
            PerceptionSourcePolicy(
                "sensor:A",
                ("temperature",),
                "trusted_observation",
            ),
        ),
        adapters={
            ("sensor:A", "temperature"): Adapter(),
        },
    )
    with pytest.raises(ValueError, match="not allowed"):
        enabled.ingest(percept(modality="audio"))


def test_missing_adapter_is_rejected(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    bus = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=(
            PerceptionSourcePolicy(
                "sensor:A",
                ("temperature",),
                "trusted_observation",
            ),
        ),
        adapters={},
    )
    with pytest.raises(ValueError, match="no perception adapter"):
        bus.ingest(percept())


def test_invalid_policy_authority_is_rejected(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    with pytest.raises(ValueError, match="unsupported"):
        PerceptionBus(
            graph=graph,
            security_graph=security,
            source_policies=(
                PerceptionSourcePolicy(
                    "sensor:A",
                    ("temperature",),
                    "made_up_authority",
                ),
            ),
            adapters={
                ("sensor:A", "temperature"): Adapter(),
            },
        )


def test_adapter_cannot_return_invalid_type(tmp_path):
    class BadAdapter:
        def normalize(self, percept):
            return {"value": 1}

    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    bus = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=(
            PerceptionSourcePolicy(
                "sensor:A",
                ("temperature",),
                "trusted_observation",
            ),
        ),
        adapters={
            ("sensor:A", "temperature"): BadAdapter(),
        },
    )
    with pytest.raises(TypeError, match="NormalizedPercept"):
        bus.ingest(percept())
