"""Synergesis bounded autonomous agent loop.

This module connects the existing episodic kernel, semantic/cognitive core, and
research/orchestration layer into one auditable cycle:

observe -> contextualize -> hypothesize -> propose -> policy gate -> execute
-> observe result -> evaluate -> learn strategy -> reflect.

Learning can change strategy statistics. It cannot change permissions.
No external action is possible unless both:
1) its action type is explicitly allowed by PermissionPolicy, and
2) an executor has been explicitly registered for that action type.

The module makes no consciousness or sentience claim.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_cognitive_core import Fact, SynCognitiveCore
from synergesis_life import SynKernel
from synergesis_research_layer import Aura, DriftReport
from synergesis_context import LexicalContextSelector


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )


def _hash(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Goal:
    goal_id: str
    description: str

    @classmethod
    def create(cls, description: str) -> "Goal":
        if not description.strip():
            raise ValueError("goal description is required")
        return cls(_hash({"goal": description}), description)


@dataclass(frozen=True)
class AgentObservation:
    kind: str
    payload: Mapping[str, Any]
    source: str

    def __post_init__(self):
        if not self.kind.strip() or not self.source.strip():
            raise ValueError("observation kind and source are required")


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    evidence_ids: Tuple[str, ...]
    rationale: str

    @classmethod
    def create(
        cls,
        statement: str,
        *,
        evidence_ids: Sequence[str] = (),
        rationale: str,
    ) -> "Hypothesis":
        if not statement.strip() or not rationale.strip():
            raise ValueError("hypothesis statement and rationale are required")
        body = {
            "statement": statement,
            "evidence_ids": tuple(evidence_ids),
            "rationale": rationale,
        }
        return cls(_hash(body), statement, tuple(evidence_ids), rationale)


@dataclass(frozen=True)
class ActionProposal:
    proposal_id: str
    action_type: str
    parameters: Mapping[str, Any]
    rationale: str
    expected_outcome: str
    strategy_key: str
    evidence_ids: Tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        action_type: str,
        parameters: Mapping[str, Any],
        *,
        rationale: str,
        expected_outcome: str,
        strategy_key: str,
        evidence_ids: Sequence[str] = (),
    ) -> "ActionProposal":
        if not action_type.strip():
            raise ValueError("action_type is required")
        if not rationale.strip() or not expected_outcome.strip() or not strategy_key.strip():
            raise ValueError("rationale, expected_outcome and strategy_key are required")
        body = {
            "action_type": action_type,
            "parameters": dict(parameters),
            "rationale": rationale,
            "expected_outcome": expected_outcome,
            "strategy_key": strategy_key,
            "evidence_ids": tuple(evidence_ids),
        }
        return cls(
            _hash(body),
            action_type,
            dict(parameters),
            rationale,
            expected_outcome,
            strategy_key,
            tuple(evidence_ids),
        )


@dataclass(frozen=True)
class ReasoningOutput:
    hypotheses: Tuple[Hypothesis, ...]
    action: Optional[ActionProposal]


@dataclass(frozen=True)
class AgentContext:
    goal: Goal
    observation: AgentObservation
    facts: Tuple[Fact, ...]
    gaps: Tuple[str, ...]
    evidence: Tuple[Any, ...]

    @property
    def known_evidence_ids(self) -> Tuple[str, ...]:
        return tuple(e.evidence_id for e in self.evidence)


@dataclass(frozen=True)
class ActionResult:
    action_type: str
    success: bool
    output: Mapping[str, Any]
    error: Optional[str] = None

    def __post_init__(self):
        if not self.action_type.strip():
            raise ValueError("action_type is required")
        if self.success and self.error is not None:
            raise ValueError("successful actions cannot carry an error")


@dataclass(frozen=True)
class LearningSignal:
    score: float
    lesson: str

    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("learning score must be in [0,1]")
        if not self.lesson.strip():
            raise ValueError("learning lesson is required")


class ReasoningProvider(Protocol):
    """Pluggable AI/reasoning boundary.

    A model may implement this protocol, but the agent loop itself does not
    invent model output when no provider is supplied.
    """

    def reason(self, context: AgentContext) -> ReasoningOutput:
        ...

    def evaluate(
        self,
        context: AgentContext,
        proposal: ActionProposal,
        result: ActionResult,
    ) -> LearningSignal:
        ...


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class PermissionPolicy:
    """Immutable allowlist for action capabilities."""

    allowed_actions: frozenset[str]

    def __post_init__(self):
        if any(not x.strip() for x in self.allowed_actions):
            raise ValueError("allowed action names must be non-empty")

    def check(self, proposal: ActionProposal) -> PolicyDecision:
        if proposal.action_type not in self.allowed_actions:
            return PolicyDecision(False, "action_type_not_allowlisted")
        return PolicyDecision(True, "action_type_allowlisted")


ActionExecutor = Callable[[Mapping[str, Any]], ActionResult]


@dataclass(frozen=True)
class StrategyRecord:
    record_id: str
    strategy_key: str
    action_type: str
    proposal_id: str
    success: bool
    score: float
    lesson: str
    created_at: str


@dataclass(frozen=True)
class StrategyStats:
    strategy_key: str
    observations: int
    successes: int
    success_rate: float
    mean_score: float


class StrategyLedger:
    """Append-only empirical learning memory.

    It stores outcome statistics only. It has no reference to PermissionPolicy
    and therefore cannot grant capabilities.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        proposal: ActionProposal,
        result: ActionResult,
        signal: LearningSignal,
    ) -> StrategyRecord:
        created_at = _now()
        body = {
            "strategy_key": proposal.strategy_key,
            "action_type": proposal.action_type,
            "proposal_id": proposal.proposal_id,
            "success": bool(result.success),
            "score": float(signal.score),
            "lesson": signal.lesson,
            "created_at": created_at,
        }
        record = StrategyRecord(_hash(body), **body)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(asdict(record)) + "\n")
        return record

    def records(self) -> Tuple[StrategyRecord, ...]:
        if not self.path.exists():
            return ()
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(StrategyRecord(**json.loads(line)))
        return tuple(out)

    def stats(self, strategy_key: str) -> StrategyStats:
        records = [r for r in self.records() if r.strategy_key == strategy_key]
        if not records:
            return StrategyStats(strategy_key, 0, 0, 0.0, 0.0)
        successes = sum(1 for r in records if r.success)
        return StrategyStats(
            strategy_key=strategy_key,
            observations=len(records),
            successes=successes,
            success_rate=successes / len(records),
            mean_score=sum(r.score for r in records) / len(records),
        )


