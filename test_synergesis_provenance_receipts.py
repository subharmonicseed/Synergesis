from dataclasses import replace

import pytest

from synergesis_aegis import (
    ActionSecurityProfile,
    AegisGuard,
    AegisSecurityGraph,
    CapabilityStore,
    IdentityRegistry,
    IdentitySigner,
    SecurityContext,
)
from synergesis_agent_loop_v2 import ActionProposal
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_provenance_receipts import (
    ProvenanceReceiptAuthority,
    ProvenanceReceiptStore,
    ProvenanceReceiptVerifier,
    bind_verified_origin_receipt,
)


def setup(tmp_path, *, minimum_rank=3):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)

    registry = IdentityRegistry(tmp_path / "identities.jsonl")
    ingress = IdentitySigner("ingress")
    relay = IdentitySigner("relay")
    syn = IdentitySigner("ZÆL-0")
    registry.register("ingress", ingress.public_key)
    registry.register("relay", relay.public_key)
    registry.register("ZÆL-0", syn.public_key)

    store = ProvenanceReceiptStore(tmp_path / "receipts.jsonl")
    verifier = ProvenanceReceiptVerifier(
        store=store,
        identity_registry=registry,
        trusted_origin_issuers=frozenset({"ingress"}),
        trusted_derivation_issuers=frozenset({"relay"}),
        origin_ranks=security.ORIGIN_CLASSES,
    )

    guard = AegisGuard(
        graph=graph,
        identity_registry=registry,
        capability_store=CapabilityStore(tmp_path / "caps.jsonl"),
        trusted_capability_issuers=frozenset(),
        allowed_actions=frozenset({"system.change"}),
        profiles=(
            ActionSecurityProfile(
                "system.change",
                False,
                frozenset(),
                require_bound_origins=True,
                minimum_origin_rank=minimum_rank,
            ),
        ),
        security_graph=security,
    )
    return (
        graph,
        security,
        registry,
        store,
        verifier,
        guard,
        ProvenanceReceiptAuthority(ingress),
        ProvenanceReceiptAuthority(relay),
    )


def proposal():
    return ActionProposal.create(
        "system.change",
        {"x": 1},
        rationale="receipt test",
        expected_outcome="decision",
        strategy_key="receipt-test",
    )


def test_receipt_chain_recovers_true_origin_after_graph_edge_loss(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)

    origin = graph.create("evidence", actor="web", content={"payload": "x"})
    r0 = ingress.issue_origin(
        glyph_id=origin.glyph_id,
        authority_class="external_untrusted",
        rank=security.ORIGIN_CLASSES["external_untrusted"],
    )
    store.append(r0)

    relay1 = graph.create(
        "concept",
        actor="relay",
        content={"summary": "x"},
        derived_from=(origin.glyph_id,),
    )
    r1 = relay.issue_derivation(
        glyph_id=relay1.glyph_id,
        parent_receipt_id=r0.receipt_id,
        transform_kind="summary",
    )
    store.append(r1)

    # Local lineage is now deliberately broken at the next process boundary.
    relay2 = graph.create(
        "observation",
        actor="relay",
        content={"forwarded": "x"},
    )
    r2 = relay.issue_derivation(
        glyph_id=relay2.glyph_id,
        parent_receipt_id=r1.receipt_id,
        transform_kind="cross_process_relay",
    )
    store.append(r2)

    trace = bind_verified_origin_receipt(
        security_graph=security,
        glyph_id=relay2.glyph_id,
        receipt_id=r2.receipt_id,
        verifier=verifier,
    )
    assert trace.true_origin_glyph_id == origin.glyph_id
    assert trace.origin_authority_class == "external_untrusted"
    assert trace.hops == 2

    assessment = security.assess_provenance((relay2.glyph_id,))
    assert assessment.unbound_root_glyph_ids == ()
    binding = assessment.origin_bindings[0]
    assert binding["true_origin_glyph_id"] == origin.glyph_id
    assert binding["receipt_hops"] == 2


