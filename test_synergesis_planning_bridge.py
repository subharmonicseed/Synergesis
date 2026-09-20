import pytest

from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentContext,
    AgentCycle,
    AgentObservation,
    Goal,
    Hypothesis,
    LearningSignal,
    PolicyDecision,
    ReasoningOutput,
)
from synergesis_planner import (
    Plan,
    PlanStep,
    PlanningContext,
    StepAssessment,
)
from synergesis_planning_bridge import SynAIPlanner
from synergesis_research_layer import DriftReport


class Backend:
    def __init__(self, outputs):
        self.outputs = dict(outputs)
        self.calls = []

    def complete(self, operation, payload):
        self.calls.append((operation, payload))
        return self.outputs[operation]


def context():
    return PlanningContext(
        goal=Goal.create("Produce a verified note"),
        observation=AgentObservation("event", {"value": 1}, "sensor"),
        allowed_actions=("note.write", "research.fetch"),
        relevant_fact_ids=("fact-1",),
        relevant_evidence_ids=("ev-1",),
        completed_step_descriptions=(),
        failed_step_descriptions=(),
    )


def valid_plan(action="note.write"):
    return {
        "rationale": "Collect evidence then record the result.",
        "steps": [
            {
                "description": "Record a verified note",
                "success_criteria": "note.write returns success",
                "required_action_type": action,
            }
        ],
    }


def step():
    return PlanStep(
        step_id="step-1",
        ordinal=1,
        description="Record a verified note",
        success_criteria="note.write returns success",
        required_action_type="note.write",
    )


def cycle(success=True, with_result=True):
    proposal = ActionProposal.create(
        "note.write",
        {"text": "x"},
        rationale="record",
        expected_outcome="stored",
        strategy_key="note",
    )
    result = (
        ActionResult("note.write", success, {"stored": success}, None if success else "failed")
        if with_result
        else None
    )
    return AgentCycle(
        cycle_id="cycle-1",
        goal_id="goal-1",
        observation_digest="obs-1",
        hypotheses=(),
        proposal=proposal,
        policy=PolicyDecision(True, "action_type_allowlisted"),
        action_result=result,
        learning=LearningSignal(1.0 if success else 0.0, "evaluated") if with_result else None,
        strategy_stats=None,
        drift=DriftReport(0, 0, 0.0, ()),
        cognitive_cycle=1,
        reflexive_cycle=1,
        memory_count=1,
    )


def previous_plan():
    return Plan(
        plan_id="plan-1",
        mission_id="mission-1",
        revision=1,
        rationale="old",
        steps=(step(),),
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_valid_plan_is_parsed():
    planner = SynAIPlanner(Backend({"plan_create": valid_plan()}))
    draft = planner.create_plan(context())
    assert len(draft.steps) == 1
    assert draft.steps[0].required_action_type == "note.write"


def test_plan_cannot_request_unavailable_capability():
    planner = SynAIPlanner(Backend({"plan_create": valid_plan("system.admin")}))
    with pytest.raises(ValueError, match="unavailable action type"):
        planner.create_plan(context())


def test_extra_plan_fields_are_rejected():
    raw = valid_plan()
    raw["grant_permissions"] = ["system.admin"]
    planner = SynAIPlanner(Backend({"plan_create": raw}))
    with pytest.raises(ValueError, match="unexpected fields"):
        planner.create_plan(context())


def test_successful_required_action_may_complete_step():
    planner = SynAIPlanner(
        Backend(
            {
                "plan_assess": {
                    "outcome": "completed",
                    "rationale": "The required executor succeeded.",
                    "confidence": 1.0,
                }
            }
        )
    )
    result = planner.assess_step(context(), step(), cycle(success=True))
    assert result.outcome == "completed"


def test_failed_required_action_cannot_be_declared_complete():
    planner = SynAIPlanner(
        Backend(
            {
                "plan_assess": {
                    "outcome": "completed",
                    "rationale": "Pretend it worked.",
                    "confidence": 1.0,
                }
            }
        )
    )
    with pytest.raises(ValueError, match="failed execution"):
        planner.assess_step(context(), step(), cycle(success=False))


def test_missing_required_action_result_cannot_be_declared_complete():
    planner = SynAIPlanner(
        Backend(
            {
                "plan_assess": {
                    "outcome": "completed",
                    "rationale": "Pretend it worked.",
                    "confidence": 1.0,
                }
            }
        )
    )
    with pytest.raises(ValueError, match="without an action result"):
        planner.assess_step(context(), step(), cycle(with_result=False))


def test_replan_uses_same_permission_boundary():
    planner = SynAIPlanner(
        Backend(
            {
                "plan_replan": {
                    "rationale": "Use another allowed approach.",
                    "steps": [
                        {
                            "description": "Fetch supporting evidence",
                            "success_criteria": "research.fetch succeeds",
                            "required_action_type": "research.fetch",
                        }
                    ],
                }
            }
        )
    )
    draft = planner.replan(
        context(),
        previous_plan(),
        step(),
        StepAssessment("replan", "old approach failed", 1.0),
    )
    assert draft.steps[0].required_action_type == "research.fetch"


def test_assessment_confidence_is_bounded():
    planner = SynAIPlanner(
        Backend(
            {
                "plan_assess": {
                    "outcome": "retry",
                    "rationale": "Need another attempt.",
                    "confidence": 1.5,
                }
            }
        )
    )
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        planner.assess_step(context(), step(), cycle(success=False))


def test_bridge_exposes_permissions_but_no_mutation_surface():
    backend = Backend({"plan_create": valid_plan()})
    planner = SynAIPlanner(backend)
    planner.create_plan(context())
    payload = backend.calls[0][1]
    assert payload["allowed_actions"] == ["note.write", "research.fetch"]
    assert payload["contract"]["permissions_are_immutable"] is True
    assert "set_permissions" not in payload
