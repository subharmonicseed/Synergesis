"""Persistent goal and mission control for Synergesis.

This layer gives Syn durable objectives without introducing hidden scheduling or
self-created authority. Goals can be created, launched, suspended, resumed and
cancelled. Execution still occurs only through SynPlannerRuntime -> SynAgentLoop
-> PermissionPolicy.

The registry is append-only and reconstructs state from events, so an active
mission can be resumed by a fresh process using the same ledgers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from synergesis_agent_loop_v2 import AgentObservation, Goal
from synergesis_planner import MissionAdvance, SynPlannerRuntime


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
class GoalEvent:
    event_id: str
    goal_id: str
    kind: str
    created_at: str
    payload: Mapping[str, Any]
    digest: str


class GoalLedger:
    """Append-only goal ledger with integrity checking."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, goal_id: str, kind: str, payload: Mapping[str, Any]) -> GoalEvent:
        if not goal_id.strip() or not kind.strip():
            raise ValueError("goal_id and event kind are required")
        created_at = _now()
        body = {
            "goal_id": goal_id,
            "kind": kind,
            "created_at": created_at,
            "payload": dict(payload),
        }
        digest = _hash(body)
        event = GoalEvent(
            event_id=digest[:20],
            goal_id=goal_id,
            kind=kind,
            created_at=created_at,
            payload=dict(payload),
            digest=digest,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(asdict(event)) + "\n")
        return event

    def events(self, goal_id: Optional[str] = None) -> Tuple[GoalEvent, ...]:
        if not self.path.exists():
            return ()
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = GoalEvent(**json.loads(line))
            body = {
                "goal_id": event.goal_id,
                "kind": event.kind,
                "created_at": event.created_at,
                "payload": dict(event.payload),
            }
            if _hash(body) != event.digest:
                raise ValueError(f"goal ledger integrity failure for {event.event_id}")
            if goal_id is None or event.goal_id == goal_id:
                out.append(event)
        return tuple(out)


@dataclass(frozen=True)
class GoalSnapshot:
    goal: Goal
    source: str
    status: str
    mission_id: Optional[str]
    created_at: str
    last_event_at: str
    event_count: int

    def __post_init__(self):
        if self.status not in {
            "registered",
            "active",
            "suspended",
            "completed",
            "blocked",
            "failed",
            "cancelled",
        }:
            raise ValueError("invalid goal status")


