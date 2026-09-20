from pathlib import Path

from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentObservation,
    Hypothesis,
    LearningSignal,
    ReasoningOutput,
)
from synergesis_audited_stack import SynAuditedConfig, build_audited_stack
from synergesis_planner import PlanDraft, PlanStepDraft, StepAssessment


class Reasoner:
    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "The active mission step should be executed.",
                    rationale="It is explicit in the current scoped goal.",
                ),
            ),
            ActionProposal.create(
                "note.write",
                {"text": "audited"},
                rationale="Record mission progress.",
                expected_outcome="The note executor succeeds.",
                strategy_key="audited-note",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "Observed executor result.",
        )


class Planner:
    def create_plan(self, context):
        return PlanDraft(
            rationale="One observable step.",
            steps=(
                PlanStepDraft(
                    "Write audited note",
                    "note.write succeeds",
                    "note.write",
                ),
            ),
        )

    def assess_step(self, context, step, cycle):
        return StepAssessment(
            "completed",
            "The executor returned success.",
            1.0,
        )

    def replan(self, context, previous_plan, failed_step, assessment):
        return PlanDraft(
            rationale="Replacement.",
            steps=(
                PlanStepDraft(
                    "Replacement note",
                    "note.write succeeds",
                    "note.write",
                ),
            ),
        )


def config(tmp_path):
    return SynAuditedConfig(
        root=tmp_path / "syn",
        identity="ZÆL-0",
        allowed_actions=frozenset({"note.write"}),
        context_max_facts=8,
        context_max_evidence=8,
        bm25_k1=1.5,
        bm25_b=0.75,
        max_steps_per_plan=4,
        max_replans=2,
        max_attempts_per_step=2,
    )


def test_single_builder_creates_fully_audited_stack(tmp_path):
    stack = build_audited_stack(
        config=config(tmp_path),
        reasoner=Reasoner(),
        planning_provider=Planner(),
        executors={
            "note.write": lambda params: ActionResult(
                "note.write", True, {"stored": True}
            )
        },
    )

    ev = stack.aura.research_ingest(
        "https://example.test/source",
        "Source",
        "Evidence body",
        "web",
    )
    claim = stack.aura.research.propose_claim(
        "System is ready",
        [ev.evidence_id],
    )
    stack.aura.research.approve(claim.claim_id, "human")
    fact = stack.aura.research.commit_approved_claim(
        claim.claim_id,
        stack.core.memory,
        "system",
        "state",
        "ready",
        0.95,
    )

    goal = stack.goals.create(
        description="Complete one audited mission",
        source="user",
    )
    stack.goals.launch(
        goal_id=goal.goal.goal_id,
        observation=AgentObservation("event", {"n": 0}, "test"),
    )
    result = stack.goals.advance(
        goal_id=goal.goal.goal_id,
        observation=AgentObservation("event", {"n": 1}, "test"),
    )

    assert result.mission.status == "completed"
    assert stack.goals.snapshot(goal.goal.goal_id).status == "completed"

    belief = stack.audit.why_fact(evidence_id=fact.evidence_id)
    assert belief.evidence

    checkpoint = stack.graph.ledger.verify()
    assert checkpoint.event_count > 0
    assert checkpoint.chain_head
    assert checkpoint.merkle_root


def test_stack_reopens_persistent_audit_graph(tmp_path):
    cfg = config(tmp_path)
    first = build_audited_stack(
        config=cfg,
        reasoner=Reasoner(),
        planning_provider=Planner(),
        executors={
            "note.write": lambda params: ActionResult(
                "note.write", True, {"stored": True}
            )
        },
    )
    first.core.remember(
        "x", "y", "z",
        source="test",
        confidence=1.0,
        evidence_id="fact-1",
    )
    first.core.cycle_once()
    before = first.graph.ledger.verify()

    second = build_audited_stack(
        config=cfg,
        reasoner=Reasoner(),
        planning_provider=Planner(),
        executors={
            "note.write": lambda params: ActionResult(
                "note.write", True, {"stored": True}
            )
        },
    )
    after = second.graph.ledger.verify()

    assert after.event_count >= before.event_count
    assert second.core.memory.count() == 1
    assert second.graph.ledger.find_by_external_ref("fact-1", glyph_type="fact")


def test_config_requires_explicit_permissions(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="allowed_actions"):
        SynAuditedConfig(
            root=tmp_path / "bad",
            identity="ZÆL-0",
            allowed_actions=frozenset(),
            context_max_facts=8,
            context_max_evidence=8,
            bm25_k1=1.5,
            bm25_b=0.75,
            max_steps_per_plan=4,
            max_replans=2,
            max_attempts_per_step=2,
        )
