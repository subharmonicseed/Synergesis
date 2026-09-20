"""Strict AI planning bridge for Synergesis.

A model may propose plans, assessments and replans, but:
- output must match an exact schema;
- requested action types must already exist in the immutable permission set
  exposed through PlanningContext;
- an action-requiring step cannot be declared completed when the concrete
  agent cycle did not execute that required action successfully;
- this bridge never executes actions and never mutates permissions.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from synergesis_ai_bridge import ModelBackend
from synergesis_planner import (
    Plan,
    PlanDraft,
    PlanStep,
    PlanStepDraft,
    PlanningContext,
    StepAssessment,
)
from synergesis_agent_loop_v2 import AgentCycle


def _require_exact_keys(value: Mapping[str, Any], required: set[str], *, label: str) -> None:
    keys = set(value.keys())
    missing = sorted(required - keys)
    extra = sorted(keys - required)
    if missing:
        raise ValueError(f"{label} missing fields: {missing}")
    if extra:
        raise ValueError(f"{label} unexpected fields: {extra}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_action(value: Any, *, allowed_actions: tuple[str, ...], label: str) -> str | None:
    if value is None:
        return None
    action = _string(value, label)
    if action not in allowed_actions:
        raise ValueError(f"{label} requests unavailable action type: {action}")
    return action


def _parse_plan(raw: Mapping[str, Any], *, context: PlanningContext, label: str) -> PlanDraft:
    _require_exact_keys(raw, {"rationale", "steps"}, label=label)
    rationale = _string(raw["rationale"], f"{label}.rationale")
    raw_steps = raw["steps"]
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError(f"{label}.steps must be a non-empty list")

    steps = []
    for index, item in enumerate(raw_steps):
        if not isinstance(item, Mapping):
            raise ValueError(f"{label}.steps[{index}] must be an object")
        _require_exact_keys(
            item,
            {"description", "success_criteria", "required_action_type"},
            label=f"{label}.steps[{index}]",
        )
        steps.append(
            PlanStepDraft(
                description=_string(
                    item["description"], f"{label}.steps[{index}].description"
                ),
                success_criteria=_string(
                    item["success_criteria"],
                    f"{label}.steps[{index}].success_criteria",
                ),
                required_action_type=_optional_action(
                    item["required_action_type"],
                    allowed_actions=context.allowed_actions,
                    label=f"{label}.steps[{index}].required_action_type",
                ),
            )
        )
    return PlanDraft(rationale=rationale, steps=tuple(steps))


class SynAIPlanner:
    """PlanningProvider backed by a strictly validated model backend."""

    def __init__(self, backend: ModelBackend):
        self.backend = backend

    @staticmethod
    def _context_payload(context: PlanningContext) -> dict[str, Any]:
        return {
            "goal": asdict(context.goal),
            "observation": {
                "kind": context.observation.kind,
                "payload": dict(context.observation.payload),
                "source": context.observation.source,
            },
            "allowed_actions": list(context.allowed_actions),
            "relevant_fact_ids": list(context.relevant_fact_ids),
            "relevant_evidence_ids": list(context.relevant_evidence_ids),
            "completed_step_descriptions": list(context.completed_step_descriptions),
            "failed_step_descriptions": list(context.failed_step_descriptions),
            "contract": {
                "plans_are_proposals_not_authority": True,
                "permissions_are_immutable": True,
                "only_allowed_action_types_may_be_requested": True,
                "success_criteria_must_be_observable": True,
            },
        }

    @staticmethod
    def _cycle_payload(cycle: AgentCycle) -> dict[str, Any]:
        return {
            "cycle_id": cycle.cycle_id,
            "proposal": asdict(cycle.proposal) if cycle.proposal else None,
            "policy": asdict(cycle.policy) if cycle.policy else None,
            "action_result": asdict(cycle.action_result) if cycle.action_result else None,
            "learning": asdict(cycle.learning) if cycle.learning else None,
            "cognitive_cycle": cycle.cognitive_cycle,
            "reflexive_cycle": cycle.reflexive_cycle,
        }

    def create_plan(self, context: PlanningContext) -> PlanDraft:
        raw = self.backend.complete("plan_create", self._context_payload(context))
        if not isinstance(raw, Mapping):
            raise TypeError("plan_create output must be an object")
        return _parse_plan(raw, context=context, label="plan_create output")

    def assess_step(
        self,
        context: PlanningContext,
        step: PlanStep,
        cycle: AgentCycle,
    ) -> StepAssessment:
        payload = {
            "context": self._context_payload(context),
            "step": asdict(step),
            "cycle": self._cycle_payload(cycle),
            "contract": {
                "allowed_outcomes": ["completed", "retry", "replan", "blocked"],
                "confidence_range": [0.0, 1.0],
                "required_action_success_needed_for_completion": True,
            },
        }
        raw = self.backend.complete("plan_assess", payload)
        if not isinstance(raw, Mapping):
            raise TypeError("plan_assess output must be an object")
        _require_exact_keys(
            raw,
            {"outcome", "rationale", "confidence"},
            label="plan_assess output",
        )

        outcome = _string(raw["outcome"], "plan_assess.outcome")
        rationale = _string(raw["rationale"], "plan_assess.rationale")
        confidence = raw["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError("plan_assess.confidence must be numeric")

        assessment = StepAssessment(outcome, rationale, float(confidence))

        if assessment.outcome == "completed" and step.required_action_type is not None:
            result = cycle.action_result
            if result is None:
                raise ValueError(
                    "action-requiring step cannot be completed without an action result"
                )
            if result.action_type != step.required_action_type:
                raise ValueError(
                    "action-requiring step cannot be completed by a different action type"
                )
            if not result.success:
                raise ValueError(
                    "action-requiring step cannot be completed after failed execution"
                )

        return assessment

    def replan(
        self,
        context: PlanningContext,
        previous_plan: Plan,
        failed_step: PlanStep,
        assessment: StepAssessment,
    ) -> PlanDraft:
        payload = {
            "context": self._context_payload(context),
            "previous_plan": asdict(previous_plan),
            "failed_step": asdict(failed_step),
            "assessment": asdict(assessment),
            "contract": {
                "permissions_are_immutable": True,
                "replacement_plan_contains_remaining_work_only": True,
            },
        }
        raw = self.backend.complete("plan_replan", payload)
        if not isinstance(raw, Mapping):
            raise TypeError("plan_replan output must be an object")
        return _parse_plan(raw, context=context, label="plan_replan output")