def test_recovered_external_origin_still_cannot_be_laundered_into_trust(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)

    origin = graph.create("evidence", actor="web", content={"payload": "x"})
    r0 = ingress.issue_origin(
        glyph_id=origin.glyph_id,
        authority_class="external_untrusted",
        rank=1,
    )
    store.append(r0)

    new_root = graph.create("fact", actor="trusted_tool", content={"payload": "rewritten"})
    r1 = relay.issue_derivation(
        glyph_id=new_root.glyph_id,
        parent_receipt_id=r0.receipt_id,
        transform_kind="trusted_tool_echo",
    )
    store.append(r1)
    bind_verified_origin_receipt(
        security_graph=security,
        glyph_id=new_root.glyph_id,
        receipt_id=r1.receipt_id,
        verifier=verifier,
    )

    action = graph.create(
        "action",
        actor="ZÆL-0",
        content={"action_type": "system.change"},
        derived_from=(new_root.glyph_id,),
    )
    decision = guard.check(
        proposal(),
        SecurityContext(
            actor_id="ZÆL-0",
            provenance_glyph_ids=(action.glyph_id,),
            resource="action:system.change",
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "aegis:origin_authority_below_threshold"


def test_trusted_origin_receipt_can_survive_broken_local_lineage(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)

    origin = graph.create("observation", actor="sensor", content={"value": 42})
    r0 = ingress.issue_origin(
        glyph_id=origin.glyph_id,
        authority_class="trusted_observation",
        rank=3,
    )
    store.append(r0)

    new_root = graph.create("fact", actor="relay", content={"value": 42})
    r1 = relay.issue_derivation(
        glyph_id=new_root.glyph_id,
        parent_receipt_id=r0.receipt_id,
        transform_kind="cross_process_copy",
    )
    store.append(r1)
    bind_verified_origin_receipt(
        security_graph=security,
        glyph_id=new_root.glyph_id,
        receipt_id=r1.receipt_id,
        verifier=verifier,
    )

    action = graph.create(
        "action",
        actor="ZÆL-0",
        content={"action_type": "system.change"},
        derived_from=(new_root.glyph_id,),
    )
    decision = guard.check(
        proposal(),
        SecurityContext(
            actor_id="ZÆL-0",
            provenance_glyph_ids=(action.glyph_id,),
            resource="action:system.change",
        ),
    )
    assert decision.allowed is True


def test_missing_receipt_on_broken_lineage_still_fails_closed(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)
    orphan = graph.create("fact", actor="relay", content={"x": 1})
    action = graph.create(
        "action",
        actor="ZÆL-0",
        content={"action_type": "system.change"},
        derived_from=(orphan.glyph_id,),
    )
    decision = guard.check(
        proposal(),
        SecurityContext(
            actor_id="ZÆL-0",
            provenance_glyph_ids=(action.glyph_id,),
            resource="action:system.change",
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "aegis:unbound_origin"


def test_receipt_cannot_be_reused_for_different_leaf_glyph(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)
    origin = graph.create("evidence", actor="web", content={"x": 1})
    r0 = ingress.issue_origin(
        glyph_id=origin.glyph_id,
        authority_class="external_untrusted",
        rank=1,
    )
    store.append(r0)

    other = graph.create("fact", actor="relay", content={"x": 2})
    with pytest.raises(ValueError, match="does not bind requested glyph"):
        verifier.verify_for_glyph(r0.receipt_id, other.glyph_id)


def test_untrusted_derivation_issuer_is_rejected(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)
    rogue = IdentitySigner("rogue")
    registry.register("rogue", rogue.public_key)
    rogue_authority = ProvenanceReceiptAuthority(rogue)

    origin = graph.create("evidence", actor="web", content={"x": 1})
    r0 = ingress.issue_origin(
        glyph_id=origin.glyph_id,
        authority_class="external_untrusted",
        rank=1,
    )
    store.append(r0)

    child = graph.create("fact", actor="rogue", content={"x": 1})
    r1 = rogue_authority.issue_derivation(
        glyph_id=child.glyph_id,
        parent_receipt_id=r0.receipt_id,
        transform_kind="rogue_relay",
    )
    store.append(r1)

    with pytest.raises(ValueError, match="untrusted derivation"):
        verifier.verify_for_glyph(r1.receipt_id, child.glyph_id)


def test_tampered_receipt_store_is_detected(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)
    origin = graph.create("evidence", actor="web", content={"x": 1})
    r0 = ingress.issue_origin(
        glyph_id=origin.glyph_id,
        authority_class="external_untrusted",
        rank=1,
    )
    store.append(r0)

    raw = store.path.read_text(encoding="utf-8")
    store.path.write_text(raw.replace('"rank":1', '"rank":5'), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity failure"):
        store.events()


def test_origin_rank_must_match_aegis_policy(tmp_path):
    graph, security, registry, store, verifier, guard, ingress, relay = setup(tmp_path)
    origin = graph.create("evidence", actor="web", content={"x": 1})
    bad = ingress.issue_origin(
        glyph_id=origin.glyph_id,
        authority_class="external_untrusted",
        rank=5,
    )
    store.append(bad)
    with pytest.raises(ValueError, match="rank does not match"):
        verifier.verify_for_glyph(bad.receipt_id, origin.glyph_id)
