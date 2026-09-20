from datetime import datetime, timedelta, timezone

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


def setup(tmp_path, *, profile):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    registry = IdentityRegistry(tmp_path / "identities.jsonl")
    caps = CapabilityStore(tmp_path / "caps.jsonl")
    signer = IdentitySigner("ZÆL-0")
    registry.register("ZÆL-0", signer.public_key)
    guard = AegisGuard(
        graph=graph,
        identity_registry=registry,
        capability_store=caps,
        trusted_capability_issuers=frozenset(),
        allowed_actions=frozenset({"note.write"}),
        profiles=(profile,),
        security_graph=security,
    )
    return graph, security, guard


def proposal():
    return ActionProposal.create(
        "note.write",
        {"text": "x"},
        rationale="test",
        expected_outcome="written",
        strategy_key="origin-test",
    )


def test_external_origin_remains_visible_through_multiple_derivations(tmp_path):
    graph, security, guard = setup(
        tmp_path,
        profile=ActionSecurityProfile(
            "note.write",
            False,
            frozenset(),
            require_bound_origins=True,
        ),
    )
    root = graph.create("evidence", actor="web", content={"x": 1})
    security.bind_origin(
        root.glyph_id,
        authority_class="external_untrusted",
        reason="web ingress",
    )
    middle = graph.create(
        "hypothesis",
        actor="syn",
        content={"h": 1},
        derived_from=(root.glyph_id,),
    )
    child = graph.create(
        "action",
        actor="syn",
        content={"a": 1},
        derived_from=(middle.glyph_id,),
    )

    assessed = security.assess_provenance((child.glyph_id,))
    assert assessed.root_glyph_ids == (root.glyph_id,)
    assert assessed.unbound_root_glyph_ids == ()
    assert assessed.minimum_origin_rank == 1
    assert assessed.origin_bindings[0]["authority_class"] == "external_untrusted"


def test_origin_authority_cannot_be_upgraded_by_rebinding(tmp_path):
    graph, security, guard = setup(
        tmp_path,
        profile=ActionSecurityProfile("note.write", False, frozenset()),
    )
    root = graph.create("evidence", actor="web", content={"x": 1})
    security.bind_origin(
        root.glyph_id,
        authority_class="external_untrusted",
        reason="web ingress",
    )
    with pytest.raises(ValueError, match="cannot be elevated"):
        security.bind_origin(
            root.glyph_id,
            authority_class="trusted_observation",
            reason="trusted tool echoed the same content",
        )


def test_origin_authority_may_be_lowered_after_compromise(tmp_path):
    graph, security, guard = setup(
        tmp_path,
        profile=ActionSecurityProfile("note.write", False, frozenset()),
    )
    root = graph.create("observation", actor="sensor", content={"x": 1})
    first = security.bind_origin(
        root.glyph_id,
        authority_class="trusted_observation",
        reason="authenticated sensor ingress",
    )
    second = security.bind_origin(
        root.glyph_id,
        authority_class="external_untrusted",
        reason="sensor key later found compromised",
    )
    assert first.glyph_id != second.glyph_id
    current = security.origin_binding(root.glyph_id)
    assert current.content["authority_class"] == "external_untrusted"
    assert current.content["rank"] == 1


def test_laundered_content_with_broken_lineage_becomes_unbound_and_is_denied(tmp_path):
    graph, security, guard = setup(
        tmp_path,
        profile=ActionSecurityProfile(
            "note.write",
            False,
            frozenset(),
            require_bound_origins=True,
        ),
    )
    original = graph.create("evidence", actor="web", content={"text": "untrusted"})
    security.bind_origin(
        original.glyph_id,
        authority_class="external_untrusted",
        reason="web ingress",
    )

    # A trusted-looking tool echo that deliberately/accidentally drops the
    # derived_from edge. It cannot inherit authority by actor name alone.
    echo = graph.create(
        "fact",
        actor="trusted_tool",
        content={"text": "same idea, rewritten"},
    )
    action = graph.create(
        "action",
        actor="syn",
        content={"action_type": "note.write"},
        derived_from=(echo.glyph_id,),
    )

    decision = guard.check(
        proposal(),
        SecurityContext(
            actor_id="ZÆL-0",
            provenance_glyph_ids=(action.glyph_id,),
            resource="action:note.write",
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "aegis:unbound_origin"


def test_minimum_origin_rank_blocks_external_origin_even_with_complete_lineage(tmp_path):
    graph, security, guard = setup(
        tmp_path,
        profile=ActionSecurityProfile(
            "note.write",
            False,
            frozenset(),
            require_bound_origins=True,
            minimum_origin_rank=3,
        ),
    )
    root = graph.create("evidence", actor="web", content={"x": 1})
    security.bind_origin(
        root.glyph_id,
        authority_class="external_untrusted",
        reason="web ingress",
    )
    action = graph.create(
        "action",
        actor="syn",
        content={"action_type": "note.write"},
        derived_from=(root.glyph_id,),
    )
    decision = guard.check(
        proposal(),
        SecurityContext(
            actor_id="ZÆL-0",
            provenance_glyph_ids=(action.glyph_id,),
            resource="action:note.write",
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "aegis:origin_authority_below_threshold"


def test_trusted_bound_origin_can_meet_threshold(tmp_path):
    graph, security, guard = setup(
        tmp_path,
        profile=ActionSecurityProfile(
            "note.write",
            False,
            frozenset(),
            require_bound_origins=True,
            minimum_origin_rank=3,
        ),
    )
    root = graph.create("observation", actor="sensor", content={"x": 1})
    security.bind_origin(
        root.glyph_id,
        authority_class="trusted_observation",
        reason="trusted sensor",
    )
    action = graph.create(
        "action",
        actor="syn",
        content={"action_type": "note.write"},
        derived_from=(root.glyph_id,),
    )
    decision = guard.check(
        proposal(),
        SecurityContext(
            actor_id="ZÆL-0",
            provenance_glyph_ids=(action.glyph_id,),
            resource="action:note.write",
        ),
    )
    assert decision.allowed is True


def test_origin_binding_is_present_in_aegis_audit_decision(tmp_path):
    graph, security, guard = setup(
        tmp_path,
        profile=ActionSecurityProfile(
            "note.write",
            False,
            frozenset(),
            require_bound_origins=True,
        ),
    )
    root = graph.create("observation", actor="user", content={"x": 1})
    binding = security.bind_origin(
        root.glyph_id,
        authority_class="user_intent",
        reason="authenticated user request",
    )
    action = graph.create(
        "action",
        actor="syn",
        content={"action_type": "note.write"},
        derived_from=(root.glyph_id,),
    )
    p = proposal()
    decision = guard.check(
        p,
        SecurityContext(
            actor_id="ZÆL-0",
            provenance_glyph_ids=(action.glyph_id,),
            resource="action:note.write",
        ),
    )
    assert decision.allowed
    policies = graph.ledger.find_by_external_ref(
        f"aegis:{p.proposal_id}",
        glyph_type="policy",
    )
    assert policies
    audit = policies[-1]
    assert audit.content["minimum_origin_rank"] == 4
    assert audit.content["origin_bindings"][0]["policy_glyph_id"] == binding.glyph_id
