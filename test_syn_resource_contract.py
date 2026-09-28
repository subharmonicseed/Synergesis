"""Regression tests for signed AEGIS capability resource matching contracts."""
from dataclasses import replace

import pytest

from synergesis_aegis import (
    CapabilityGrant,
    CapabilityStore,
    verify_grant_signature,
)

from test_synergesis_aegis import future, proposal, setup_security
from synergesis_aegis import SecurityContext


def test_path_contract_respects_component_boundaries_and_traversal(tmp_path):
    graph, registry, caps, authority, _worker, _security_graph, guard = setup_security(tmp_path)
    grant = authority.issue(
        subject_id="worker",
        action_type="system.admin",
        resource_prefixes=("system:/safe",),
        resource_match_mode="path",
        expires_at=future(),
    )
    caps.add_grant(grant)

    def check(resource):
        return guard.check(
            proposal("system.admin"),
            SecurityContext(actor_id="worker", capability_grant_ids=(grant.grant_id,), resource=resource),
        ).allowed

    assert check("system:/safe") is True
    assert check("system:/safe/child") is True
    assert check("system:/safely/child") is False
    assert check("system:/safe/../admin") is False
    assert check("system:\\safe\\child") is False


def test_exact_contract_is_exact_and_matching_mode_is_signed(tmp_path):
    _graph, registry, caps, authority, _worker, _security_graph, guard = setup_security(tmp_path)
    grant = authority.issue(
        subject_id="worker",
        action_type="system.admin",
        resource_prefixes=("system:/admin",),
        resource_match_mode="exact",
        expires_at=future(),
    )
    caps.add_grant(grant)

    def check(resource):
        return guard.check(
            proposal("system.admin"),
            SecurityContext(actor_id="worker", capability_grant_ids=(grant.grant_id,), resource=resource),
        ).allowed

    assert check("system:/admin") is True
    assert check("system:/admin/child") is False
    tampered = replace(grant, resource_match_mode="path")
    with pytest.raises(ValueError, match="grant id does not match payload|invalid capability signature"):
        verify_grant_signature(tampered, registry)


def test_legacy_prefix_semantics_remain_compatible(tmp_path):
    _graph, _registry, caps, authority, _worker, _security_graph, guard = setup_security(tmp_path)
    grant = authority.issue(
        subject_id="worker",
        action_type="system.admin",
        resource_prefixes=("system:/safe",),
        expires_at=future(),
    )
    assert grant.resource_match_mode == "legacy_prefix"
    caps.add_grant(grant)
    result = guard.check(
        proposal("system.admin"),
        SecurityContext(actor_id="worker", capability_grant_ids=(grant.grant_id,), resource="system:/safely"),
    )
    assert result.allowed is True


def test_unknown_mode_is_rejected_during_construction_and_store_load(tmp_path):
    _graph, _registry, caps, authority, _worker, _security_graph, _guard = setup_security(tmp_path)
    grant = authority.issue(
        subject_id="worker",
        action_type="system.admin",
        resource_prefixes=("system:/admin",),
        expires_at=future(),
    )
    with pytest.raises(ValueError, match="unknown capability resource matching mode"):
        replace(grant, resource_match_mode="prefix-or-path")

    caps.add_grant(grant)
    raw = caps.path.read_text(encoding="utf-8")
    caps.path.write_text(raw.replace('"resource_match_mode": "legacy_prefix"', '"resource_match_mode": "widened"'), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown capability resource matching mode"):
        CapabilityStore(caps.path).grants()
