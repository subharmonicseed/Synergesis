"""Cumulative risk budget for prepared causal experiments.

A sequence of individually acceptable experiments can still create excessive
aggregate exposure. SYN-RISK-BUDGET therefore constrains cumulative exposure
independently of per-action risk thresholds.

Reservation protocol
--------------------
1. Immediately before a prepared experiment is advanced through Planner/AEGIS,
   reserve the current effective risk.
2. If no executor action occurs (reasoner gate or AEGIS blocks), release the
   reservation.
3. If an executor action occurs, consume the reservation regardless of action
   success. Exposure happened even when the intended effect failed.
4. If execution becomes ambiguous due to an exception after reservation, no
   automatic release is performed. This intentionally fails closed.

The budget is append-only and hash-chained. Learning cannot increase the budget
limit, erase consumption, or convert a reservation into authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Optional, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised on unsupported platforms
    fcntl = None

from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_storage_lock import PathTransaction


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RiskBudgetPolicy:
    budget_limit: float
    maximum_single_reservation: float = 1.0
    epoch_id: str = "risk-epoch:default"

    def __post_init__(self):
        if not isinstance(self.epoch_id, str) or not self.epoch_id.strip():
            raise ValueError("epoch_id is required")
        if not math.isfinite(self.budget_limit) or self.budget_limit <= 0:
            raise ValueError("budget_limit must be finite and > 0")
        if (
            not math.isfinite(self.maximum_single_reservation)
            or self.maximum_single_reservation <= 0
        ):
            raise ValueError(
                "maximum_single_reservation must be finite and > 0"
            )


@dataclass(frozen=True)
class RiskBudgetEvent:
    sequence: int
    event_id: str
    event_type: str
    epoch_id: str
    directive_id: str
    reservation_id: str
    action_type: str
    strategy_key: str
    intervention: str
    amount: float
    cycle_id: Optional[str]
    proposal_id: Optional[str]
    occurred_at: str
    previous_digest: Optional[str]
    digest: str

    def __post_init__(self):
        if self.event_type not in {"reserved", "released", "consumed"}:
            raise ValueError("invalid risk budget event type")
        if not isinstance(self.epoch_id, str) or not self.epoch_id.strip():
            raise ValueError("risk budget epoch_id is required")
        if not math.isfinite(self.amount) or self.amount < 0:
            raise ValueError("risk budget amount must be finite and >= 0")


@dataclass(frozen=True)
class RiskBudgetState:
    epoch_id: str
    budget_limit: float
    consumed: float
    reserved: float
    available: float
    active_reservations: int

    def __post_init__(self):
        for name, value in (
            ("budget_limit", self.budget_limit),
            ("consumed", self.consumed),
            ("reserved", self.reserved),
            ("available", self.available),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class RiskBudgetReservation:
    reservation_id: str
    directive_id: str
    amount: float
    action_type: str
    strategy_key: str
    intervention: str
    event_id: str


_LOCK_TIMEOUT_SECONDS = 10.0


class RiskBudgetLedger:
    """Append-only hash chain of budget reservation lifecycle events."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if fcntl is None:
            raise RuntimeError("risk budget locking requires POSIX fcntl support")
        self._events: list[RiskBudgetEvent] = []
        self._loaded_size: Optional[int] = None

    def _size(self) -> Optional[int]:
        return self.path.stat().st_size if self.path.exists() else None

    def _load(self, *, force: bool = False) -> None:
        size = self._size()
        if not force and size == self._loaded_size:
            return

        events: list[RiskBudgetEvent] = []
        previous = None
        if self.path.exists():
            for index, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                raw = json.loads(line)
                event = RiskBudgetEvent(**raw)
                if event.sequence != index:
                    raise ValueError("risk budget ledger sequence failure")
                if event.previous_digest != previous:
                    raise ValueError("risk budget ledger chain failure")
                body = {
                    "sequence": event.sequence,
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "epoch_id": event.epoch_id,
                    "directive_id": event.directive_id,
                    "reservation_id": event.reservation_id,
                    "action_type": event.action_type,
                    "strategy_key": event.strategy_key,
                    "intervention": event.intervention,
                    "amount": event.amount,
                    "cycle_id": event.cycle_id,
                    "proposal_id": event.proposal_id,
                    "occurred_at": event.occurred_at,
                    "previous_digest": event.previous_digest,
                }
                if event.digest != _digest(body):
                    raise ValueError("risk budget ledger integrity failure")
                events.append(event)
                previous = event.digest
        self._events = events
        self._loaded_size = self._size()

    def events(self) -> Tuple[RiskBudgetEvent, ...]:
        with self.transaction():
            return tuple(self._events)

    @contextmanager
    def transaction(self):
        """Lock and reload atomically; nested calls are reentrant."""
        with PathTransaction(self.path, timeout=_LOCK_TIMEOUT_SECONDS, label="risk budget"):
            self._load(force=True)
            yield self

    def append(
        self,
        *,
        event_type: str,
        epoch_id: str,
        directive_id: str,
        reservation_id: str,
        action_type: str,
        strategy_key: str,
        intervention: str,
        amount: float,
        cycle_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
    ) -> RiskBudgetEvent:
        with self.transaction():
            return self._append_unlocked(
                event_type=event_type, epoch_id=epoch_id,
                directive_id=directive_id, reservation_id=reservation_id,
                action_type=action_type, strategy_key=strategy_key,
                intervention=intervention, amount=amount,
                cycle_id=cycle_id, proposal_id=proposal_id,
            )

    def _append_unlocked(
        self, *, event_type: str, epoch_id: str, directive_id: str,
        reservation_id: str, action_type: str, strategy_key: str,
        intervention: str, amount: float, cycle_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
    ) -> RiskBudgetEvent:
        if event_type not in {"reserved", "released", "consumed"}:
            raise ValueError("invalid risk budget event type")
        previous = self._events[-1].digest if self._events else None
        body = {
            "sequence": len(self._events) + 1,
            "event_id": "rbe:" + _digest({
                'sequence': len(self._events) + 1,
                'directive_id': directive_id,
                'reservation_id': reservation_id,
                'event_type': event_type,
                'amount': amount,
                'previous': previous,
            })[:32],
            "event_type": event_type,
            "epoch_id": epoch_id,
            "directive_id": directive_id,
            "reservation_id": reservation_id,
            "action_type": action_type,
            "strategy_key": strategy_key,
            "intervention": intervention,
            "amount": float(amount),
            "cycle_id": cycle_id,
            "proposal_id": proposal_id,
            "occurred_at": _now(),
            "previous_digest": previous,
        }
        event = RiskBudgetEvent(**body, digest=_digest(body))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(asdict(event)) + "\n")
        self._events.append(event)
        self._loaded_size = self._size()
        return event

    def verify(self) -> tuple[int, Optional[str]]:
        with self.transaction():
            return (len(self._events), self._events[-1].digest if self._events else None)


