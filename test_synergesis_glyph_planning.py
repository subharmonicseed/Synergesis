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
    SynAgentLoop,
)
from synergesis_audit_service_v2 import SynAuditServiceV2
from synergesis_cognitive_core import Rule
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_agent_v2 import GlyphAuditedAgentProxy, SynGlyphAuditAdapterV2
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_planning import GlyphGoalAudit, GlyphPlanningAudit
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_goal_manager import GoalLedger, SynGoalManager
from synergesis_life import PersistentMemory, SynKernel
from synergesis_planner import (
    PlanDraft,
    PlanLedger,
    PlanLimits,
    PlanStepDraft,
    StepAssessment,
    SynPlannerRuntime,
)
from synergesis_research_layer import Aura


class Reasoner:
    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "The current plan step can be executed.",
                    rationale="The action is within the active step scope.",
                ),
            ),
            ActionProposal.create(
                "note.write",
                {"text": context.goal.description},
                rationale="Record the current step.",
                expected_outcome="A note is stored.",
                strategy_key="audited-plan-note",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "executor success" if result.success else "executor failure",
        )


class Planner:
    def __init__(self, replan_first=False):
        self.replan_first = replan_first
        self.assessed = 0

    def create_plan(self, context):
        return PlanDraft(
            rationale="Use bounded note steps.",
            steps=(
                PlanStepDraft("Record first", "note.write succeeds", "note.write"),
                PlanStepDraft("Record second", "note.write succeeds", "note.write"),
            ),
        )

    def assess_step(self, context, step, cycle):
        self.assessed += 1
        if self.replan_first and self.assessed == 1:
            return StepAssessment(
                "replan",
                "The first approach should be replaced.",
                1.0,
            )
        return StepAssessment(
            "completed",
            "The required executor succeeded.",
            1.0,
        )

    def replan(self, context, previous_plan, failed_step, assessment):
        return PlanDraft(
            rationale="Replacement plan after observed failure.",
            steps=(
                PlanStepDraft("Replacement", "note.write succeeds", "note.write"),
            ),
        )


def build(tmp_path, planner=None):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = Aura(core)
    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))
    agent = SynAgentLoop(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(frozenset({"note.write"})),
        reasoner=Reasoner(),
        executors={
            "note.write": lambda params: ActionResult(
                "note.write", True, {"stored": True}
            )
        },
        strategy_ledger=StrategyLedger(tmp_path / "strategies.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
    )
    adapter = SynGlyphAuditAdapterV2(agent=agent, graph=graph)
    proxy = GlyphAuditedAgentProxy(adapter)
    raw_runtime = SynPlannerRuntime(
        agent=proxy,
        provider=planner or Planner(),
        ledger=PlanLedger(tmp_path / "plans.jsonl"),
        limits=PlanLimits(
            max_steps_per_plan=4,
            max_replans=2,
            max_attempts_per_step=2,
        ),
    )
    audited_runtime = GlyphPlanningAudit(
        runtime=raw_runtime,
        graph=graph,
        actor="ZÆL-0",
    )
    raw_goals = SynGoalManager(
        runtime=audited_runtime,
        ledger=GoalLedger(tmp_path / "goals.jsonl"),
    )
    goals = GlyphGoalAudit(
        manager=raw_goals,
        graph=graph,
        actor="ZÆL-0",
    )
    return goals, audited_runtime, graph, core


def obs(n):
    return AgentObservation("event", {"n": n}, "test")


def test_goal_plan_step_agent_world_are_one_graph(tmp_path):
    goals, runtime, graph, core = build(tmp_path)
    core.remember(
        "system", "state", "ready",
        source="test", confidence=1.0, evidence_id="fact-ready",
    )

    goal = goals.create(description="Complete audited mission", source="user")
    active = goals.launch(goal_id=goal.goal.goal_id, observation=obs(0))
    assert active.status == "active"

    result = goals.advance(goal_id=goal.goal.goal_id, observation=obs(1))
    assert result.cycle is not None

    cycle_glyph = graph.ledger.find_by_external_ref(
        result.cycle.cycle_id, glyph_type="cycle"
    )[-1]
    trace = graph.upstream(cycle_glyph.glyph_id, max_depth=4)
    types = {g.glyph_type for g in trace.glyphs}
    assert "decision" in types
    assert "cycle" in types  # includes world_state
    assert "fact" in types

    plans = graph.ledger.find_by_external_ref(
        result.mission.plan.plan_id, glyph_type="plan"
    )
    assert plans
    steps = graph.ledger.find_by_external_ref(
        result.mission.plan.steps[0].step_id, glyph_type="step"
    )
    assert any(g.content["status"] == "completed" for g in steps)


def test_replan_is_explainable_from_assessment_and_previous_plan(tmp_path):
    goals, runtime, graph, core = build(tmp_path, Planner(replan_first=True))
    goal = goals.create(description="Adaptive mission", source="user")
    active = goals.launch(goal_id=goal.goal.goal_id, observation=obs(0))

    result = goals.advance(goal_id=goal.goal.goal_id, observation=obs(1))
    assert result.replanned is True
    assert result.mission.plan.revision == 2

    revised = graph.ledger.find_by_external_ref(
        result.mission.plan.plan_id,
        glyph_type="plan",
    )[-1]
    report = SynAuditServiceV2(graph).why_plan(revised.glyph_id)
    assert report.previous_plans
    assert report.assessments
    assert report.assessments[-1].content["outcome"] == "replan"


def test_goal_state_is_versioned_without_history_rewrite(tmp_path):
    goals, runtime, graph, core = build(tmp_path)
    g = goals.create(description="Pauseable goal", source="user")
    goals.launch(goal_id=g.goal.goal_id, observation=obs(0))
    goals.suspend(g.goal.goal_id, reason="pause")
    goals.resume(g.goal.goal_id, reason="continue")

    versions = graph.ledger.find_by_external_ref(g.goal.goal_id, glyph_type="goal")
    statuses = [x.content.get("status") for x in versions]
    assert statuses[:4] == ["registered", "active", "suspended", "active"]
    assert graph.ledger.verify().event_count > len(versions)


def test_world_state_is_linked_to_agent_cycle(tmp_path):
    goals, runtime, graph, core = build(tmp_path)
    g = goals.create(description="World-linked goal", source="user")
    goals.launch(goal_id=g.goal.goal_id, observation=obs(0))
    result = goals.advance(goal_id=g.goal.goal_id, observation=obs(1))
    world = graph.ledger.find_by_external_ref(
        f"cognitive-cycle:{result.cycle.cognitive_cycle}",
        glyph_type="cycle",
    )[-1]
    cycle = graph.ledger.find_by_external_ref(
        result.cycle.cycle_id,
        glyph_type="cycle",
    )[-1]
    edges = graph.ledger.edges()
    assert any(
        e.source == cycle.glyph_id
        and e.target == world.glyph_id
        and e.relation == "derived_from"
        for e in edges
    )


def test_goal_completion_is_auditable(tmp_path):
    goals, runtime, graph, core = build(tmp_path)
    g = goals.create(description="Finish me", source="user")
    goals.launch(goal_id=g.goal.goal_id, observation=obs(0))
    goals.advance(goal_id=g.goal.goal_id, observation=obs(1))
    goals.advance(goal_id=g.goal.goal_id, observation=obs(2))
    snap = goals.snapshot(g.goal.goal_id)
    assert snap.status == "completed"
    versions = graph.ledger.find_by_external_ref(g.goal.goal_id, glyph_type="goal")
    assert versions[-1].content["status"] == "completed"
