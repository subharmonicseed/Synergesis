"""Empirical evolution of SYN-ROAM research methods.

A model may *propose* a method variation, but it cannot activate it directly.
Candidates are schema/permission validated, trialed under normal ROAM budgets,
and promoted only after explicit empirical comparison with a baseline.

This is strategy evolution, not self-modifying code.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from string import Formatter
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_glyph_protocol import GlyphAuditGraph
from synergesis_roam import (
    MethodLedger,
    MethodOutcome,
    OutcomeMetrics,
    ResearchMethod,
    ResearchMethodLearner,
    RoamSession,
    SearchStep,
    SourceRegistry,
    UtilityWeights,
    make_method,
)


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
class ResearchMethodDraft:
    name: str
    domain: str
    steps: Tuple[SearchStep, ...]
    rationale: str

    def __post_init__(self):
        if not self.name.strip() or not self.domain.strip() or not self.rationale.strip():
            raise ValueError("draft name/domain/rationale are required")
        if not self.steps:
            raise ValueError("method draft requires at least one step")


@dataclass(frozen=True)
class EvolutionPolicy:
    max_steps_per_method: int
    min_trials_per_method: int
    promotion_margin: float
    require_counter_search: bool

    def __post_init__(self):
        if self.max_steps_per_method < 1:
            raise ValueError("max_steps_per_method must be >= 1")
        if self.min_trials_per_method < 1:
            raise ValueError("min_trials_per_method must be >= 1")
        if not math.isfinite(self.promotion_margin):
            raise ValueError("promotion_margin must be finite")


@dataclass(frozen=True)
class MethodCandidate:
    candidate_id: str
    baseline_method_id: str
    method: ResearchMethod
    rationale: str
    status: str

    def __post_init__(self):
        if self.status not in {"experimental", "promoted", "rejected"}:
            raise ValueError("invalid method candidate status")


@dataclass(frozen=True)
class EvolutionDecision:
    candidate_id: str
    decision: str
    candidate_observations: int
    baseline_observations: int
    candidate_mean_utility: Optional[float]
    baseline_mean_utility: Optional[float]
    margin_observed: Optional[float]
    required_margin: float
    rationale: str

    def __post_init__(self):
        if self.decision not in {"insufficient_data", "promote", "reject"}:
            raise ValueError("invalid evolution decision")


class MethodEvolutionLedger:
    """Hash-chained candidate lifecycle ledger."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def events(self) -> Tuple[Mapping[str, Any], ...]:
        previous = None
        out = []
        for index, event in enumerate(self._raw(), start=1):
            if event["sequence"] != index:
                raise ValueError("evolution ledger sequence failure")
            if event["previous_digest"] != previous:
                raise ValueError("evolution ledger chain failure")
            body = {
                "sequence": event["sequence"],
                "previous_digest": event["previous_digest"],
                "payload": event["payload"],
            }
            digest = _hash(body)
            if digest != event["digest"]:
                raise ValueError("evolution ledger integrity failure")
            out.append(event)
            previous = digest
        return tuple(out)

    def append(self, payload: Mapping[str, Any]) -> None:
        events = self.events()
        body = {
            "sequence": len(events) + 1,
            "previous_digest": events[-1]["digest"] if events else None,
            "payload": dict(payload),
        }
        event = {**body, "digest": _hash(body)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(event) + "\n")


class MethodDraftProvider(Protocol):
    def propose_method(
        self,
        *,
        baseline: ResearchMethod,
        domain: str,
        feedback: Mapping[str, Any],
    ) -> ResearchMethodDraft:
        ...


