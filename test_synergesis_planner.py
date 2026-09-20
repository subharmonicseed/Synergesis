from pathlib import Path

import pytest

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
from synergesis_cognitive_core import SynCognitiveCore
from synergesis_context import ContextBudget, LexicalContextSelector
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


class StepReasoner:
    def __init__(self, action_type="note.write"):
        self.action_type = action_type

    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "The current plan step can be attempted.",
                    rationale="A bounded executor is available.",
                ),
            ),
            ActionProposal.create(
                self.action_type,
                {"text": context.goal.description},
                rationale="Execute the current plan step.",
                expected_outcome="The step produces an observable result.",
                strategy_key=f"plan:{self.action_type}",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "executor success" if result.success else "executor failure",
        )


class TwoStepPlanner:
    def __init__(self):
        self.assessments = []
        self.replans = 0

    def create_plan(self, context):
        return PlanDraft(
            rationale="Perform two bounded note actions.",
            steps=(
                PlanStepDraft("Record first note", "executor succeeds", "note.write"),
                PlanStepDraft("Record second note", "executor succeeds", "note.write"),
            ),
        )

    def assess_step(self, context, step, cycle):
        assessment = StepAssessment(
            "completed" if cycle.action_result and cycle.action_result.success else "retry",
            "The executor result determines completion.",
            1.0,
        )
        self.assessments.append((step.step_id, assessment.outcome))
        return assessment

    def replan(self, context, previous_plan, failed_step, assessment):
        self.replans += 1
        return PlanDraft(
            rationale="Use a replacement note step.",
            steps=(
                PlanStepDraft("Replacement note", "executor succeeds", "note.write"),
            ),
        )


class ReplanningPlanner(TwoStepPlanner):
    def __init__(self):
        super().__init__()
        self.first = True

    def create_plan(self, context):
        return PlanDraft(
            rationale="Initial approach.",
            steps=(PlanStepDraft("Try first approach", "must succeed", "note.write"),),
        )

    def assess_step(self, context, step, cycle):
        if self.first:
            self.first = False
            return StepAssessment("replan", "Observed outcome requires a new approach.", 1.0)
        return StepAssessment("completed", "Replacement approach succeeded.", 1.0)


class BlockedPlanner(TwoStepPlanner):
    def create_plan(self, context):
        return PlanDraft(
            rationale="Requests unavailable authority.",
            steps=(
                PlanStepDraft(
                    "Change system administration",
                    "administrative change succeeds",
                    "system.admin",
                ),
            ),
        )


class ScopeViolationReasoner(StepReasoner):
    def __init__(self):
        super().__init__(action_type="research.fetch")


