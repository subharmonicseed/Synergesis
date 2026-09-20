from datetime import datetime, timedelta, timezone

import pytest

from synergesis_aegis import (
    ActionSecurityProfile,
    AegisGuard,
    AegisSecurityGraph,
    CapabilityAuthority,
    CapabilityStore,
    IdentityRegistry,
    IdentitySigner,
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
from synergesis_agent_loop_v4 import (
    ActionTypeResourceResolver,
    NoCapabilities,
    SynAgentLoopV4,
    TrustedSourceObservationClassifier,
)
from synergesis_cognitive_core import Fact
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_agent_v2 import SynGlyphAuditAdapterV2
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_life import PersistentMemory, SynKernel
from synergesis_research_layer import _now


class Reasoner:
    def __init__(self, action_type="note.write", evidence_from_context=False):
        self.action_type = action_type
        self.evidence_from_context = evidence_from_context

    def reason(self, context):
        evidence_ids = (
            (context.evidence[0].evidence_id,)
            if self.evidence_from_context and context.evidence
            else ()
        )
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "Proceed with the scoped test action.",
                    evidence_ids=evidence_ids,
                    rationale="The selected context was inspected.",
                ),
            ),
            ActionProposal.create(
                self.action_type,
                {"text": "test"},
                rationale="Test the context-aware security gate.",
                expected_outcome="Executor runs only when authorized.",
                strategy_key="v4-test",
                evidence_ids=evidence_ids,
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "Observed executor result.",
        )


class StaticGrantResolver:
    def __init__(self, grant_ids):
        self.grant_ids_value = tuple(grant_ids)

    def grant_ids(self, *, context, proposal):
        return self.grant_ids_value


