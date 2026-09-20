import pytest

from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentObservation,
    Hypothesis,
    LearningSignal,
    PermissionPolicy,
    ReasoningOutput,
    StrategyLedger,
    SynAgentLoop,
)
from synergesis_cognitive_core import SynCognitiveCore
from synergesis_context import ContextBudget, LexicalContextSelector
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
                    "The current goal step can be executed.",
                    rationale="The configured action is bounded.",
                ),
            ),
            ActionProposal.create(
                "note.write",
                {"text": context.goal.description},
                rationale="Record progress.",
                expected_outcome="Note recorded.",
                strategy_key="goal-note",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(1.0 if result.success else 0.0, "evaluated")


class Planner:
    def create_plan(self, context):
        return PlanDraft(
            rationale="Two explicit steps.",
            steps=(
                PlanStepDraft("Step one", "note succeeds", "note.write"),
                PlanStepDraft("Step two", "note succeeds", "note.write"),
            ),
        )

    def assess_step(self, context, step, cycle):
        return StepAssessment(
            "completed" if cycle.action_result and cycle.action_result.success else "retry",
            "Concrete executor result is authoritative.",
            1.0,
        )

    def replan(self, context, previous_plan, failed_step, assessment):
        return PlanDraft(
            rationale="Replacement step.",
            steps=(PlanStepDraft("Replacement", "note succeeds", "note.write"),),
        )


def build(tmp_path):
    core = SynCognitiveCore(tmp_path / "semantic.jsonl")
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
        strategy_ledger=StrategyLedger(tmp_path / "strategy.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
    )
    runtime = SynPlannerRuntime(
        agent=agent,
        provider=Planner(),
        ledger=PlanLedger(tmp_path / "plans.jsonl"),
        limits=PlanLimits(
            max_steps_per_plan=4,
            max_replans=2,
            max_attempts_per_step=2,
        ),
    )
    manager = SynGoalManager(
        runtime=runtime,
        ledger=GoalLedger(tmp_path / "goals.jsonl"),
    )
    return manager, runtime


def obs(n):
    return AgentObservation("event", {"n": n}, "test")


def test_goal_lifecycle_to_completion(tmp_path):
    manager, _ = build(tmp_path)
    registered = manager.create(description="Finish durable mission", source="user")
    assert registered.status == "registered"

    active = manager.launch(goal_id=registered.goal.goal_id, observation=obs(0))
    assert active.status == "active"
    assert active.mission_id is not None

    manager.advance(goal_id=registered.goal.goal_id, observation=obs(1))
    still = manager.snapshot(registered.goal.goal_id)
    assert still.status == "active"

    manager.advance(goal_id=registered.goal.goal_id, observation=obs(2))
    done = manager.snapshot(registered.goal.goal_id)
    assert done.status == "completed"


def test_suspend_blocks_progress_and_resume_restores_it(tmp_path):
    manager, _ = build(tmp_path)
    g = manager.create(description="Suspendable mission", source="user")
    manager.launch(goal_id=g.goal.goal_id, observation=obs(0))
    suspended = manager.suspend(g.goal.goal_id, reason="user pause")
    assert suspended.status == "suspended"

    with pytest.raises(ValueError, match="cannot advance"):
        manager.advance(goal_id=g.goal.goal_id, observation=obs(1))

    resumed = manager.resume(g.goal.goal_id, reason="user continue")
    assert resumed.status == "active"


def test_state_reconstructs_from_persistent_ledgers(tmp_path):
    manager, runtime = build(tmp_path)
    g = manager.create(description="Persistent objective", source="user")
    manager.launch(goal_id=g.goal.goal_id, observation=obs(0))
    manager.advance(goal_id=g.goal.goal_id, observation=obs(1))

    fresh = SynGoalManager(
        runtime=runtime,
        ledger=GoalLedger(tmp_path / "goals.jsonl"),
    )
    restored = fresh.snapshot(g.goal.goal_id)
    assert restored.status == "active"
    assert restored.mission_id is not None
    mission = runtime.snapshot(restored.mission_id)
    assert len(mission.completed_step_ids) == 1


def test_cancel_is_final_for_goal_manager(tmp_path):
    manager, _ = build(tmp_path)
    g = manager.create(description="Cancellable objective", source="user")
    manager.launch(goal_id=g.goal.goal_id, observation=obs(0))
    cancelled = manager.cancel(g.goal.goal_id, reason="no longer wanted")
    assert cancelled.status == "cancelled"

    with pytest.raises(ValueError, match="cannot advance"):
        manager.advance(goal_id=g.goal.goal_id, observation=obs(1))


def test_multiple_goals_remain_independent(tmp_path):
    manager, _ = build(tmp_path)
    a = manager.create(description="Objective A", source="user")
    b = manager.create(description="Objective B", source="user")
    manager.launch(goal_id=a.goal.goal_id, observation=obs(0))
    manager.launch(goal_id=b.goal.goal_id, observation=obs(0))
    manager.suspend(a.goal.goal_id, reason="pause A")

    assert manager.snapshot(a.goal.goal_id).status == "suspended"
    assert manager.snapshot(b.goal.goal_id).status == "active"


def test_list_can_exclude_final_goals(tmp_path):
    manager, _ = build(tmp_path)
    a = manager.create(description="Active objective", source="user")
    b = manager.create(description="Cancelled objective", source="user")
    manager.launch(goal_id=a.goal.goal_id, observation=obs(0))
    manager.cancel(b.goal.goal_id, reason="discard")

    non_final = manager.list(include_final=False)
    assert [x.goal.description for x in non_final] == ["Active objective"]


def test_goal_ledger_detects_tampering(tmp_path):
    ledger = GoalLedger(tmp_path / "goals.jsonl")
    ledger.append("goal", "event", {"x": 1})
    path = tmp_path / "goals.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"x":1', '"x":9'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.events("goal")


def test_duplicate_goal_registration_is_idempotent(tmp_path):
    manager, _ = build(tmp_path)
    first = manager.create(description="Same objective", source="user")
    second = manager.create(description="Same objective", source="user")
    assert first.goal.goal_id == second.goal.goal_id
    assert second.event_count == 1
