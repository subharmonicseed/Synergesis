from synergesis_aegis import (
    ActionSecurityProfile,
    AegisGuard,
    CapabilityAuthority,
    CapabilityStore,
    IdentityRegistry,
    IdentitySigner,
    SecurityContext,
)
from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentObservation,
    Goal,
    Hypothesis,
    LearningSignal,
    PermissionPolicy,
    ReasoningOutput,
    StrategyLedger,
)
from synergesis_agent_loop_v3 import SynAgentLoopV3
from synergesis_cognitive_core import SynCognitiveCore
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_life import PersistentMemory, SynKernel
from synergesis_research_layer import Aura


class Reasoner:
    def __init__(self, action_type):
        self.action_type = action_type

    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "Attempt the configured action.",
                    rationale="Test reasoner.",
                ),
            ),
            ActionProposal.create(
                self.action_type,
                {"resource": "system:/admin"},
                rationale="Test action.",
                expected_outcome="Executor runs.",
                strategy_key="test",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "evaluated",
        )


def build(tmp_path, action_type, requires_capability):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    registry = IdentityRegistry(tmp_path / "identities.jsonl")
    cap_store = CapabilityStore(tmp_path / "caps.jsonl")
    authority_signer = IdentitySigner("authority")
    worker_signer = IdentitySigner("worker")
    registry.register("authority", authority_signer.public_key)
    registry.register("worker", worker_signer.public_key)

    guard = AegisGuard(
        graph=graph,
        identity_registry=registry,
        capability_store=cap_store,
        trusted_capability_issuers=frozenset({"authority"}),
        allowed_actions=frozenset({action_type}),
        profiles=(
            ActionSecurityProfile(
                action_type,
                requires_capability=requires_capability,
                forbidden_taints=frozenset(),
            ),
        ),
    )

    core = SynCognitiveCore(tmp_path / "semantic.jsonl")
    aura = Aura(core)
    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))
    called = {"count": 0}

    def executor(params):
        called["count"] += 1
        return ActionResult(action_type, True, {"ok": True})

    loop = SynAgentLoopV3(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(frozenset({action_type})),
        reasoner=Reasoner(action_type),
        executors={action_type: executor},
        strategy_ledger=StrategyLedger(tmp_path / "strategies.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
        aegis_guard=guard,
    )
    return loop, called, CapabilityAuthority(authority_signer), cap_store


def test_aegis_missing_context_denies_before_executor(tmp_path):
    loop, called, authority, cap_store = build(
        tmp_path, "system.admin", requires_capability=True
    )
    result = loop.run_cycle(
        goal=Goal.create("Do guarded action"),
        observation=AgentObservation("event", {"x": 1}, "test"),
    )
    assert result.policy.allowed is False
    assert result.policy.reason == "aegis:missing_security_context"
    assert called["count"] == 0


def test_aegis_denial_prevents_executor(tmp_path):
    loop, called, authority, cap_store = build(
        tmp_path, "system.admin", requires_capability=True
    )
    result = loop.run_cycle(
        goal=Goal.create("Do guarded action"),
        observation=AgentObservation("event", {"x": 1}, "test"),
        security_context=SecurityContext(
            actor_id="worker",
            resource="system:/admin",
        ),
    )
    assert result.policy.allowed is False
    assert result.policy.reason == "aegis:no_valid_capability"
    assert called["count"] == 0


def test_valid_capability_reaches_executor(tmp_path):
    from datetime import datetime, timedelta, timezone

    loop, called, authority, cap_store = build(
        tmp_path, "system.admin", requires_capability=True
    )
    grant = authority.issue(
        subject_id="worker",
        action_type="system.admin",
        resource_prefixes=("system:/",),
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    cap_store.add_grant(grant)

    result = loop.run_cycle(
        goal=Goal.create("Do guarded action"),
        observation=AgentObservation("event", {"x": 1}, "test"),
        security_context=SecurityContext(
            actor_id="worker",
            resource="system:/admin",
            capability_grant_ids=(grant.grant_id,),
        ),
    )
    assert result.policy.allowed is True
    assert result.action_result.success is True
    assert called["count"] == 1


def test_aegis_can_only_narrow_existing_permission_policy(tmp_path):
    loop, called, authority, cap_store = build(
        tmp_path, "note.write", requires_capability=False
    )
    # Change ordinary policy to deny the very action AEGIS profile would allow.
    loop.policy = PermissionPolicy(frozenset({"different.action"}))
    result = loop.run_cycle(
        goal=Goal.create("Respect base policy"),
        observation=AgentObservation("event", {"x": 1}, "test"),
        security_context=SecurityContext(actor_id="worker"),
    )
    assert result.policy.allowed is False
    assert result.policy.reason == "action_type_not_allowlisted"
    assert called["count"] == 0
