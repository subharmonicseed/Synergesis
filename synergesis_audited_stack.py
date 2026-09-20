"""Composition root for the fully audited Synergesis Alpha runtime.

This module intentionally exposes one constructor for the traced production path:

DeepResearch -> NOUS/THALES/World Model -> Agent Loop -> Planner -> Goal Manager
                                      -> Glyph Protocol audit graph

The LLM/reasoner and planner remain pluggable. Permissions and budgets are
explicit configuration and are never inferred from model output.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from synergesis_agent_loop_v2 import (
    ActionExecutor,
    PermissionPolicy,
    ReasoningProvider,
    StrategyLedger,
    SynAgentLoop,
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


@dataclass(frozen=True)
class SynAuditedConfig:
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

    def __post_init__(self):
        if not self.identity.strip():
            raise ValueError("identity is required")
        if not self.allowed_actions:
            raise ValueError("allowed_actions cannot be empty")
        self.root.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SynAuditedStack:
    config: SynAuditedConfig
    graph: GlyphAuditGraph
    core: GlyphAuditedCognitiveCore
    aura: GlyphAuditedAura
    kernel: SynKernel
    agent: SynAgentLoop
    agent_audit: SynGlyphAuditAdapterV2
    planner: GlyphPlanningAudit
    goals: GlyphGoalAudit
    audit: SynAuditServiceV2


def build_audited_stack(
    *,
    config: SynAuditedConfig,
    reasoner: ReasoningProvider,
    planning_provider: PlanningProvider,
    executors: Mapping[str, ActionExecutor],
) -> SynAuditedStack:
    root = config.root

    graph = GlyphAuditGraph(GlyphLedger(root / "glyph_ledger.jsonl"))
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

    agent = SynAgentLoop(
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
    )

    agent_audit = SynGlyphAuditAdapterV2(agent=agent, graph=graph)
    proxy = GlyphAuditedAgentProxy(agent_audit)

    raw_planner = SynPlannerRuntime(
        agent=proxy,
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

    audit = SynAuditServiceV2(graph)

    return SynAuditedStack(
        config=config,
        graph=graph,
        core=core,
        aura=aura,
        kernel=kernel,
        agent=agent,
        agent_audit=agent_audit,
        planner=planner,
        goals=goals,
        audit=audit,
    )
