import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from test_synergesis_perception_bus import Adapter, percept, setup
from synergesis_perception_bus import PerceptionBus, PerceptionSourcePolicy


def configured(graph, authority="trusted_observation", taint=None):
    security = AegisSecurityGraph(graph)
    bus = PerceptionBus(
        graph=graph,
        security_graph=security,
        source_policies=(PerceptionSourcePolicy("sensor:A", ("temperature",), authority, taint_label=taint),),
        adapters={("sensor:A", "temperature"): Adapter()},
    )
    return security, bus


def test_replay_rejects_changed_authority_or_taint_before_mutation(tmp_path):
    graph, _, bus = setup(tmp_path, taint="external_untrusted")
    record = bus.ingest(percept())
    checkpoint = graph.ledger.verify()
    _, changed_authority = configured(graph, "external_untrusted", "external_untrusted")
    with pytest.raises(ValueError, match="configuration changed"):
        changed_authority.ingest(percept())
    _, changed_taint = configured(graph, "trusted_observation", None)
    with pytest.raises(ValueError, match="configuration changed"):
        changed_taint.ingest(percept())
    assert graph.ledger.verify() == checkpoint
    assert graph.ledger.get(record.raw_glyph_id).content["authority_contract"] == {
        "authority_class": "trusted_observation", "taint_label": "external_untrusted"
    }


def test_contradictory_existing_origin_is_rejected(tmp_path):
    graph, security, bus = setup(tmp_path)
    record = bus.ingest(percept())
    # Append an explicit contradictory binding, simulating corrupted/imported history.
    security.bind_origin(record.raw_glyph_id, authority_class="unknown", reason="test contradiction")
    checkpoint = graph.ledger.verify()
    with pytest.raises(ValueError, match="conflicts"):
        bus.ingest(percept())
    assert graph.ledger.verify() == checkpoint


def test_legacy_raw_without_provenance_is_not_guessed(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "legacy.jsonl"))
    _, bus = configured(graph)
    p = percept()
    digest = bus._percept_digest(p)
    graph.create("observation", actor="SYN-PERCEPTION",
                   content={"kind": "raw_percept", "percept_digest": digest,
                            "source_id": p.source_id, "modality": p.modality,
                            "payload": dict(p.payload), "captured_at": p.captured_at,
                            "external_id": p.external_id, "authority_from_payload": False,
                            "authorization_effect": "none"},
                   external_refs=("percept:sensor:A:reading:1",))
    with pytest.raises(ValueError, match="legacy perception raw"):
        bus.ingest(p)


def test_legacy_raw_with_complete_matching_bindings_can_replay(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "legacy-complete.jsonl"))
    security, bus = configured(graph, taint="external_untrusted")
    p = percept()
    raw = graph.create("observation", actor="SYN-PERCEPTION",
                       content={"kind": "raw_percept", "percept_digest": bus._percept_digest(p),
                                "source_id": p.source_id, "modality": p.modality,
                                "payload": dict(p.payload), "captured_at": p.captured_at,
                                "external_id": p.external_id},
                       external_refs=("percept:sensor:A:reading:1",))
    security.bind_origin(raw.glyph_id, authority_class="trusted_observation", reason="legacy fixture")
    security.mark_taint(raw.glyph_id, label="external_untrusted", reason="legacy fixture")
    record = bus.ingest(p)
    assert record.raw_glyph_id == raw.glyph_id
    assert graph.ledger.get(record.normalized_glyph_id)


def test_taint_clear_and_malformed_contract_are_rejected(tmp_path):
    graph, security, bus = setup(tmp_path, taint="external_untrusted")
    record = bus.ingest(percept())
    active = security._policy_targets("taint", record.raw_glyph_id)[-1]
    security.clear_taint(record.raw_glyph_id, label="external_untrusted", reason="test clear")
    checkpoint = graph.ledger.verify()
    with pytest.raises(ValueError, match="cleared"):
        bus.ingest(percept())
    assert graph.ledger.verify() == checkpoint

    assert active.content["active"] is True


def test_present_but_malformed_contract_is_rejected(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "malformed.jsonl"))
    _, bus = configured(graph)
    p = percept()
    graph.create("observation", actor="SYN-PERCEPTION",
                 content={"kind": "raw_percept", "percept_digest": bus._percept_digest(p),
                          "source_id": p.source_id, "modality": p.modality,
                          "payload": dict(p.payload), "captured_at": p.captured_at,
                          "external_id": p.external_id, "authority_contract": None},
                 external_refs=("percept:sensor:A:reading:1",))
    with pytest.raises(ValueError, match="configuration changed"):
        bus.ingest(p)
