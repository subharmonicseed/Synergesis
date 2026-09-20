"""Synergesis secure roaming composition root v2.

This composition root unifies:
- Glyph Protocol audit graph
- audited NOUS / THALES / World Model / DeepResearch
- context-derived SYN-AEGIS
- SYN-REALITY independent runtime verification (Agent Loop v5)
- bounded Planner + Goal Manager
- adaptive SYN-ROAM search
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
)
from synergesis_agent_loop_v5 import SynAgentLoopV5
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
from synergesis_roam_adaptive import (
    AdaptiveResearchMethodLearner,
    AdaptiveSelectionConfig,
)
from synergesis_reality import (
    RealityAuditService,
    RealityProbeBinding,
    RealityProfile,
    RealityVerifier,
)
from synergesis_prediction import (
    EmpiricalPredictionProvider,
    PredictionAuditService,
    PredictionEngine,
    PredictionLedger,
)
from synergesis_prediction_curiosity import (
    PredictionCuriosityMonitor,
    PredictionCuriosityPolicy,
)
from synergesis_world_revision import WorldModelPredictionBridge
from synergesis_world_belief_view import VersionedBeliefView
from synergesis_belief_research import BeliefResearchPolicy, ProvisionalBeliefResearch
from synergesis_provisional_beliefs import FusionProvisionalBeliefs, ProvisionalBeliefPolicy
from synergesis_causal_credit import (
    CausalCreditBridge,
    CausalModel,
    install_causal_credit,
)
from synergesis_causal_experiment import (
    CausalExperimentPolicy,
    CausalExperimentSelector,
)
from synergesis_causal_planning import (
    CausalDirectiveReasoner,
    CausalExperimentCoordinator,
    CausalExperimentDirectiveRegistry,
    CausalExperimentPlanningProvider,
)
from synergesis_experiment_utility import (
    ExperimentImpactProfile,
    ExperimentUtilityGate,
    ExperimentUtilityPolicy,
)
from synergesis_risk_learning import (
    RiskLearningEngine,
    RiskLearningPolicy,
    RiskLedger,
    RiskObservationContract,
)
from synergesis_risk_budget import (
    RiskBudgetLedger,
    RiskBudgetManager,
    RiskBudgetPolicy,
)
from synergesis_provenance_receipts import (
    ProvenanceReceiptStore,
    ProvenanceReceiptVerifier,
)
from synergesis_provenance_transport import (
    ProvenanceReplayLedger,
    ProvenanceTransportImporter,
    ProvenanceTransportPolicy,
)
from synergesis_perception_bus import (
    DomainAdapter,
    PerceptionBus,
    PerceptionSourcePolicy,
)
from synergesis_perception_knowledge import (
    PerceptionKnowledgeBridge,
    PerceptionKnowledgeRule,
)
from synergesis_multisource_fusion import (
    FusionPolicy,
    FusionSourceProfile,
    MultisourcePerceptionFusion,
    PerceptionReliabilityLedger,
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
    adaptive_selection_config: AdaptiveSelectionConfig
    utility_weights: UtilityWeights
    attention_weights: AttentionWeights
    service_limits: RoamServiceLimits
    evolution_policy: EvolutionPolicy

    enable_prediction: bool = True
    prediction_prior_alpha: float = 1.0
    prediction_prior_beta: float = 1.0
    prediction_half_life_events: float = 16.0

    def __post_init__(self):
        if not self.identity.strip():
            raise ValueError("identity is required")
        if not self.allowed_actions:
            raise ValueError("allowed_actions cannot be empty")
        if self.context_max_facts < 0 or self.context_max_evidence < 0:
            raise ValueError("context budgets must be >= 0")
        for name, value in (
            ("prediction_prior_alpha", self.prediction_prior_alpha),
            ("prediction_prior_beta", self.prediction_prior_beta),
            ("prediction_half_life_events", self.prediction_half_life_events),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be > 0")
        self.root.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SynSecureRoamRealityStack:
    config: SecureRoamConfig

    graph: GlyphAuditGraph
    security_graph: AegisSecurityGraph
    aegis: AegisGuard
    provenance_transport: ProvenanceTransportImporter | None
    provenance_replay: ProvenanceReplayLedger | None
    perception: PerceptionBus | None
    perception_knowledge: PerceptionKnowledgeBridge | None
    multisource_fusion: MultisourcePerceptionFusion | None
    provisional_beliefs: FusionProvisionalBeliefs | None
    belief_research: ProvisionalBeliefResearch | None

    core: GlyphAuditedCognitiveCore
    world_beliefs: VersionedBeliefView
    aura: GlyphAuditedAura
    kernel: SynKernel
    agent: SynAgentLoopV5
    agent_audit: SynGlyphAuditAdapterV2
    reality: RealityVerifier
    reality_audit: RealityAuditService
    prediction: PredictionEngine | None
    prediction_audit: PredictionAuditService | None
    prediction_curiosity: PredictionCuriosityMonitor | None
    world_revision: WorldModelPredictionBridge | None
    causal_credit: CausalCreditBridge | None
    causal_experiment: CausalExperimentSelector | None
    risk_learning: RiskLearningEngine | None
    causal_experiment_utility: ExperimentUtilityGate | None
    risk_budget: RiskBudgetManager | None
    causal_planning: CausalExperimentCoordinator | None

    planner: GlyphPlanningAudit
    goals: GlyphGoalAudit
    audit: SynAuditServiceV2

    source_registry: SourceRegistry
    method_learner: AdaptiveResearchMethodLearner
    roam_runtime: RoamRuntime
    roam: SynRoam
    agenda: ResearchAgenda
    attention: RoamAttentionController
    service: SynRoamService
    evolution: MethodEvolutionManager


def build_secure_roam_reality_stack(
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
    reality_probe_bindings: Sequence[RealityProbeBinding],
    reality_profiles: Sequence[RealityProfile],

    source_registry: SourceRegistry,
    source_adapters: Mapping[str, SearchAdapter],
    research_methods: Sequence[ResearchMethod],
    prediction_curiosity_policy: PredictionCuriosityPolicy | None = None,
    causal_models: Sequence[CausalModel] = (),
    causal_experiment_policy: CausalExperimentPolicy | None = None,
    causal_experiment_utility_profiles: Sequence[ExperimentImpactProfile] = (),
    causal_experiment_utility_policy: ExperimentUtilityPolicy | None = None,
    risk_observation_contracts: Sequence[RiskObservationContract] = (),
    risk_learning_policy: RiskLearningPolicy | None = None,
    risk_budget_policy: RiskBudgetPolicy | None = None,
    provenance_receipt_store: ProvenanceReceiptStore | None = None,
    provenance_receipt_verifier: ProvenanceReceiptVerifier | None = None,
    provenance_transport_policy: ProvenanceTransportPolicy | None = None,
    perception_source_policies: Sequence[PerceptionSourcePolicy] = (),
    perception_adapters: Mapping[tuple[str, str], DomainAdapter] | None = None,
    perception_knowledge_rules: Sequence[PerceptionKnowledgeRule] = (),
    fusion_source_profiles: Sequence[FusionSourceProfile] = (),
    fusion_policy: FusionPolicy | None = None,
    provisional_belief_policy: ProvisionalBeliefPolicy | None = None,
    belief_research_policy: BeliefResearchPolicy | None = None,
) -> SynSecureRoamRealityStack:
    root = config.root
    perception_adapter_map = dict(perception_adapters or {})

    if bool(causal_experiment_utility_profiles) != (
        causal_experiment_utility_policy is not None
    ):
        raise ValueError(
            "causal experiment utility requires both trusted impact profiles "
            "and an explicit utility policy"
        )
    if bool(risk_observation_contracts) != (risk_learning_policy is not None):
        raise ValueError(
            "risk learning requires both observation contracts "
            "and an explicit learning policy"
        )
    if risk_budget_policy is not None and causal_experiment_utility_policy is None:
        raise ValueError(
            "risk budget requires experiment utility configuration"
        )
    transport_parts = (
        provenance_receipt_store,
        provenance_receipt_verifier,
        provenance_transport_policy,
    )
    if any(part is not None for part in transport_parts) and not all(
        part is not None for part in transport_parts
    ):
        raise ValueError(
            "provenance transport requires receipt store, verifier and policy"
        )
    if (
        provenance_receipt_verifier is not None
        and provenance_receipt_verifier.identity_registry is not identity_registry
    ):
        raise ValueError(
            "provenance transport verifier must share stack identity registry"
        )
    if bool(perception_source_policies) != bool(perception_adapter_map):
        raise ValueError(
            "perception bus requires both source policies and adapters"
        )
    if perception_knowledge_rules and not perception_source_policies:
        raise ValueError(
            "perception knowledge rules require the perception bus"
        )
    if belief_research_policy is not None and provisional_belief_policy is None:
        raise ValueError("belief research requires provisional beliefs")
    if provisional_belief_policy is not None:
        if fusion_policy is None or provisional_belief_policy.observation_kind != fusion_policy.observation_kind:
            raise ValueError("provisional beliefs require a matching fusion policy")
    if bool(fusion_source_profiles) != (fusion_policy is not None):
        raise ValueError(
            "multisource fusion requires both source profiles and a fusion policy"
        )
    if fusion_source_profiles and not perception_source_policies:
        raise ValueError(
            "multisource fusion requires the perception bus"
        )
    perception_source_ids = {
        policy.source_id for policy in perception_source_policies
    }
    missing_fusion_sources = {
        profile.source_id
        for profile in fusion_source_profiles
        if profile.source_id not in perception_source_ids
    }
    if missing_fusion_sources:
        raise ValueError(
            "fusion source profiles missing perception source policies: "
            + ",".join(sorted(missing_fusion_sources))
        )
    if perception_source_policies:
        required_perception_adapters = {
            (policy.source_id, modality)
            for policy in perception_source_policies
            if policy.enabled
            for modality in policy.allowed_modalities
        }
        missing_perception_adapters = (
            required_perception_adapters - set(perception_adapter_map)
        )
        if missing_perception_adapters:
            raise ValueError(
                "enabled perception modalities missing adapters: "
                + ",".join(
                    f"{source}/{modality}"
                    for source, modality in sorted(missing_perception_adapters)
                )
            )

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

    provenance_replay = None
    provenance_transport = None
    if provenance_transport_policy is not None:
        assert provenance_receipt_store is not None
        assert provenance_receipt_verifier is not None
        provenance_replay = ProvenanceReplayLedger(
            root / "provenance_transport_replay.jsonl"
        )
        provenance_transport = ProvenanceTransportImporter(
            graph=graph,
            security_graph=security_graph,
            receipt_store=provenance_receipt_store,
            receipt_verifier=provenance_receipt_verifier,
            replay_ledger=provenance_replay,
            policy=provenance_transport_policy,
        )

    perception = None
    if perception_source_policies:
        perception = PerceptionBus(
            graph=graph,
            security_graph=security_graph,
            source_policies=tuple(perception_source_policies),
            adapters=perception_adapter_map,
        )

    aegis = AegisGuard(
        graph=graph,
        identity_registry=identity_registry,
        capability_store=capability_store,
        trusted_capability_issuers=trusted_capability_issuers,
        allowed_actions=config.allowed_actions,
        profiles=tuple(action_security_profiles),
        security_graph=security_graph,
    )

    reality = RealityVerifier(
        graph=graph,
        security_graph=security_graph,
        probe_bindings=tuple(reality_probe_bindings),
        profiles=tuple(reality_profiles),
    )
    reality.require_profiles_for(config.allowed_actions)

    # The World Model must exist before PREDICT is assembled: the prediction
    # provider records exactly which semantic belief was used, then receives
    # the verified settlement to append the corresponding revision.
    core = GlyphAuditedCognitiveCore(
        root / "semantic_memory.jsonl",
        graph=graph,
        actor=config.identity,
    )
    versioned_predicates = tuple(dict.fromkeys(
        (
            WorldModelPredictionBridge.predicate,
            CausalCreditBridge.predicate,
            *(
                rule.predicate
                for rule in perception_knowledge_rules
                if rule.versioned
            ),
        )
    ))
    world_beliefs = VersionedBeliefView(
        core.memory,
        versioned_predicates=versioned_predicates,
    )
    context_selector = LexicalContextSelector(
        budget=ContextBudget(
            max_facts=config.context_max_facts,
            max_evidence=config.context_max_evidence,
        ),
        k1=config.bm25_k1,
        b=config.bm25_b,
    )

    prediction = None
    prediction_audit = None
    world_revision = None
    causal_credit = None
    causal_experiment = None
    risk_learning = None
    causal_experiment_utility = None
    risk_budget = None
    causal_registry = None
    causal_planning = None
    if config.enable_prediction:
        prediction_ledger = PredictionLedger(root / "prediction_ledger.jsonl")
        empirical_estimator = EmpiricalPredictionProvider(
            ledger=prediction_ledger,
            prior_alpha=config.prediction_prior_alpha,
            prior_beta=config.prediction_prior_beta,
            half_life_events=config.prediction_half_life_events,
        )
        world_revision = WorldModelPredictionBridge(
            core=core,
            estimator=empirical_estimator,
        )
        prediction = PredictionEngine(
            graph=graph,
            provider=world_revision,
            ledger=prediction_ledger,
        )
        prediction.add_settlement_sink(world_revision)
        if causal_models:
            causal_credit = install_causal_credit(
                engine=prediction,
                core=core,
                models=tuple(causal_models),
            )
            causal_experiment = CausalExperimentSelector(
                graph=graph,
                causal_credit=causal_credit,
                policy=(
                    causal_experiment_policy
                    if causal_experiment_policy is not None
                    else CausalExperimentPolicy()
                ),
            )
            if risk_learning_policy is not None:
                risk_learning = RiskLearningEngine(
                    graph=graph,
                    ledger=RiskLedger(root / "risk_ledger.jsonl"),
                    contracts=tuple(risk_observation_contracts),
                    policy=risk_learning_policy,
                )
                prediction.add_settlement_sink(risk_learning)
            if causal_experiment_utility_policy is not None:
                causal_experiment_utility = ExperimentUtilityGate(
                    graph=graph,
                    profiles=tuple(causal_experiment_utility_profiles),
                    policy=causal_experiment_utility_policy,
                    learned_risk_provider=risk_learning,
                )
                if risk_budget_policy is not None:
                    risk_budget = RiskBudgetManager(
                        graph=graph,
                        ledger=RiskBudgetLedger(root / "risk_budget_ledger.jsonl"),
                        policy=risk_budget_policy,
                    )
        elif (
            causal_experiment_policy is not None
            or causal_experiment_utility_policy is not None
            or causal_experiment_utility_profiles
            or risk_learning_policy is not None
            or risk_observation_contracts
            or risk_budget_policy is not None
        ):
            raise ValueError(
                "causal experiment policy/utility/risk learning "
                "requires at least one causal model"
            )
        prediction_audit = PredictionAuditService(
            graph=graph,
            ledger=prediction_ledger,
        )
    elif (
        causal_models
        or causal_experiment_policy is not None
        or causal_experiment_utility_policy is not None
        or causal_experiment_utility_profiles
        or risk_learning_policy is not None
        or risk_observation_contracts
        or risk_budget_policy is not None
    ):
        raise ValueError(
            "causal models/experiment selection/risk learning "
            "require prediction to be enabled"
        )

    effective_reasoner = reasoner
    effective_planning_provider = planning_provider
    if causal_experiment is not None:
        assert causal_credit is not None
        assert prediction is not None
        causal_registry = CausalExperimentDirectiveRegistry(
            graph=graph,
            causal_credit=causal_credit,
        )
        effective_reasoner = CausalDirectiveReasoner(
            base=reasoner,
            registry=causal_registry,
        )
        effective_planning_provider = CausalExperimentPlanningProvider(
            base=planning_provider,
            registry=causal_registry,
            prediction=prediction,
        )

    aura = GlyphAuditedAura(core, graph=graph)
    kernel = SynKernel(
        config.identity,
        PersistentMemory(root / "episodic_memory.jsonl"),
    )

    agent = SynAgentLoopV5(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(config.allowed_actions),
        reasoner=effective_reasoner,
        executors=executors,
        strategy_ledger=StrategyLedger(root / "strategy_ledger.jsonl"),
        context_selector=context_selector,
        graph=graph,
        aegis_guard=aegis,
        observation_classifier=observation_classifier,
        capability_resolver=capability_resolver,
        resource_resolver=resource_resolver,
        reality_verifier=reality,
        prediction_engine=prediction,
    )

    agent_audit = SynGlyphAuditAdapterV2(agent=agent, graph=graph)
    agent_proxy = GlyphAuditedAgentProxy(agent_audit)

    raw_planner = SynPlannerRuntime(
        agent=agent_proxy,
        provider=effective_planning_provider,
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
    if causal_experiment is not None:
        assert causal_registry is not None
        causal_planning = CausalExperimentCoordinator(
            selector=causal_experiment,
            registry=causal_registry,
            planner=planner,
            utility_gate=causal_experiment_utility,
            risk_budget=risk_budget,
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
    learner = AdaptiveResearchMethodLearner(
        ledger=method_ledger,
        config=config.selection_config,
        adaptive_config=config.adaptive_selection_config,
        graph=graph,
        actor="SYN-ROAM",
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
    prediction_curiosity = None
    if prediction is not None and prediction_curiosity_policy is not None:
        prediction_curiosity = PredictionCuriosityMonitor(
            graph=graph,
            prediction_ledger=prediction.ledger,
            agenda=agenda,
            policy=prediction_curiosity_policy,
        )
        prediction.add_settlement_sink(prediction_curiosity)

    perception_knowledge = None
    if perception_knowledge_rules:
        assert perception is not None
        perception_knowledge = PerceptionKnowledgeBridge(
            graph=graph,
            core=core,
            aura=aura,
            world_beliefs=world_beliefs,
            agenda=agenda,
            context_selector=context_selector,
            rules=tuple(perception_knowledge_rules),
        )

    multisource_fusion = None
    provisional_beliefs = None
    if fusion_policy is not None:
        assert perception is not None
        multisource_fusion = MultisourcePerceptionFusion(
            graph=graph,
            security_graph=security_graph,
            profiles=tuple(fusion_source_profiles),
            policy=fusion_policy,
            reliability_ledger=PerceptionReliabilityLedger(
                root / "perception_reliability.jsonl"
            ),
            agenda=agenda,
            aura=aura,
        )

    if provisional_belief_policy is not None:
        provisional_beliefs = FusionProvisionalBeliefs(graph=graph, policy=provisional_belief_policy)
        multisource_fusion.add_decision_sink(provisional_beliefs)
        core.world.provisional_beliefs = provisional_beliefs

    attention = RoamAttentionController(
        agenda=agenda,
        roam=roam,
    )
    belief_research = None
    if belief_research_policy is not None:
        belief_research = ProvisionalBeliefResearch(
            beliefs=provisional_beliefs, agenda=agenda, policy=belief_research_policy)
        attention.add_tick_hook(belief_research.scan_once)
        attention.add_need_guard(belief_research.still_needed)
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
    reality_audit = RealityAuditService(graph)

    return SynSecureRoamRealityStack(
        config=config,
        graph=graph,
        security_graph=security_graph,
        aegis=aegis,
        provenance_transport=provenance_transport,
        provenance_replay=provenance_replay,
        perception=perception,
        perception_knowledge=perception_knowledge,
        multisource_fusion=multisource_fusion,
        provisional_beliefs=provisional_beliefs,
        belief_research=belief_research,
        core=core,
        world_beliefs=world_beliefs,
        aura=aura,
        kernel=kernel,
        agent=agent,
        agent_audit=agent_audit,
        reality=reality,
        reality_audit=reality_audit,
        prediction=prediction,
        prediction_audit=prediction_audit,
        prediction_curiosity=prediction_curiosity,
        world_revision=world_revision,
        causal_credit=causal_credit,
        causal_experiment=causal_experiment,
        risk_learning=risk_learning,
        causal_experiment_utility=causal_experiment_utility,
        risk_budget=risk_budget,
        causal_planning=causal_planning,
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
