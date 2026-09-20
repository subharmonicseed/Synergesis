"""Persistent multi-step planning for Synergesis.

Goal -> plan -> scoped step execution -> assessment -> retry/replan -> completion.

This layer is deliberately separated from permission control:
- a plan can request only capabilities that already exist in PermissionPolicy;
- every concrete action still passes through SynAgentLoop's policy gate;
- a plan step may narrow the capabilities available for that cycle, never expand them;
- execution is budgeted, so there is no unbounded autonomous loop.

The planner may be implemented by an AI model, deterministic rules, or another
provider. Planning output is treated as a proposal, not authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_agent_loop_v2 import (
    AgentCycle,
    AgentObservation,
    Goal,
    SynAgentLoop,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _hash(value: Any) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PlanLimits:
    max_steps_per_plan: int
    max_replans: int
    max_attempts_per_step: int

    def __post_init__(self):
        if self.max_steps_per_plan < 1:
            raise ValueError("max_steps_per_plan must be >= 1")
        if self.max_replans < 0:
            raise ValueError("max_replans must be >= 0")
        if self.max_attempts_per_step < 1:
            raise ValueError("max_attempts_per_step must be >= 1")


@dataclass(frozen=True)
class PlanStepDraft:
    description: str
    success_criteria: str
    required_action_type: Optional[str] = None

    def __post_init__(self):
        if not self.description.strip() or not self.success_criteria.strip():
            raise ValueError("step description and success_criteria are required")
        if self.required_action_type is not None and not self.required_action_type.strip():
            raise ValueError("required_action_type must be non-empty when supplied")


@dataclass(frozen=True)
class PlanDraft:
    rationale: str
    steps: Tuple[PlanStepDraft, ...]

    def __post_init__(self):
        if not self.rationale.strip():
            raise ValueError("plan rationale is required")
        if not self.steps:
            raise ValueError("a plan requires at least one step")


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    ordinal: int
    description: str
    success_criteria: str
    required_action_type: Optional[str]


@dataclass(frozen=True)
class Plan:
    plan_id: str
    mission_id: str
    revision: int
    rationale: str
    steps: Tuple[PlanStep, ...]
    created_at: str


@dataclass(frozen=True)
class PlanningContext:
    goal: Goal
    observation: AgentObservation
    allowed_actions: Tuple[str, ...]
    relevant_fact_ids: Tuple[str, ...]
    relevant_evidence_ids: Tuple[str, ...]
    completed_step_descriptions: Tuple[str, ...]
    failed_step_descriptions: Tuple[str, ...]


@dataclass(frozen=True)
class StepAssessment:
    """Planner evaluation of one executed step.

    outcome:
      completed - success criteria are satisfied.
      retry     - retry the same step, subject to attempt budget.
      replan    - replace the remaining plan, subject to replan budget.
      blocked   - stop because progress requires unavailable authority/input.
    """

    outcome: str
    rationale: str
    confidence: float

    def __post_init__(self):
        if self.outcome not in {"completed", "retry", "replan", "blocked"}:
            raise ValueError("invalid step assessment outcome")
        if not self.rationale.strip():
            raise ValueError("assessment rationale is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("assessment confidence must be in [0,1]")


class PlanningProvider(Protocol):
    def create_plan(self, context: PlanningContext) -> PlanDraft:
        ...

    def assess_step(
        self,
        context: PlanningContext,
        step: PlanStep,
        cycle: AgentCycle,
    ) -> StepAssessment:
        ...

    def replan(
        self,
        context: PlanningContext,
        previous_plan: Plan,
        failed_step: PlanStep,
        assessment: StepAssessment,
    ) -> PlanDraft:
        ...


@dataclass(frozen=True)
class PlanEvent:
    event_id: str
    mission_id: str
    kind: str
    created_at: str
    payload: Mapping[str, Any]
    digest: str


class PlanLedger:
    """Append-only plan/event store with integrity verification."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, mission_id: str, kind: str, payload: Mapping[str, Any]) -> PlanEvent:
        if not mission_id.strip() or not kind.strip():
            raise ValueError("mission_id and event kind are required")
        created_at = _now()
        body = {
            "mission_id": mission_id,
            "kind": kind,
            "created_at": created_at,
            "payload": dict(payload),
        }
        digest = _hash(body)
        event = PlanEvent(
            event_id=digest[:20],
            mission_id=mission_id,
            kind=kind,
            created_at=created_at,
            payload=dict(payload),
            digest=digest,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(asdict(event)) + "\n")
        return event

    def events(self, mission_id: Optional[str] = None) -> Tuple[PlanEvent, ...]:
        if not self.path.exists():
            return ()
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = PlanEvent(**json.loads(line))
            body = {
                "mission_id": event.mission_id,
                "kind": event.kind,
                "created_at": event.created_at,
                "payload": dict(event.payload),
            }
            if _hash(body) != event.digest:
                raise ValueError(f"plan ledger integrity failure for {event.event_id}")
            if mission_id is None or event.mission_id == mission_id:
                out.append(event)
        return tuple(out)