class MethodEvolutionManager:
    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        source_registry: SourceRegistry,
        learner: ResearchMethodLearner,
        outcome_ledger: MethodLedger,
        evolution_ledger: MethodEvolutionLedger,
        policy: EvolutionPolicy,
        actor: str = "SYN-ROAM-EVOLUTION",
    ):
        self.graph = graph
        self.source_registry = source_registry
        self.learner = learner
        self.outcome_ledger = outcome_ledger
        self.evolution_ledger = evolution_ledger
        self.policy = policy
        self.actor = actor
        self._candidates: dict[str, MethodCandidate] = {}
        self._restore_candidates()

    def _restore_candidates(self) -> None:
        for event in self.evolution_ledger.events():
            payload = event["payload"]
            if payload.get("event") == "candidate_proposed":
                raw_method = dict(payload["method"])
                raw_method["steps"] = tuple(
                    SearchStep(**step) for step in raw_method["steps"]
                )
                method = ResearchMethod(**raw_method)
                candidate = MethodCandidate(
                    candidate_id=payload["candidate_id"],
                    baseline_method_id=payload["baseline_method_id"],
                    method=method,
                    rationale=payload["rationale"],
                    status="experimental",
                )
                self._candidates[candidate.candidate_id] = candidate
            elif payload.get("event") == "candidate_evaluated":
                candidate_id = payload["candidate_id"]
                current = self._candidates.get(candidate_id)
                if current is None:
                    raise ValueError(
                        "evolution ledger decision references unknown candidate"
                    )
                decision = payload["decision"]
                if decision in {"promote", "reject"}:
                    status = "promoted" if decision == "promote" else "rejected"
                    self._candidates[candidate_id] = MethodCandidate(
                        candidate_id=current.candidate_id,
                        baseline_method_id=current.baseline_method_id,
                        method=current.method,
                        rationale=current.rationale,
                        status=status,
                    )

    def _validate_template(self, value: str) -> None:
        allowed = {"question", "hypothesis"}
        fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(value)
            if field_name is not None
        }
        unknown = fields - allowed
        if unknown:
            raise ValueError(
                "query template contains unsupported fields: "
                + ",".join(sorted(unknown))
            )

    def _validate_draft(
        self,
        draft: ResearchMethodDraft,
        baseline: ResearchMethod,
    ) -> None:
        if draft.domain != baseline.domain:
            raise ValueError("candidate cannot change baseline domain")
        if len(draft.steps) > self.policy.max_steps_per_method:
            raise ValueError("candidate exceeds max_steps_per_method")
        if self.policy.require_counter_search and not any(
            step.perspective == "challenge" for step in draft.steps
        ):
            raise ValueError("candidate must contain a challenge step")

        for step in draft.steps:
            source = self.source_registry.get(step.source_id)
            if not source.enabled:
                raise ValueError(f"candidate references disabled source: {step.source_id}")
            if not ("*" in source.domains or draft.domain in source.domains):
                raise ValueError(
                    f"candidate source is outside domain: {step.source_id}"
                )
            if step.max_items > source.max_items_per_query:
                raise ValueError(
                    f"candidate step exceeds source item policy: {step.source_id}"
                )
            self._validate_template(step.query_template)

    def propose(
        self,
        *,
        baseline: ResearchMethod,
        draft: ResearchMethodDraft,
        created_by: str,
    ) -> MethodCandidate:
        self._validate_draft(draft, baseline)
        method = make_method(
            name=draft.name,
            domain=draft.domain,
            steps=draft.steps,
            created_by=created_by,
        )
        payload = {
            "baseline_method_id": baseline.method_id,
            "method_id": method.method_id,
            "rationale": draft.rationale,
        }
        candidate_id = f"candidate:{_hash(payload)[:32]}"
        existing = self._candidates.get(candidate_id)
        if existing is not None:
            return existing

        candidate = MethodCandidate(
            candidate_id=candidate_id,
            baseline_method_id=baseline.method_id,
            method=method,
            rationale=draft.rationale,
            status="experimental",
        )
        self._candidates[candidate_id] = candidate
        self.evolution_ledger.append({
            "event": "candidate_proposed",
            "candidate_id": candidate_id,
            "baseline_method_id": baseline.method_id,
            "method": {
                **asdict(method),
                "steps": [asdict(s) for s in method.steps],
            },
            "rationale": draft.rationale,
        })

        baseline_glyphs = self.graph.ledger.find_by_external_ref(
            baseline.method_id,
            glyph_type="plan",
        )
        parents = (baseline_glyphs[-1].glyph_id,) if baseline_glyphs else ()
        self.graph.create(
            "plan",
            actor=self.actor,
            content={
                "kind": "research_method_candidate",
                "candidate_id": candidate_id,
                "baseline_method_id": baseline.method_id,
                "method_id": method.method_id,
                "name": method.name,
                "domain": method.domain,
                "rationale": draft.rationale,
                "status": "experimental",
                "steps": [asdict(s) for s in method.steps],
            },
            external_refs=(candidate_id, method.method_id),
            derived_from=parents,
            dedupe_external_ref=candidate_id,
        )
        return candidate

    def get(self, candidate_id: str) -> MethodCandidate:
        try:
            return self._candidates[candidate_id]
        except KeyError as exc:
            raise KeyError(f"unknown method candidate: {candidate_id}") from exc

    def record_trial(
        self,
        *,
        candidate_id: str,
        session: RoamSession,
        metrics: OutcomeMetrics,
        weights: UtilityWeights,
    ) -> MethodOutcome:
        candidate = self.get(candidate_id)
        if candidate.status != "experimental":
            raise ValueError("only experimental candidates may receive trials")
        if session.method_id != candidate.method.method_id:
            raise ValueError("trial session does not use candidate method")
        return self.learner.record_outcome(
            session=session,
            metrics=metrics,
            weights=weights,
        )

    def decide(self, candidate_id: str) -> EvolutionDecision:
        candidate = self.get(candidate_id)
        candidate_stats = self.outcome_ledger.stats(candidate.method.method_id)
        baseline_stats = self.outcome_ledger.stats(candidate.baseline_method_id)

        if (
            candidate_stats.observations < self.policy.min_trials_per_method
            or baseline_stats.observations < self.policy.min_trials_per_method
        ):
            decision = EvolutionDecision(
                candidate_id=candidate_id,
                decision="insufficient_data",
                candidate_observations=candidate_stats.observations,
                baseline_observations=baseline_stats.observations,
                candidate_mean_utility=(
                    candidate_stats.mean_utility
                    if candidate_stats.observations else None
                ),
                baseline_mean_utility=(
                    baseline_stats.mean_utility
                    if baseline_stats.observations else None
                ),
                margin_observed=None,
                required_margin=self.policy.promotion_margin,
                rationale="minimum empirical trial count not reached",
            )
            self._record_decision(candidate, decision)
            return decision

        margin = (
            candidate_stats.mean_utility - baseline_stats.mean_utility
        )
        if margin >= self.policy.promotion_margin:
            decision_name = "promote"
            rationale = "candidate met empirical promotion margin"
        else:
            decision_name = "reject"
            rationale = "candidate did not meet empirical promotion margin"

        decision = EvolutionDecision(
            candidate_id=candidate_id,
            decision=decision_name,
            candidate_observations=candidate_stats.observations,
            baseline_observations=baseline_stats.observations,
            candidate_mean_utility=candidate_stats.mean_utility,
            baseline_mean_utility=baseline_stats.mean_utility,
            margin_observed=margin,
            required_margin=self.policy.promotion_margin,
            rationale=rationale,
        )
        self._record_decision(candidate, decision)

        if decision_name == "promote":
            self.learner.register(candidate.method)
            updated = MethodCandidate(
                candidate_id=candidate.candidate_id,
                baseline_method_id=candidate.baseline_method_id,
                method=candidate.method,
                rationale=candidate.rationale,
                status="promoted",
            )
        else:
            updated = MethodCandidate(
                candidate_id=candidate.candidate_id,
                baseline_method_id=candidate.baseline_method_id,
                method=candidate.method,
                rationale=candidate.rationale,
                status="rejected",
            )
        self._candidates[candidate_id] = updated
        return decision

    def _record_decision(
        self,
        candidate: MethodCandidate,
        decision: EvolutionDecision,
    ) -> None:
        self.evolution_ledger.append({
            "event": "candidate_evaluated",
            **asdict(decision),
        })
        candidates = self.graph.ledger.find_by_external_ref(
            candidate.candidate_id,
            glyph_type="plan",
        )
        parents = (candidates[-1].glyph_id,) if candidates else ()
        self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "research_method_evolution",
                **asdict(decision),
            },
            external_refs=(
                f"evolution-decision:{candidate.candidate_id}:"
                f"{len(self.evolution_ledger.events())}"
            ),
            derived_from=parents,
        )