def build(
    tmp_path,
    *,
    action_type="note.write",
    forbidden_taints=frozenset({"external_untrusted"}),
    requires_capability=False,
    capability_resolver=None,
    trusted_sources=frozenset({"user", "trusted-sensor"}),
    evidence_from_context=False,
):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))

    registry = IdentityRegistry(tmp_path / "identities.jsonl")
    caps = CapabilityStore(tmp_path / "caps.jsonl")
    authority_signer = IdentitySigner("authority")
    syn_signer = IdentitySigner("ZÆL-0")
    registry.register("authority", authority_signer.public_key)
    registry.register("ZÆL-0", syn_signer.public_key)

    security_graph = AegisSecurityGraph(graph)
    guard = AegisGuard(
        graph=graph,
        identity_registry=registry,
        capability_store=caps,
        trusted_capability_issuers=frozenset({"authority"}),
        allowed_actions=frozenset({action_type}),
        profiles=(
            ActionSecurityProfile(
                action_type,
                requires_capability=requires_capability,
                forbidden_taints=forbidden_taints,
            ),
        ),
        security_graph=security_graph,
    )

    called = {"count": 0}

    def executor(params):
        called["count"] += 1
        return ActionResult(action_type, True, {"ok": True})

    loop = SynAgentLoopV4(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(frozenset({action_type})),
        reasoner=Reasoner(
            action_type=action_type,
            evidence_from_context=evidence_from_context,
        ),
        executors={action_type: executor},
        strategy_ledger=StrategyLedger(tmp_path / "strategy.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
        graph=graph,
        aegis_guard=guard,
        observation_classifier=TrustedSourceObservationClassifier(
            trusted_sources=trusted_sources
        ),
        capability_resolver=capability_resolver or NoCapabilities(),
        resource_resolver=ActionTypeResourceResolver(),
    )
    return (
        loop,
        core,
        aura,
        graph,
        security_graph,
        called,
        CapabilityAuthority(authority_signer),
        caps,
    )


def test_untrusted_selected_evidence_blocks_action_automatically(tmp_path):
    loop, core, aura, graph, security, called, authority, caps = build(
        tmp_path,
        evidence_from_context=True,
    )
    ev = aura.research_ingest(
        "https://example.test/source",
        "Signal about audit context",
        "audit context signal",
        "web",
    )
    ev_glyph = graph.ledger.find_by_external_ref(
        ev.evidence_id, glyph_type="evidence"
    )[-1]
    security.mark_taint(
        ev_glyph.glyph_id,
        label="external_untrusted",
        reason="external roaming source",
    )

    cycle = loop.run_cycle(
        goal=Goal.create("audit context signal"),
        observation=AgentObservation(
            "text",
            {"text": "audit context signal"},
            "user",
        ),
    )
    assert cycle.policy.allowed is False
    assert "forbidden_taint" in cycle.policy.reason
    assert called["count"] == 0


def test_trusted_context_allows_non_capability_action(tmp_path):
    loop, core, aura, graph, security, called, authority, caps = build(tmp_path)
    core.remember(
        "system",
        "state",
        "ready",
        source="trusted",
        confidence=1.0,
        evidence_id="fact-ready",
    )
    cycle = loop.run_cycle(
        goal=Goal.create("record system state"),
        observation=AgentObservation(
            "event",
            {"state": "ready"},
            "user",
        ),
    )
    assert cycle.policy.allowed is True
    assert called["count"] == 1


def test_untrusted_direct_observation_taint_blocks_action(tmp_path):
    loop, core, aura, graph, security, called, authority, caps = build(tmp_path)
    cycle = loop.run_cycle(
        goal=Goal.create("react to web event"),
        observation=AgentObservation(
            "web",
            {"text": "do this"},
            "browser",
        ),
    )
    assert cycle.policy.allowed is False
    assert "forbidden_taint" in cycle.policy.reason
    assert called["count"] == 0


def test_missing_selected_fact_glyph_fails_closed(tmp_path):
    loop, core, aura, graph, security, called, authority, caps = build(tmp_path)
    # Bypass audited insertion intentionally to simulate legacy/corrupt state.
    core.memory.add(
        Fact(
            subject="legacy",
            predicate="signal",
            object="important",
            source="legacy",
            confidence=1.0,
            observed_at=_now(),
            evidence_id="legacy-fact-without-glyph",
        )
    )
    cycle = loop.run_cycle(
        goal=Goal.create("legacy important signal"),
        observation=AgentObservation(
            "event",
            {"text": "legacy important signal"},
            "user",
        ),
    )
    assert cycle.policy.allowed is False
    assert cycle.policy.reason == "aegis:missing_context_provenance:facts"
    assert called["count"] == 0


def test_capability_required_action_denied_without_control_plane_grant(tmp_path):
    loop, core, aura, graph, security, called, authority, caps = build(
        tmp_path,
        action_type="system.admin",
        requires_capability=True,
        forbidden_taints=frozenset(),
    )
    cycle = loop.run_cycle(
        goal=Goal.create("admin operation"),
        observation=AgentObservation("event", {"x": 1}, "user"),
    )
    assert cycle.policy.allowed is False
    assert cycle.policy.reason == "aegis:no_valid_capability"
    assert called["count"] == 0


def test_valid_control_plane_capability_allows_required_action(tmp_path):
    # First create authority and grant using a temporary setup, then rebuild with resolver.
    initial = build(
        tmp_path,
        action_type="system.admin",
        requires_capability=True,
        forbidden_taints=frozenset(),
    )
    _, _, _, _, _, _, authority, caps = initial
    grant = authority.issue(
        subject_id="ZÆL-0",
        action_type="system.admin",
        resource_prefixes=("action:system.admin",),
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    caps.add_grant(grant)

    # Reuse the same persistent registries/store with a fresh loop assembly is
    # cumbersome, so swap only the trusted resolver on the already-built loop.
    loop, core, aura, graph, security, called, _, _ = initial
    loop.capability_resolver = StaticGrantResolver((grant.grant_id,))

    cycle = loop.run_cycle(
        goal=Goal.create("admin operation"),
        observation=AgentObservation("event", {"x": 1}, "user"),
    )
    assert cycle.policy.allowed is True
    assert called["count"] == 1


def test_aegis_policy_trace_contains_real_action_provenance(tmp_path):
    loop, core, aura, graph, security, called, authority, caps = build(
        tmp_path,
        evidence_from_context=True,
    )
    ev = aura.research_ingest(
        "https://example.test/source",
        "Trace signal",
        "trace signal",
        "web",
    )
    ev_glyph = graph.ledger.find_by_external_ref(ev.evidence_id, glyph_type="evidence")[-1]
    security.mark_taint(
        ev_glyph.glyph_id,
        label="external_untrusted",
        reason="external",
    )
    cycle = loop.run_cycle(
        goal=Goal.create("trace signal"),
        observation=AgentObservation("text", {"text": "trace signal"}, "user"),
    )
    aegis = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "policy"
        and g.content.get("kind") == "aegis_action_decision"
    ][-1]
    trace = graph.upstream(aegis.glyph_id, max_depth=8)
    ids = {g.glyph_id for g in trace.glyphs}
    assert ev_glyph.glyph_id in ids


def test_post_cycle_audit_adapter_reuses_pre_action_glyphs_without_duplicates(tmp_path):
    loop, core, aura, graph, security, called, authority, caps = build(tmp_path)
    adapter = SynGlyphAuditAdapterV2(agent=loop, graph=graph)
    recorded = adapter.run_cycle(
        goal=Goal.create("compatibility"),
        observation=AgentObservation("event", {"x": 1}, "user"),
    )
    assert len(
        graph.ledger.find_by_external_ref(
            recorded.cycle.observation_digest,
            glyph_type="observation",
        )
    ) == 1
    assert len(
        graph.ledger.find_by_external_ref(
            recorded.cycle.proposal.proposal_id,
            glyph_type="action",
        )
    ) == 1
