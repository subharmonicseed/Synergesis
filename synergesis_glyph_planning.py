"""Glyph audit adapters for Synergesis planning and goal management.

Plans, plan steps, assessments, replans, and goal-state transitions become
first-class nodes in the same Glyph Graph used for agent decisions.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from synergesis_agent_loop_v2 import AgentObservation, Goal
from synergesis_goal_manager import GoalSnapshot, SynGoalManager
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph
from synergesis_planner import MissionAdvance, MissionSnapshot, Plan, PlanStep, SynPlannerRuntime


class GlyphPlanningAudit:
    def __init__(self, *, runtime: SynPlannerRuntime, graph: GlyphAuditGraph, actor: str = "ZÆL-0"):
        self.runtime = runtime
        self.graph = graph
        self.actor = actor

    def _latest(self, external_ref: str, glyph_type: Optional[str] = None):
        matches = self.graph.ledger.find_by_external_ref(external_ref, glyph_type=glyph_type)
        return matches[-1] if matches else None

    def _goal_glyph(self, goal: Goal) -> Glyph:
        existing = self._latest(goal.goal_id, "goal")
        if existing is not None:
            return existing
        return self.graph.create(
            "goal",
            actor=self.actor,
            content={"description": goal.description, "status": "planning"},
            external_refs=(goal.goal_id,),
            dedupe_external_ref=goal.goal_id,
        )

    def _record_plan(
        self,
        plan: Plan,
        goal: Goal,
        *,
        previous_plan_id: Optional[str] = None,
        assessment_glyph_id: Optional[str] = None,
    ) -> Glyph:
        existing = self._latest(plan.plan_id, "plan")
        if existing is not None:
            return existing

        goal_glyph = self._goal_glyph(goal)
        parents = [goal_glyph.glyph_id]
        previous_plan = None
        if previous_plan_id is not None:
            previous_plan = self._latest(previous_plan_id, "plan")
            if previous_plan is not None:
                parents.append(previous_plan.glyph_id)
        if assessment_glyph_id is not None:
            parents.append(assessment_glyph_id)

        plan_glyph = self.graph.create(
            "plan",
            actor=self.actor,
            content={
                "mission_id": plan.mission_id,
                "revision": plan.revision,
                "rationale": plan.rationale,
                "created_at": plan.created_at,
                "step_count": len(plan.steps),
            },
            external_refs=(plan.plan_id, f"mission:{plan.mission_id}"),
            derived_from=tuple(parents),
            dedupe_external_ref=plan.plan_id,
        )
        if previous_plan is not None:
            self.graph.relate(
                plan_glyph.glyph_id,
                previous_plan.glyph_id,
                "supersedes",
                actor=self.actor,
            )

        for step in plan.steps:
            self._record_step_version(step, plan_glyph, status="planned")

        return plan_glyph

    def _record_step_version(
        self,
        step: PlanStep,
        plan_glyph: Glyph,
        *,
        status: str,
        cycle_id: Optional[str] = None,
        assessment_glyph_id: Optional[str] = None,
    ) -> Glyph:
        versions = self.graph.ledger.find_by_external_ref(step.step_id, glyph_type="step")
        prior = versions[-1] if versions else None
        state_ref = f"step-state:{step.step_id}:{status}:{len(versions)+1}"

        parents = [plan_glyph.glyph_id]
        if prior is not None:
            parents.append(prior.glyph_id)
        if assessment_glyph_id is not None:
            parents.append(assessment_glyph_id)

        cycle_glyph = None
        if cycle_id is not None:
            matches = self.graph.ledger.find_by_external_ref(cycle_id, glyph_type="cycle")
            cycle_glyph = matches[-1] if matches else None
            if cycle_glyph is not None:
                parents.append(cycle_glyph.glyph_id)

        current = self.graph.create(
            "step",
            actor=self.actor,
            content={
                "ordinal": step.ordinal,
                "description": step.description,
                "success_criteria": step.success_criteria,
                "required_action_type": step.required_action_type,
                "status": status,
                "cycle_id": cycle_id,
            },
            external_refs=(step.step_id, state_ref),
            derived_from=tuple(parents),
            dedupe_external_ref=state_ref,
        )
        self.graph.relate(
            current.glyph_id,
            plan_glyph.glyph_id,
            "part_of",
            actor=self.actor,
        )
        if prior is not None:
            self.graph.relate(
                current.glyph_id,
                prior.glyph_id,
                "supersedes",
                actor=self.actor,
            )
        return current

    def start(self, *, goal: Goal, observation: AgentObservation) -> MissionSnapshot:
        mission = self.runtime.start(goal=goal, observation=observation)
        self._record_plan(mission.plan, mission.goal)
        return mission

    def snapshot(self, mission_id: str) -> MissionSnapshot:
        return self.runtime.snapshot(mission_id)

    def advance(
        self,
        *,
        mission_id: str,
        observation: AgentObservation,
    ) -> MissionAdvance:
        before = self.runtime.snapshot(mission_id)
        step = before.next_step
        previous_plan = before.plan

        result = self.runtime.advance(
            mission_id=mission_id,
            observation=observation,
        )

        if step is None:
            return result

        assessment_glyph = None
        if result.assessment is not None:
            parents = []
            step_versions = self.graph.ledger.find_by_external_ref(
                step.step_id,
                glyph_type="step",
            )
            if step_versions:
                parents.append(step_versions[-1].glyph_id)
            if result.cycle is not None:
                cycle_matches = self.graph.ledger.find_by_external_ref(
                    result.cycle.cycle_id,
                    glyph_type="cycle",
                )
                if cycle_matches:
                    parents.append(cycle_matches[-1].glyph_id)

            assessment_ref = (
                f"assessment:{mission_id}:{previous_plan.plan_id}:"
                f"{step.step_id}:{result.mission.event_count}"
            )
            assessment_glyph = self.graph.create(
                "decision",
                actor=self.actor,
                content={
                    "kind": "step_assessment",
                    "outcome": result.assessment.outcome,
                    "rationale": result.assessment.rationale,
                    "confidence": result.assessment.confidence,
                    "mission_id": mission_id,
                    "plan_id": previous_plan.plan_id,
                    "step_id": step.step_id,
                },
                external_refs=(assessment_ref,),
                confidence=result.assessment.confidence,
                derived_from=tuple(parents),
                dedupe_external_ref=assessment_ref,
            )

        status = "active"
        if result.assessment is not None:
            status = {
                "completed": "completed",
                "blocked": "blocked",
                "retry": "retry",
                "replan": "failed",
            }[result.assessment.outcome]

        previous_plan_glyph = self._latest(previous_plan.plan_id, "plan")
        if previous_plan_glyph is None:
            previous_plan_glyph = self._record_plan(previous_plan, before.goal)

        self._record_step_version(
            step,
            previous_plan_glyph,
            status=status,
            cycle_id=result.cycle.cycle_id if result.cycle else None,
            assessment_glyph_id=(
                assessment_glyph.glyph_id if assessment_glyph else None
            ),
        )

        if result.replanned and result.mission.plan.plan_id != previous_plan.plan_id:
            self._record_plan(
                result.mission.plan,
                result.mission.goal,
                previous_plan_id=previous_plan.plan_id,
                assessment_glyph_id=(
                    assessment_glyph.glyph_id if assessment_glyph else None
                ),
            )

        return result

    def run_bounded(self, **kwargs):
        # Preserve the caller budget while auditing each advance.
        mission_id = kwargs["mission_id"]
        observations = kwargs["observations"]
        max_advances = kwargs["max_advances"]
        if max_advances < 1:
            raise ValueError("max_advances must be >= 1")
        if len(observations) < max_advances:
            raise ValueError("one observation is required per requested advance")

        outputs = []
        for index in range(max_advances):
            if self.snapshot(mission_id).status != "active":
                break
            outputs.append(
                self.advance(
                    mission_id=mission_id,
                    observation=observations[index],
                )
            )
        return tuple(outputs)


class GlyphGoalAudit:
    """SynGoalManager-compatible wrapper that versions goal state as glyphs."""

    def __init__(self, *, manager: SynGoalManager, graph: GlyphAuditGraph, actor: str = "ZÆL-0"):
        self.manager = manager
        self.graph = graph
        self.actor = actor

    def _record(self, snapshot: GoalSnapshot) -> Glyph:
        versions = self.graph.ledger.find_by_external_ref(
            snapshot.goal.goal_id,
            glyph_type="goal",
        )
        prior = versions[-1] if versions else None
        state_ref = (
            f"goal-state:{snapshot.goal.goal_id}:"
            f"{snapshot.status}:{snapshot.event_count}"
        )
        parents = [prior.glyph_id] if prior is not None else []

        mission_plan = None
        if snapshot.mission_id is not None:
            try:
                mission = self.manager.runtime.snapshot(snapshot.mission_id)
            except Exception:
                mission = None
            if mission is not None:
                plan_matches = self.graph.ledger.find_by_external_ref(
                    mission.plan.plan_id,
                    glyph_type="plan",
                )
                mission_plan = plan_matches[-1] if plan_matches else None
                if mission_plan is not None:
                    parents.append(mission_plan.glyph_id)

        glyph = self.graph.create(
            "goal",
            actor=self.actor,
            content={
                "description": snapshot.goal.description,
                "source": snapshot.source,
                "status": snapshot.status,
                "mission_id": snapshot.mission_id,
                "event_count": snapshot.event_count,
                "last_event_at": snapshot.last_event_at,
            },
            external_refs=(snapshot.goal.goal_id, state_ref),
            derived_from=tuple(parents),
            dedupe_external_ref=state_ref,
        )
        if prior is not None and prior.glyph_id != glyph.glyph_id:
            self.graph.relate(
                glyph.glyph_id,
                prior.glyph_id,
                "supersedes",
                actor=self.actor,
            )
        return glyph

    def create(self, **kwargs) -> GoalSnapshot:
        snapshot = self.manager.create(**kwargs)
        self._record(snapshot)
        return snapshot

    def snapshot(self, goal_id: str) -> GoalSnapshot:
        return self.manager.snapshot(goal_id)

    def list(self, **kwargs):
        return self.manager.list(**kwargs)

    def launch(self, **kwargs) -> GoalSnapshot:
        snapshot = self.manager.launch(**kwargs)
        self._record(snapshot)
        return snapshot

    def suspend(self, goal_id: str, **kwargs) -> GoalSnapshot:
        snapshot = self.manager.suspend(goal_id, **kwargs)
        self._record(snapshot)
        return snapshot

    def resume(self, goal_id: str, **kwargs) -> GoalSnapshot:
        snapshot = self.manager.resume(goal_id, **kwargs)
        self._record(snapshot)
        return snapshot

    def cancel(self, goal_id: str, **kwargs) -> GoalSnapshot:
        snapshot = self.manager.cancel(goal_id, **kwargs)
        self._record(snapshot)
        return snapshot

    def advance(self, **kwargs) -> MissionAdvance:
        output = self.manager.advance(**kwargs)
        goal_id = kwargs["goal_id"]
        self._record(self.manager.snapshot(goal_id))
        return output