class SynGoalManager:
    """Durable objective registry around the bounded planning runtime."""

    FINAL = frozenset({"completed", "blocked", "failed", "cancelled"})

    def __init__(self, *, runtime: SynPlannerRuntime, ledger: GoalLedger):
        self.runtime = runtime
        self.ledger = ledger

    def create(self, *, description: str, source: str) -> GoalSnapshot:
        if not source.strip():
            raise ValueError("goal source is required")
        goal = Goal.create(description)
        existing = self.ledger.events(goal.goal_id)
        if existing:
            snapshot = self.snapshot(goal.goal_id)
            if snapshot.goal.description != description:
                raise ValueError("goal id collision")
            return snapshot

        created_at = _now()
        self.ledger.append(
            goal.goal_id,
            "goal_registered",
            {
                "goal": asdict(goal),
                "source": source,
                "created_at": created_at,
            },
        )
        return self.snapshot(goal.goal_id)

    def snapshot(self, goal_id: str) -> GoalSnapshot:
        events = self.ledger.events(goal_id)
        if not events:
            raise KeyError(f"unknown goal: {goal_id}")
        registered = next((e for e in events if e.kind == "goal_registered"), None)
        if registered is None:
            raise ValueError("goal has no registration event")

        g = registered.payload["goal"]
        goal = Goal(goal_id=str(g["goal_id"]), description=str(g["description"]))
        source = str(registered.payload["source"])
        created_at = str(registered.payload["created_at"])

        status = "registered"
        mission_id: Optional[str] = None
        for event in events:
            if event.kind == "mission_linked":
                mission_id = str(event.payload["mission_id"])
                status = "active"
            elif event.kind == "goal_suspended":
                status = "suspended"
            elif event.kind == "goal_resumed":
                status = "active"
            elif event.kind == "goal_completed":
                status = "completed"
            elif event.kind == "goal_blocked":
                status = "blocked"
            elif event.kind == "goal_failed":
                status = "failed"
            elif event.kind == "goal_cancelled":
                status = "cancelled"

        return GoalSnapshot(
            goal=goal,
            source=source,
            status=status,
            mission_id=mission_id,
            created_at=created_at,
            last_event_at=events[-1].created_at,
            event_count=len(events),
        )

    def list(self, *, include_final: bool = True) -> Tuple[GoalSnapshot, ...]:
        goal_ids = []
        seen = set()
        for event in self.ledger.events():
            if event.goal_id not in seen:
                seen.add(event.goal_id)
                goal_ids.append(event.goal_id)
        snapshots = tuple(self.snapshot(goal_id) for goal_id in goal_ids)
        if include_final:
            return snapshots
        return tuple(s for s in snapshots if s.status not in self.FINAL)

    def launch(
        self,
        *,
        goal_id: str,
        observation: AgentObservation,
    ) -> GoalSnapshot:
        current = self.snapshot(goal_id)
        if current.status != "registered":
            raise ValueError(f"goal cannot be launched from status {current.status}")
        mission = self.runtime.start(goal=current.goal, observation=observation)
        self.ledger.append(
            goal_id,
            "mission_linked",
            {
                "mission_id": mission.mission_id,
                "plan_id": mission.plan.plan_id,
            },
        )
        return self.snapshot(goal_id)

    def suspend(self, goal_id: str, *, reason: str) -> GoalSnapshot:
        current = self.snapshot(goal_id)
        if current.status != "active":
            raise ValueError(f"only active goals can be suspended, got {current.status}")
        if not reason.strip():
            raise ValueError("suspension reason is required")
        self.ledger.append(goal_id, "goal_suspended", {"reason": reason})
        return self.snapshot(goal_id)

    def resume(self, goal_id: str, *, reason: str) -> GoalSnapshot:
        current = self.snapshot(goal_id)
        if current.status != "suspended":
            raise ValueError(f"only suspended goals can be resumed, got {current.status}")
        if current.mission_id is None:
            raise ValueError("suspended goal has no linked mission")
        if self.runtime.snapshot(current.mission_id).status != "active":
            raise ValueError("linked mission is no longer active")
        if not reason.strip():
            raise ValueError("resume reason is required")
        self.ledger.append(goal_id, "goal_resumed", {"reason": reason})
        return self.snapshot(goal_id)

    def cancel(self, goal_id: str, *, reason: str) -> GoalSnapshot:
        current = self.snapshot(goal_id)
        if current.status in self.FINAL:
            raise ValueError(f"goal is already final: {current.status}")
        if not reason.strip():
            raise ValueError("cancellation reason is required")
        self.ledger.append(goal_id, "goal_cancelled", {"reason": reason})
        return self.snapshot(goal_id)

    def advance(
        self,
        *,
        goal_id: str,
        observation: AgentObservation,
    ) -> MissionAdvance:
        current = self.snapshot(goal_id)
        if current.status != "active":
            raise ValueError(f"goal cannot advance from status {current.status}")
        if current.mission_id is None:
            raise ValueError("active goal has no mission")

        output = self.runtime.advance(
            mission_id=current.mission_id,
            observation=observation,
        )
        mission_status = output.mission.status

        if mission_status == "completed":
            self.ledger.append(
                goal_id,
                "goal_completed",
                {"mission_id": current.mission_id},
            )
        elif mission_status == "blocked":
            self.ledger.append(
                goal_id,
                "goal_blocked",
                {"mission_id": current.mission_id},
            )
        elif mission_status == "failed":
            self.ledger.append(
                goal_id,
                "goal_failed",
                {"mission_id": current.mission_id},
            )

        return output