class RiskBudgetManager:
    """Serialized cumulative exposure budget; other graph writers remain single-writer."""

    actor = "SYN-RISK-BUDGET"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        ledger: RiskBudgetLedger,
        policy: RiskBudgetPolicy,
    ):
        self.graph = graph
        self.ledger = ledger
        self.policy = policy

    def _lifecycles(self) -> dict[str, list[RiskBudgetEvent]]:
        lifecycles: dict[str, list[RiskBudgetEvent]] = {}
        for event in self.ledger.events():
            if event.epoch_id != self.policy.epoch_id:
                continue
            lifecycles.setdefault(event.reservation_id, []).append(event)
        for reservation_id, events in lifecycles.items():
            if events[0].event_type != "reserved":
                raise ValueError("risk budget lifecycle missing reservation")
            if len(events) > 2:
                raise ValueError("risk budget lifecycle has too many events")
            if len(events) == 2 and events[1].event_type not in {
                "released",
                "consumed",
            }:
                raise ValueError("risk budget lifecycle has invalid terminal event")
            first = events[0]
            for event in events[1:]:
                if (
                    event.epoch_id != first.epoch_id
                    or event.directive_id != first.directive_id
                    or event.amount != first.amount
                    or event.action_type != first.action_type
                    or event.strategy_key != first.strategy_key
                    or event.intervention != first.intervention
                ):
                    raise ValueError("risk budget lifecycle identity mismatch")
        return lifecycles

    def state(self) -> RiskBudgetState:
        with self.ledger.transaction():
            lifecycles = self._lifecycles()
            consumed = 0.0
            reserved = 0.0
            active = 0
            for events in lifecycles.values():
                first = events[0]
                if len(events) == 1:
                    reserved += first.amount
                    active += 1
                elif events[1].event_type == "consumed":
                    consumed += first.amount
            available = max(0.0, self.policy.budget_limit - consumed - reserved)
            return RiskBudgetState(
                epoch_id=self.policy.epoch_id,
                budget_limit=self.policy.budget_limit,
                consumed=consumed,
                reserved=reserved,
                available=available,
                active_reservations=active,
            )

    def reserve(
        self,
        *,
        directive_id: str,
        action_type: str,
        strategy_key: str,
        intervention: str,
        amount: float,
    ) -> RiskBudgetReservation:
        with self.ledger.transaction():
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("risk reservation amount must be finite and >= 0")
            if amount > self.policy.maximum_single_reservation:
                raise ValueError("risk reservation exceeds single-exposure maximum")

            lifecycles = self._lifecycles()
            existing = [
                events for events in lifecycles.values()
                if events[0].directive_id == directive_id
            ]
            if existing:
                raise ValueError("directive already has a risk budget lifecycle")

            state = self.state()
            if amount > state.available + 1e-15:
                self.graph.create(
                    "decision",
                    actor=self.actor,
                    content={
                        "kind": "risk_budget_decision",
                        "epoch_id": self.policy.epoch_id,
                        "directive_id": directive_id,
                        "status": "budget_exhausted",
                        "requested_amount": amount,
                        "budget_limit": self.policy.budget_limit,
                        "consumed": state.consumed,
                        "reserved": state.reserved,
                        "available": state.available,
                        "authorization_effect": "none",
                    },
                )
                raise ValueError("cumulative risk budget exhausted")

            reservation_id = "rbr:" + _digest({
                'epoch_id': self.policy.epoch_id,
                'directive_id': directive_id,
                'amount': amount,
                'action_type': action_type,
                'strategy_key': strategy_key,
                'intervention': intervention,
                'sequence': len(self.ledger.events()) + 1,
            })[:32]
            event = self.ledger.append(
                event_type="reserved",
                epoch_id=self.policy.epoch_id,
                directive_id=directive_id,
                reservation_id=reservation_id,
                action_type=action_type,
                strategy_key=strategy_key,
                intervention=intervention,
                amount=amount,
            )
            self.graph.create(
                "decision",
                actor=self.actor,
                content={
                    "kind": "risk_budget_decision",
                    "epoch_id": self.policy.epoch_id,
                    "directive_id": directive_id,
                    "reservation_id": reservation_id,
                    "status": "reserved",
                    "amount": amount,
                    "budget_limit": self.policy.budget_limit,
                    "authorization_effect": "none",
                },
                external_refs=(f"risk-budget-reservation:{reservation_id}",),
                dedupe_external_ref=f"risk-budget-reservation:{reservation_id}",
            )
            return RiskBudgetReservation(
                reservation_id=reservation_id,
                directive_id=directive_id,
                amount=amount,
                action_type=action_type,
                strategy_key=strategy_key,
                intervention=intervention,
                event_id=event.event_id,
            )

    def _terminal(
        self,
        reservation: RiskBudgetReservation,
        *,
        event_type: str,
        cycle_id: Optional[str],
        proposal_id: Optional[str],
    ) -> RiskBudgetEvent:
        with self.ledger.transaction():
            lifecycles = self._lifecycles()
            events = lifecycles.get(reservation.reservation_id)
            if events is None or len(events) != 1:
                raise ValueError("risk reservation is not active")
            first = events[0]
            if (
                first.directive_id != reservation.directive_id
                or first.amount != reservation.amount
                or first.action_type != reservation.action_type
                or first.strategy_key != reservation.strategy_key
                or first.intervention != reservation.intervention
                or first.event_id != reservation.event_id
            ):
                raise ValueError("risk reservation identity mismatch")

            event = self.ledger.append(
                event_type=event_type,
                epoch_id=self.policy.epoch_id,
                directive_id=reservation.directive_id,
                reservation_id=reservation.reservation_id,
                action_type=reservation.action_type,
                strategy_key=reservation.strategy_key,
                intervention=reservation.intervention,
                amount=reservation.amount,
                cycle_id=cycle_id,
                proposal_id=proposal_id,
            )
            self.graph.create(
                "learning" if event_type == "consumed" else "decision",
                actor=self.actor,
                content={
                    "kind": "risk_budget_exposure",
                    "epoch_id": self.policy.epoch_id,
                    "directive_id": reservation.directive_id,
                    "reservation_id": reservation.reservation_id,
                    "status": event_type,
                    "amount": reservation.amount,
                    "cycle_id": cycle_id,
                    "proposal_id": proposal_id,
                    "authorization_effect": "none",
                },
                external_refs=(
                    f"risk-budget-terminal:{reservation.reservation_id}",
                ),
                dedupe_external_ref=(
                    f"risk-budget-terminal:{reservation.reservation_id}"
                ),
            )
            return event

    def release(
        self,
        reservation: RiskBudgetReservation,
        *,
        cycle_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
    ) -> RiskBudgetEvent:
        return self._terminal(
            reservation,
            event_type="released",
            cycle_id=cycle_id,
            proposal_id=proposal_id,
        )

    def consume(
        self,
        reservation: RiskBudgetReservation,
        *,
        cycle_id: str,
        proposal_id: str,
    ) -> RiskBudgetEvent:
        return self._terminal(
            reservation,
            event_type="consumed",
            cycle_id=cycle_id,
            proposal_id=proposal_id,
        )