@dataclass(frozen=True)
class MissionSnapshot:
    mission_id: str
    goal: Goal
    status: str
    plan: Plan
    completed_step_ids: Tuple[str, ...]
    failed_step_ids: Tuple[str, ...]
    blocked_step_ids: Tuple[str, ...]
    replans_used: int
    next_step: Optional[PlanStep]
    event_count: int

    def __post_init__(self):
        if self.status not in {"active", "completed", "blocked", "failed"}:
            raise ValueError("invalid mission status")


@dataclass(frozen=True)
class MissionAdvance:
    mission: MissionSnapshot
    cycle: Optional[AgentCycle]
    assessment: Optional[StepAssessment]
    replanned: bool


class SynPlannerRuntime:
    """Budgeted multi-step autonomous runtime on top of SynAgentLoop."""

    def __init__(
        self,
        *,
        agent: SynAgentLoop,
        provider: PlanningProvider,
        ledger: PlanLedger,
        limits: PlanLimits,
    ):
        self.agent = agent
        self.provider = provider
        self.ledger = ledger
        self.limits = limits

    def _planning_context(
        self,
        *,
        goal: Goal,
        observation: AgentObservation,
        mission_id: Optional[str] = None,
    ) -> PlanningContext:
        query = " ".join(
            (
                goal.description,
                observation.kind,
                _canon(dict(observation.payload)),
            )
        )
        selected = self.agent.context_selector.select(
            query=query,
            facts=tuple(self.agent.core.memory.query()),
            evidence=tuple(self.agent.aura.research.store.all()),
        )

        completed: list[str] = []
        failed: list[str] = []
        if mission_id is not None:
            for event in self.ledger.events(mission_id):
                if event.kind == "step_completed":
                    completed.append(str(event.payload["description"]))
                elif event.kind in {"step_failed", "step_blocked"}:
                    failed.append(str(event.payload["description"]))

        return PlanningContext(
            goal=goal,
            observation=observation,
            allowed_actions=tuple(sorted(self.agent.policy.allowed_actions)),
            relevant_fact_ids=tuple(f.evidence_id for f in selected.facts),
            relevant_evidence_ids=tuple(e.evidence_id for e in selected.evidence),
            completed_step_descriptions=tuple(completed),
            failed_step_descriptions=tuple(failed),
        )

    def _materialize_plan(
        self,
        *,
        mission_id: str,
        revision: int,
        draft: PlanDraft,
    ) -> Plan:
        if len(draft.steps) > self.limits.max_steps_per_plan:
            raise ValueError("plan exceeds max_steps_per_plan")

        steps = []
        for ordinal, step in enumerate(draft.steps, start=1):
            body = {
                "mission_id": mission_id,
                "revision": revision,
                "ordinal": ordinal,
                "description": step.description,
                "success_criteria": step.success_criteria,
                "required_action_type": step.required_action_type,
            }
            steps.append(
                PlanStep(
                    step_id=_hash(body),
                    ordinal=ordinal,
                    description=step.description,
                    success_criteria=step.success_criteria,
                    required_action_type=step.required_action_type,
                )
            )

        created_at = _now()
        body = {
            "mission_id": mission_id,
            "revision": revision,
            "rationale": draft.rationale,
            "steps": [asdict(s) for s in steps],
            "created_at": created_at,
        }
        return Plan(
            plan_id=_hash(body),
            mission_id=mission_id,
            revision=revision,
            rationale=draft.rationale,
            steps=tuple(steps),
            created_at=created_at,
        )

    @staticmethod
    def _goal_from_event(event: PlanEvent) -> Goal:
        payload = event.payload["goal"]
        return Goal(goal_id=str(payload["goal_id"]), description=str(payload["description"]))

    @staticmethod
    def _plan_from_payload(payload: Mapping[str, Any]) -> Plan:
        steps = tuple(PlanStep(**s) for s in payload["steps"])
        return Plan(
            plan_id=str(payload["plan_id"]),
            mission_id=str(payload["mission_id"]),
            revision=int(payload["revision"]),
            rationale=str(payload["rationale"]),
            steps=steps,
            created_at=str(payload["created_at"]),
        )

    def snapshot(self, mission_id: str) -> MissionSnapshot:
        events = self.ledger.events(mission_id)
        if not events:
            raise KeyError(f"unknown mission: {mission_id}")

        started = next((e for e in events if e.kind == "mission_started"), None)
        if started is None:
            raise ValueError("mission has no mission_started event")
        goal = self._goal_from_event(started)

        plan_events = [e for e in events if e.kind in {"plan_created", "plan_revised"}]
        if not plan_events:
            raise ValueError("mission has no plan")
        plan = self._plan_from_payload(plan_events[-1].payload["plan"])

        completed = {
            str(e.payload["step_id"])
            for e in events
            if e.kind == "step_completed" and e.payload.get("plan_id") == plan.plan_id
        }
        failed = {
            str(e.payload["step_id"])
            for e in events
            if e.kind == "step_failed" and e.payload.get("plan_id") == plan.plan_id
        }
        blocked = {
            str(e.payload["step_id"])
            for e in events
            if e.kind == "step_blocked" and e.payload.get("plan_id") == plan.plan_id
        }

        status = "active"
        if any(e.kind == "mission_completed" for e in events):
            status = "completed"
        elif any(e.kind == "mission_blocked" for e in events):
            status = "blocked"
        elif any(e.kind == "mission_failed" for e in events):
            status = "failed"

        next_step = None
        if status == "active":
            for step in plan.steps:
                if step.step_id not in completed:
                    next_step = step
                    break

        return MissionSnapshot(
            mission_id=mission_id,
            goal=goal,
            status=status,
            plan=plan,
            completed_step_ids=tuple(sorted(completed)),
            failed_step_ids=tuple(sorted(failed)),
            blocked_step_ids=tuple(sorted(blocked)),
            replans_used=sum(1 for e in events if e.kind == "plan_revised"),
            next_step=next_step,
            event_count=len(events),
        )

    def _attempts_for_step(self, mission_id: str, plan_id: str, step_id: str) -> int:
        return sum(
            1
            for event in self.ledger.events(mission_id)
            if event.kind == "step_started"
            and event.payload.get("plan_id") == plan_id
            and event.payload.get("step_id") == step_id
        )

    def start(self, *, goal: Goal, observation: AgentObservation) -> MissionSnapshot:
        started_at = _now()
        mission_id = _hash(
            {
                "goal_id": goal.goal_id,
                "started_at": started_at,
                "observation": {
                    "kind": observation.kind,
                    "payload": dict(observation.payload),
                    "source": observation.source,
                },
            }
        )
        context = self._planning_context(goal=goal, observation=observation)
        draft = self.provider.create_plan(context)
        if not isinstance(draft, PlanDraft):
            raise TypeError("provider.create_plan must return PlanDraft")
        plan = self._materialize_plan(mission_id=mission_id, revision=1, draft=draft)

        self.ledger.append(
            mission_id,
            "mission_started",
            {"goal": asdict(goal), "started_at": started_at},
        )
        self.ledger.append(
            mission_id,
            "plan_created",
            {"plan": asdict(plan)},
        )
        self.agent.kernel.memory.append(
            "mission_started",
            {"mission_id": mission_id, "goal": asdict(goal), "plan_id": plan.plan_id},
            self.agent.kernel.identity,
        )
        return self.snapshot(mission_id)

    def _replan(
        self,
        *,
        mission: MissionSnapshot,
        observation: AgentObservation,
        failed_step: PlanStep,
        assessment: StepAssessment,
    ) -> bool:
        if mission.replans_used >= self.limits.max_replans:
            self.ledger.append(
                mission.mission_id,
                "mission_failed",
                {
                    "reason": "replan_budget_exhausted",
                    "failed_step_id": failed_step.step_id,
                },
            )
            return False

        context = self._planning_context(
            goal=mission.goal,
            observation=observation,
            mission_id=mission.mission_id,
        )
        draft = self.provider.replan(
            context,
            mission.plan,
            failed_step,
            assessment,
        )
        if not isinstance(draft, PlanDraft):
            raise TypeError("provider.replan must return PlanDraft")
        revised = self._materialize_plan(
            mission_id=mission.mission_id,
            revision=mission.plan.revision + 1,
            draft=draft,
        )
        self.ledger.append(
            mission.mission_id,
            "plan_revised",
            {
                "previous_plan_id": mission.plan.plan_id,
                "reason": assessment.rationale,
                "plan": asdict(revised),
            },
        )
        self.agent.kernel.memory.append(
            "plan_revised",
            {
                "mission_id": mission.mission_id,
                "previous_plan_id": mission.plan.plan_id,
                "plan_id": revised.plan_id,
                "reason": assessment.rationale,
            },
            self.agent.kernel.identity,
        )
        return True

    def advance(
        self,
        *,
        mission_id: str,
        observation: AgentObservation,
    ) -> MissionAdvance:
        mission = self.snapshot(mission_id)
        if mission.status != "active":
            raise ValueError(f"mission is not active: {mission.status}")

        step = mission.next_step
        if step is None:
            self.ledger.append(mission_id, "mission_completed", {"reason": "all_steps_completed"})
            return MissionAdvance(self.snapshot(mission_id), None, None, False)

        if (
            step.required_action_type is not None
            and step.required_action_type not in self.agent.policy.allowed_actions
        ):
            self.ledger.append(
                mission_id,
                "step_blocked",
                {
                    "plan_id": mission.plan.plan_id,
                    "step_id": step.step_id,
                    "description": step.description,
                    "reason": "required_action_not_permitted",
                    "required_action_type": step.required_action_type,
                },
            )
            assessment = StepAssessment(
                outcome="blocked",
                rationale="The plan requires an action type outside the immutable permission policy.",
                confidence=1.0,
            )
            self.ledger.append(
                mission_id,
                "mission_blocked",
                {
                    "step_id": step.step_id,
                    "reason": assessment.rationale,
                },
            )
            return MissionAdvance(self.snapshot(mission_id), None, assessment, False)

        attempts = self._attempts_for_step(mission_id, mission.plan.plan_id, step.step_id)
        if attempts >= self.limits.max_attempts_per_step:
            assessment = StepAssessment(
                outcome="replan",
                rationale="The step attempt budget is exhausted.",
                confidence=1.0,
            )
            replanned = self._replan(
                mission=mission,
                observation=observation,
                failed_step=step,
                assessment=assessment,
            )
            return MissionAdvance(self.snapshot(mission_id), None, assessment, replanned)

        self.ledger.append(
            mission_id,
            "step_started",
            {
                "plan_id": mission.plan.plan_id,
                "step_id": step.step_id,
                "description": step.description,
                "attempt": attempts + 1,
            },
        )

        step_goal = Goal.create(
            "\n".join(
                (
                    mission.goal.description,
                    f"Current plan step: {step.description}",
                    f"Success criteria: {step.success_criteria}",
                )
            )
        )
        action_scope = (
            frozenset({step.required_action_type})
            if step.required_action_type is not None
            else None
        )
        cycle = self.agent.run_cycle(
            goal=step_goal,
            observation=observation,
            action_scope=action_scope,
        )

        context = self._planning_context(
            goal=mission.goal,
            observation=observation,
            mission_id=mission_id,
        )
        assessment = self.provider.assess_step(context, step, cycle)
        if not isinstance(assessment, StepAssessment):
            raise TypeError("provider.assess_step must return StepAssessment")

        self.ledger.append(
            mission_id,
            "step_assessed",
            {
                "plan_id": mission.plan.plan_id,
                "step_id": step.step_id,
                "cycle_id": cycle.cycle_id,
                "assessment": asdict(assessment),
            },
        )

        replanned = False
        if assessment.outcome == "completed":
            self.ledger.append(
                mission_id,
                "step_completed",
                {
                    "plan_id": mission.plan.plan_id,
                    "step_id": step.step_id,
                    "description": step.description,
                    "cycle_id": cycle.cycle_id,
                },
            )
            after = self.snapshot(mission_id)
            if after.next_step is None:
                self.ledger.append(
                    mission_id,
                    "mission_completed",
                    {"reason": "all_steps_completed"},
                )

        elif assessment.outcome == "blocked":
            self.ledger.append(
                mission_id,
                "step_blocked",
                {
                    "plan_id": mission.plan.plan_id,
                    "step_id": step.step_id,
                    "description": step.description,
                    "reason": assessment.rationale,
                },
            )
            self.ledger.append(
                mission_id,
                "mission_blocked",
                {
                    "step_id": step.step_id,
                    "reason": assessment.rationale,
                },
            )

        elif assessment.outcome == "replan":
            self.ledger.append(
                mission_id,
                "step_failed",
                {
                    "plan_id": mission.plan.plan_id,
                    "step_id": step.step_id,
                    "description": step.description,
                    "reason": assessment.rationale,
                    "cycle_id": cycle.cycle_id,
                },
            )
            replanned = self._replan(
                mission=self.snapshot(mission_id),
                observation=observation,
                failed_step=step,
                assessment=assessment,
            )

        elif assessment.outcome == "retry":
            post_attempts = self._attempts_for_step(
                mission_id, mission.plan.plan_id, step.step_id
            )
            if post_attempts >= self.limits.max_attempts_per_step:
                exhausted = StepAssessment(
                    outcome="replan",
                    rationale="The planner requested retry but the step attempt budget is exhausted.",
                    confidence=1.0,
                )
                self.ledger.append(
                    mission_id,
                    "step_failed",
                    {
                        "plan_id": mission.plan.plan_id,
                        "step_id": step.step_id,
                        "description": step.description,
                        "reason": exhausted.rationale,
                        "cycle_id": cycle.cycle_id,
                    },
                )
                replanned = self._replan(
                    mission=self.snapshot(mission_id),
                    observation=observation,
                    failed_step=step,
                    assessment=exhausted,
                )

        return MissionAdvance(
            mission=self.snapshot(mission_id),
            cycle=cycle,
            assessment=assessment,
            replanned=replanned,
        )

    def run_bounded(
        self,
        *,
        mission_id: str,
        observations: Sequence[AgentObservation],
        max_advances: int,
    ) -> Tuple[MissionAdvance, ...]:
        """Run only within an explicit caller-supplied budget.

        There is intentionally no "run forever" method.
        """
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
