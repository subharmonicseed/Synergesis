"""Unified secure + audited + roaming Synergesis composition root.

This is the first composition root that unifies:
- Glyph Protocol audit graph
- audited NOUS / THALES / World Model / DeepResearch
- context-derived SYN-AEGIS (Agent Loop v4)
- bounded Planner + Goal Manager
- SYN-ROAM adaptive search
- research attention agenda
- empirical research-method evolution
- finite service runner

Live source adapters are injected through the SearchAdapter protocol. This keeps
credentials/network policies outside model control.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, Tuple

from synergesis_aegis import (
    ActionSecurityProfile,
    AegisGuard,
    AegisSecurityGraph,
    CapabilityStore,
    IdentityRegistry,
)
from synergesis_agent_loop_v2 import (
    ActionExecutor,
    PermissionPolicy,
    ReasoningProvider,
    StrategyLedger,
)
from synergesis_agent_loop_v4 import (
    CapabilityResolver,
    ObservationSecurityClassifier,
    ResourceResolver,
    SynAgentLoopV4,
)
from synergesis_audit_service_v2 import SynAuditServiceV2
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_agent_v2 import (
    GlyphAuditedAgentProxy,
    SynGlyphAuditAdapterV2,
)
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_planning import GlyphGoalAudit, GlyphPlanningAudit
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_goal_manager import GoalLedger, SynGoalManager
from synergesis_life import PersistentMemory, SynKernel
from synergesis_planner import (
    PlanLedger,
    PlanLimits,
    PlanningProvider,
    SynPlannerRuntime,
)
from synergesis_roam import (
    MethodLedger,
    ResearchMethod,
    ResearchMethodLearner,
    RoamLimits,
    RoamRuntime,
    SearchAdapter,
    SelectionConfig,
    SourceRegistry,
    SynRoam,
    UtilityWeights,
)
from synergesis_roam_attention import (
    AttentionWeights,
    ResearchAgenda,
    RoamAttentionController,
)
from synergesis_roam_evolution import (
    EvolutionPolicy,
    MethodEvolutionLedger,
    MethodEvolutionManager,
)
from synergesis_roam_service import (
    RoamServiceLedger,
    RoamServiceLimits,
    SynRoamService,
)


@dataclass(frozen=True)
class SecureRoamConfig:
    root: Path
    identity: str
    allowed_actions: frozenset[str]

    context_max_facts: int
    context_max_evidence: int
    bm25_k1: float
    bm25_b: float

    max_steps_per_plan: int
    max_replans: int
    max_attempts_per_step: int

    roam_limits: RoamLimits
    selection_config: SelectionConfig
    utility_weights: UtilityWeights
    attention_weights: AttentionWeights
    service_limits: RoamServiceLimits
    evolution_policy: EvolutionPolicy

    def __post_init__(self):
        if not self.identity.strip():
            raise ValueError("identity is required")
        if not self.allowed_actions:
            raise ValueError("allowed_actions cannot be empty")
        if self.context_max_facts < 0 or self.context_max_evidence < 0:
            raise ValueError("context budgets must be >= 0")
        self.root.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SynSecureRoamStack:
    config: SecureRoamConfig

    graph: GlyphAuditGraph
    security_graph: AegisSecurityGraph
    aegis: AegisGuard

    core: GlyphAuditedCognitiveCore
    aura: GlyphAuditedAura
    kernel: SynKernel
    agent: SynAgentLoopV4
    agent_audit: SynGlyphAuditAdapterV2

    planner: GlyphPlanningAudit
    goals: GlyphGoalAudit
    audit: SynAuditServiceV2

    source_registry: SourceRegistry
    method_learner: ResearchMethodLearner
    roam_runtime: RoamRuntime
    roam: SynRoam
    agenda: ResearchAgenda
    attention: RoamAttentionController
    service: SynRoamService
    evolution: MethodEvolutionManager


def build_secure_roam_stack(
    *,
    config: SecureRoamConfig,
    reasoner: ReasoningProvider,
    planning_provider: PlanningProvider,
    executors: Mapping[str, ActionExecutor],

    identity_registry: IdentityRegistry,
    capability_store: CapabilityStore,
    trusted_capability_issuers: frozenset[str],
    action_security_profiles: Sequence[ActionSecurityProfile],
    observation_classifier: ObservationSecurityClassifier,
    capability_resolver: CapabilityResolver,
    resource_resolver: ResourceResolver,

    source_registry: SourceRegistry,
    source_adapters: Mapping[str, SearchAdapter],
    research_methods: Sequence[ResearchMethod],
) -> SynSecureRoamStack:
    root = config.root

    profile_actions = {p.action_type for p in action_security_profiles}
    missing_profiles = config.allowed_actions - profile_actions
    if missing_profiles:
        raise ValueError(
            "every globally allowed action requires an AEGIS profile: "
            + ",".join(sorted(missing_profiles))
        )

    missing_adapters = {
        p.source_id
        for p in source_registry.policies()
        if p.enabled and p.source_id not in source_adapters
    }
    if missing_adapters:
        raise ValueError(
            "enabled sources missing adapters: "
            + ",".join(sorted(missing_adapters))
        )

    graph = GlyphAuditGraph(GlyphLedger(root / "glyph_ledger.jsonl"))
    security_graph = AegisSecurityGraph(graph)

    aegis = AegisGuard(
        graph=graph,
        identity_registry=identity_registry,
        capability_store=capability_store,
        trusted_capability_issuers=trusted_capability_issuers,
        allowed_actions=config.allowed_actions,
        profiles=tuple(action_security_profiles),
        security_graph=security_graph,
    )

    core = GlyphAuditedCognitiveCore(
        root / "semantic_memory.jsonl",
        graph=graph,
        actor=config.identity,
    )
    aura = GlyphAuditedAura(core, graph=graph)
    kernel = SynKernel(
        config.identity,
        PersistentMemory(root / "episodic_memory.jsonl"),
    )

    agent = SynAgentLoopV4(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(config.allowed_actions),
        reasoner=reasoner,
        executors=executors,
        strategy_ledger=StrategyLedger(root / "strategy_ledger.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(
                max_facts=config.context_max_facts,
                max_evidence=config.context_max_evidence,
            ),
            k1=config.bm25_k1,
            b=config.bm25_b,
        ),
        graph=graph,
        aegis_guard=aegis,
        observation_classifier=observation_classifier,
        capability_resolver=capability_resolver,
        resource_resolver=resource_resolver,
    )

    agent_audit = SynGlyphAuditAdapterV2(agent=agent, graph=graph)
    agent_proxy = GlyphAuditedAgentProxy(agent_audit)

    raw_planner = SynPlannerRuntime(
        agent=agent_proxy,
        provider=planning_provider,
        ledger=PlanLedger(root / "plan_ledger.jsonl"),
        limits=PlanLimits(
            max_steps_per_plan=config.max_steps_per_plan,
            max_replans=config.max_replans,
            max_attempts_per_step=config.max_attempts_per_step,
        ),
    )
    planner = GlyphPlanningAudit(
        runtime=raw_planner,
        graph=graph,
        actor=config.identity,
    )

    raw_goals = SynGoalManager(
        runtime=planner,
        ledger=GoalLedger(root / "goal_ledger.jsonl"),
    )
    goals = GlyphGoalAudit(
        manager=raw_goals,
        graph=graph,
        actor=config.identity,
    )

    method_ledger = MethodLedger(root / "roam_method_outcomes.jsonl")
    learner = ResearchMethodLearner(
        ledger=method_ledger,
        config=config.selection_config,
    )
    for method in research_methods:
        learner.register(method)

    roam_runtime = RoamRuntime(
        graph=graph,
        aura=aura,
        security_graph=security_graph,
        source_registry=source_registry,
        adapters=source_adapters,
        limits=config.roam_limits,
        actor="SYN-ROAM",
    )
    roam = SynRoam(
        learner=learner,
        runtime=roam_runtime,
        utility_weights=config.utility_weights,
    )

    agenda = ResearchAgenda(
        root / "roam_agenda.jsonl",
        graph=graph,
        weights=config.attention_weights,
        actor="SYN-ROAM",
    )
    attention = RoamAttentionController(
        agenda=agenda,
        roam=roam,
    )
    service = SynRoamService(
        controller=attention,
        ledger=RoamServiceLedger(root / "roam_service.jsonl"),
        limits=config.service_limits,
    )

    evolution = MethodEvolutionManager(
        graph=graph,
        source_registry=source_registry,
        learner=learner,
        outcome_ledger=method_ledger,
        evolution_ledger=MethodEvolutionLedger(
            root / "roam_method_evolution.jsonl"
        ),
        policy=config.evolution_policy,
    )

    audit = SynAuditServiceV2(graph)

    return SynSecureRoamStack(
        config=config,
        graph=graph,
        security_graph=security_graph,
        aegis=aegis,
        core=core,
        aura=aura,
        kernel=kernel,
        agent=agent,
        agent_audit=agent_audit,
        planner=planner,
        goals=goals,
        audit=audit,
        source_registry=source_registry,
        method_learner=learner,
        roam_runtime=roam_runtime,
        roam=roam,
        agenda=agenda,
        attention=attention,
        service=service,
        evolution=evolution,
    )