def build_agent(tmp_path, reasoner=None, allowed=("note.write",), executors=None):
    core = SynCognitiveCore(tmp_path / "semantic.jsonl")
    aura = Aura(core)
    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))
    return SynAgentLoop(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(frozenset(allowed)),
        reasoner=reasoner or StepReasoner(),
        executors=executors or {},
        strategy_ledger=StrategyLedger(tmp_path / "strategies.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
    )


def ok_note(params):
    return ActionResult("note.write", True, {"stored": True})


def ok_research(params):
    return ActionResult("research.fetch", True, {"fetched": True})


def build_runtime(tmp_path, planner, agent=None, **limit_overrides):
    agent = agent or build_agent(
        tmp_path,
        executors={"note.write": ok_note},
    )
    values = {
        "max_steps_per_plan": 4,
        "max_replans": 2,
        "max_attempts_per_step": 2,
    }
    values.update(limit_overrides)
    return SynPlannerRuntime(
        agent=agent,
        provider=planner,
        ledger=PlanLedger(tmp_path / "plans.jsonl"),
        limits=PlanLimits(**values),
    )


def obs(value):
    return AgentObservation("event", {"value": value}, "test")


def test_two_step_mission_completes(tmp_path):
    runtime = build_runtime(tmp_path, TwoStepPlanner())
    mission = runtime.start(goal=Goal.create("Complete two notes"), observation=obs(0))
    assert mission.status == "active"
    assert mission.next_step.description == "Record first note"

    first = runtime.advance(mission_id=mission.mission_id, observation=obs(1))
    assert first.assessment.outcome == "completed"
    assert first.mission.status == "active"
    assert first.mission.next_step.description == "Record second note"

    second = runtime.advance(mission_id=mission.mission_id, observation=obs(2))
    assert second.mission.status == "completed"
    assert second.mission.next_step is None


def test_plan_persists_and_can_be_reloaded(tmp_path):
    runtime = build_runtime(tmp_path, TwoStepPlanner())
    mission = runtime.start(goal=Goal.create("Persistent plan"), observation=obs(0))
    runtime.advance(mission_id=mission.mission_id, observation=obs(1))

    same = runtime.snapshot(mission.mission_id)
    assert same.mission_id == mission.mission_id
    assert len(same.completed_step_ids) == 1
    assert same.next_step.description == "Record second note"


def test_unpermitted_planned_capability_blocks_before_agent_execution(tmp_path):
    called = {"value": False}

    def forbidden(params):
        called["value"] = True
        return ActionResult("system.admin", True, {})

    agent = build_agent(
        tmp_path,
        allowed=("note.write",),
        executors={"system.admin": forbidden},
    )
    runtime = build_runtime(tmp_path, BlockedPlanner(), agent=agent)
    mission = runtime.start(goal=Goal.create("Stay bounded"), observation=obs(0))
    result = runtime.advance(mission_id=mission.mission_id, observation=obs(1))

    assert result.mission.status == "blocked"
    assert result.cycle is None
    assert called["value"] is False


def test_step_scope_can_only_narrow_global_permissions(tmp_path):
    agent = build_agent(
        tmp_path,
        reasoner=ScopeViolationReasoner(),
        allowed=("note.write", "research.fetch"),
        executors={"note.write": ok_note, "research.fetch": ok_research},
    )
    runtime = build_runtime(tmp_path, TwoStepPlanner(), agent=agent)
    mission = runtime.start(goal=Goal.create("Use note capability only"), observation=obs(0))
    result = runtime.advance(mission_id=mission.mission_id, observation=obs(1))

    assert result.cycle.proposal.action_type == "research.fetch"
    assert result.cycle.policy.allowed is False
    assert result.cycle.policy.reason == "action_type_outside_cycle_scope"
    assert result.cycle.action_result is None


def test_replanning_creates_new_revision(tmp_path):
    planner = ReplanningPlanner()
    runtime = build_runtime(tmp_path, planner)
    mission = runtime.start(goal=Goal.create("Adapt strategy"), observation=obs(0))

    first = runtime.advance(mission_id=mission.mission_id, observation=obs(1))
    assert first.replanned is True
    assert first.mission.plan.revision == 2
    assert first.mission.next_step.description == "Replacement note"

    second = runtime.advance(mission_id=mission.mission_id, observation=obs(2))
    assert second.mission.status == "completed"


def test_replan_budget_prevents_unbounded_loop(tmp_path):
    planner = ReplanningPlanner()
    planner.first = True
    runtime = build_runtime(tmp_path, planner, max_replans=0)
    mission = runtime.start(goal=Goal.create("Budgeted replanning"), observation=obs(0))

    result = runtime.advance(mission_id=mission.mission_id, observation=obs(1))
    assert result.replanned is False
    assert result.mission.status == "failed"


def test_plan_step_limit_is_enforced(tmp_path):
    runtime = build_runtime(tmp_path, TwoStepPlanner(), max_steps_per_plan=1)
    with pytest.raises(ValueError, match="max_steps_per_plan"):
        runtime.start(goal=Goal.create("Too many steps"), observation=obs(0))


def test_run_bounded_has_no_run_forever_mode(tmp_path):
    runtime = build_runtime(tmp_path, TwoStepPlanner())
    mission = runtime.start(goal=Goal.create("Bounded run"), observation=obs(0))
    outputs = runtime.run_bounded(
        mission_id=mission.mission_id,
        observations=(obs(1), obs(2), obs(3)),
        max_advances=3,
    )
    assert len(outputs) == 2
    assert outputs[-1].mission.status == "completed"


def test_attempt_budget_forces_replan(tmp_path):
    class RetryPlanner(TwoStepPlanner):
        def create_plan(self, context):
            return PlanDraft(
                rationale="Retry initial step.",
                steps=(PlanStepDraft("Retry me", "must pass", "note.write"),),
            )

        def assess_step(self, context, step, cycle):
            return StepAssessment("retry", "Result is not yet sufficient.", 1.0)

    planner = RetryPlanner()
    runtime = build_runtime(
        tmp_path,
        planner,
        max_attempts_per_step=1,
        max_replans=1,
    )
    mission = runtime.start(goal=Goal.create("Respect attempt budget"), observation=obs(0))
    result = runtime.advance(mission_id=mission.mission_id, observation=obs(1))

    assert result.replanned is True
    assert result.mission.plan.revision == 2


def test_plan_ledger_detects_tampering(tmp_path):
    ledger = PlanLedger(tmp_path / "plans.jsonl")
    event = ledger.append("mission", "x", {"a": 1})
    raw = (tmp_path / "plans.jsonl").read_text(encoding="utf-8")
    (tmp_path / "plans.jsonl").write_text(raw.replace('"a":1', '"a":2'), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity failure"):
        ledger.events("mission")