@dataclass(frozen=True)
class AgentCycle:
    cycle_id: str
    goal_id: str
    observation_digest: str
    hypotheses: Tuple[Hypothesis, ...]
    proposal: Optional[ActionProposal]
    policy: Optional[PolicyDecision]
    action_result: Optional[ActionResult]
    learning: Optional[LearningSignal]
    strategy_stats: Optional[StrategyStats]
    drift: DriftReport
    cognitive_cycle: int
    reflexive_cycle: int
    memory_count: int


class SynAgentLoop:
    """Bounded, auditable autonomous cycle for Synergesis."""

    def __init__(
        self,
        *,
        kernel: SynKernel,
        cognitive_core: SynCognitiveCore,
        aura: Aura,
        policy: PermissionPolicy,
        reasoner: ReasoningProvider,
        executors: Mapping[str, ActionExecutor],
        strategy_ledger: StrategyLedger,
        context_selector: LexicalContextSelector,
    ):
        if aura.core is not cognitive_core:
            raise ValueError("Aura must be attached to the supplied cognitive core")
        self.kernel = kernel
        self.core = cognitive_core
        self.aura = aura
        self.policy = policy
        self.reasoner = reasoner
        self.executors = dict(executors)
        self.strategy_ledger = strategy_ledger
        self.context_selector = context_selector

    def _validate_evidence_refs(self, ids: Sequence[str]) -> None:
        known = {e.evidence_id for e in self.aura.research.store.all()}
        unknown = sorted(set(ids) - known)
        if unknown:
            raise ValueError(f"unknown evidence ids: {unknown}")

    def run_cycle(
        self,
        *,
        goal: Goal,
        observation: AgentObservation,
        required_predicates: Sequence[str] = (),
        rules: Sequence[Any] = (),
    ) -> AgentCycle:
        before_facts = tuple(self.core.memory.query())

        obs = self.kernel.observe(
            observation.kind,
            dict(observation.payload),
            observation.source,
        )

        gaps = tuple(self.core.selene.gaps(required_predicates))
        all_evidence = tuple(self.aura.research.store.all())
        query = " ".join(
            (
                goal.description,
                observation.kind,
                _canonical(dict(observation.payload)),
            )
        )
        selected = self.context_selector.select(
            query=query,
            facts=before_facts,
            evidence=all_evidence,
        )
        context = AgentContext(
            goal=goal,
            observation=observation,
            facts=selected.facts,
            gaps=gaps,
            evidence=selected.evidence,
        )

        reasoning = self.reasoner.reason(context)
        if not isinstance(reasoning, ReasoningOutput):
            raise TypeError("reasoner.reason must return ReasoningOutput")

        for hypothesis in reasoning.hypotheses:
            self._validate_evidence_refs(hypothesis.evidence_ids)
            self.kernel.memory.append(
                "hypothesis",
                asdict(hypothesis),
                self.kernel.identity,
            )
            self.kernel.blackboard.publish(
                f"hypothesis:{hypothesis.hypothesis_id[:16]}",
                asdict(hypothesis),
            )

        proposal = reasoning.action
        policy_decision: Optional[PolicyDecision] = None
        action_result: Optional[ActionResult] = None
        learning: Optional[LearningSignal] = None
        strategy_stats: Optional[StrategyStats] = None

        if proposal is not None:
            self._validate_evidence_refs(proposal.evidence_ids)
            self.kernel.memory.append(
                "action_proposal",
                asdict(proposal),
                self.kernel.identity,
            )

            policy_decision = self.policy.check(proposal)
            self.kernel.memory.append(
                "policy_decision",
                {
                    "proposal_id": proposal.proposal_id,
                    **asdict(policy_decision),
                },
                self.kernel.identity,
            )

            if policy_decision.allowed:
                executor = self.executors.get(proposal.action_type)
                if executor is None:
                    action_result = ActionResult(
                        proposal.action_type,
                        False,
                        {},
                        "no_executor_registered",
                    )
                else:
                    action_result = executor(dict(proposal.parameters))
                    if not isinstance(action_result, ActionResult):
                        raise TypeError("action executor must return ActionResult")
                    if action_result.action_type != proposal.action_type:
                        raise ValueError("executor returned a result for a different action type")

                self.kernel.observe(
                    "action_result",
                    asdict(action_result),
                    f"executor:{proposal.action_type}",
                )
                learning = self.reasoner.evaluate(context, proposal, action_result)
                if not isinstance(learning, LearningSignal):
                    raise TypeError("reasoner.evaluate must return LearningSignal")

                self.strategy_ledger.append(proposal, action_result, learning)
                strategy_stats = self.strategy_ledger.stats(proposal.strategy_key)
                self.kernel.memory.append(
                    "learning_signal",
                    {
                        "proposal_id": proposal.proposal_id,
                        **asdict(learning),
                        "strategy_stats": asdict(strategy_stats),
                    },
                    self.kernel.identity,
                )

        cognitive = self.core.cycle_once(
            rules=rules,
            required_predicates=required_predicates,
        )
        after_facts = tuple(self.core.memory.query())
        drift = self.aura.echo.compare(before_facts, after_facts)

        reflexive = self.kernel.reflect()
        cycle_id = _hash(
            {
                "goal_id": goal.goal_id,
                "observation_digest": obs.digest,
                "cognitive_cycle": cognitive.cycle,
                "reflexive_cycle": reflexive.cycle,
                "proposal_id": proposal.proposal_id if proposal else None,
            }
        )
        self.kernel.memory.append(
            "agent_cycle",
            {
                "cycle_id": cycle_id,
                "goal_id": goal.goal_id,
                "cognitive_cycle": cognitive.cycle,
                "reflexive_cycle": reflexive.cycle,
                "policy": asdict(policy_decision) if policy_decision else None,
            },
            self.kernel.identity,
        )

        return AgentCycle(
            cycle_id=cycle_id,
            goal_id=goal.goal_id,
            observation_digest=obs.digest,
            hypotheses=reasoning.hypotheses,
            proposal=proposal,
            policy=policy_decision,
            action_result=action_result,
            learning=learning,
            strategy_stats=strategy_stats,
            drift=drift,
            cognitive_cycle=cognitive.cycle,
            reflexive_cycle=reflexive.cycle,
            memory_count=len(self.kernel.memory.read_all()),
        )
