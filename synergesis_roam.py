"""SYN-ROAM: bounded, auditable adaptive research for Synergesis.

SYN-ROAM learns *how to search*, not merely what to remember.

It never grants itself permissions and never treats retrieved material as truth.
External results enter Synergesis as untrusted evidence, with provenance in the
Glyph Graph. Research methods are evaluated from observed outcomes and may be
selected adaptively using empirical performance.

Core loop:
    gap/question -> choose method -> bounded search -> ingest evidence
    -> evaluate outcome -> update method statistics -> choose better next time

Important constraints
---------------------
- No infinite roaming loop.
- No hidden default budget.
- No agreement/reinforcement score: confirming the current hypothesis is not a
  reward by itself.
- Counter-evidence discovery may be explicitly required.
- External content is marked tainted/untrusted through AEGIS.
- Search adapters cannot execute arbitrary actions; they only return material.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_aegis import AegisSecurityGraph
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph


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


def _unit(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    v = float(value)
    if not math.isfinite(v) or not 0.0 <= v <= 1.0:
        raise ValueError(f"{name} must be in [0,1]")
    return v


@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    source_type: str
    domains: Tuple[str, ...]
    max_items_per_query: int
    external_untrusted: bool
    enabled: bool = True

    def __post_init__(self):
        if not self.source_id.strip() or not self.source_type.strip():
            raise ValueError("source_id and source_type are required")
        if not self.domains or any(not x.strip() for x in self.domains):
            raise ValueError("source domains are required")
        if self.max_items_per_query < 1:
            raise ValueError("max_items_per_query must be >= 1")


class SourceRegistry:
    def __init__(self):
        self._policies: dict[str, SourcePolicy] = {}

    def register(self, policy: SourcePolicy) -> SourcePolicy:
        old = self._policies.get(policy.source_id)
        if old is not None and old != policy:
            raise ValueError("source_id collision")
        self._policies[policy.source_id] = policy
        return policy

    def get(self, source_id: str) -> SourcePolicy:
        try:
            return self._policies[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source: {source_id}") from exc

    def enabled_for_domain(self, domain: str) -> Tuple[SourcePolicy, ...]:
        return tuple(
            p for p in self._policies.values()
            if p.enabled and ("*" in p.domains or domain in p.domains)
        )

    def policies(self) -> Tuple[SourcePolicy, ...]:
        return tuple(
            sorted(self._policies.values(), key=lambda p: p.source_id)
        )


@dataclass(frozen=True)
class SearchStep:
    source_id: str
    perspective: str
    query_template: str
    max_items: int

    def __post_init__(self):
        if self.perspective not in {"explore", "support", "challenge"}:
            raise ValueError("invalid search perspective")
        if not self.query_template.strip():
            raise ValueError("query_template is required")
        if self.max_items < 1:
            raise ValueError("max_items must be >= 1")

    def render(self, question: str, hypothesis: Optional[str]) -> str:
        return self.query_template.format(
            question=question,
            hypothesis=hypothesis or "",
        ).strip()


@dataclass(frozen=True)
class ResearchMethod:
    method_id: str
    name: str
    domain: str
    steps: Tuple[SearchStep, ...]
    created_by: str
    created_at: str

    def __post_init__(self):
        if not self.method_id.strip() or not self.name.strip() or not self.domain.strip():
            raise ValueError("method identity fields are required")
        if not self.steps:
            raise ValueError("research method requires at least one step")


def make_method(
    *,
    name: str,
    domain: str,
    steps: Sequence[SearchStep],
    created_by: str,
) -> ResearchMethod:
    if not created_by.strip():
        raise ValueError("created_by is required")
    created_at = _now()
    payload = {
        "name": name,
        "domain": domain,
        "steps": [asdict(s) for s in steps],
        "created_by": created_by,
    }
    return ResearchMethod(
        method_id=f"method:{_hash(payload)[:32]}",
        name=name,
        domain=domain,
        steps=tuple(steps),
        created_by=created_by,
        created_at=created_at,
    )


@dataclass(frozen=True)
class RoamLimits:
    max_steps_per_session: int
    max_items_per_session: int
    max_budget_units: float

    def __post_init__(self):
        if self.max_steps_per_session < 1:
            raise ValueError("max_steps_per_session must be >= 1")
        if self.max_items_per_session < 1:
            raise ValueError("max_items_per_session must be >= 1")
        if not math.isfinite(self.max_budget_units) or self.max_budget_units <= 0:
            raise ValueError("max_budget_units must be finite and > 0")


@dataclass(frozen=True)
class ResearchQuestion:
    question_id: str
    domain: str
    question: str
    hypothesis: Optional[str]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        domain: str,
        question: str,
        hypothesis: Optional[str] = None,
    ) -> "ResearchQuestion":
        if not domain.strip() or not question.strip():
            raise ValueError("domain and question are required")
        payload = {
            "domain": domain,
            "question": question,
            "hypothesis": hypothesis,
        }
        return cls(
            question_id=f"rq:{_hash(payload)[:32]}",
            domain=domain,
            question=question,
            hypothesis=hypothesis,
            created_at=_now(),
        )


@dataclass(frozen=True)
class RetrievedItem:
    source_ref: str
    title: str
    content: str
    source_type: str
    cost_units: float

    def __post_init__(self):
        if not self.source_ref.strip() or not self.title.strip() or not self.content.strip():
            raise ValueError("retrieved item source_ref/title/content are required")
        if not self.source_type.strip():
            raise ValueError("retrieved item source_type is required")
        if not math.isfinite(self.cost_units) or self.cost_units < 0:
            raise ValueError("cost_units must be finite and >= 0")


class SearchAdapter(Protocol):
    def search(
        self,
        *,
        query: str,
        max_items: int,
    ) -> Sequence[RetrievedItem]:
        ...


@dataclass(frozen=True)
class SearchExecution:
    step_index: int
    source_id: str
    perspective: str
    query: str
    evidence_ids: Tuple[str, ...]
    item_count: int
    cost_units: float
    step_glyph_id: str


@dataclass(frozen=True)
class RoamSession:
    session_id: str
    question: ResearchQuestion
    method_id: str
    executions: Tuple[SearchExecution, ...]
    total_items: int
    total_cost_units: float
    status: str
    plan_glyph_id: str

    def __post_init__(self):
        if self.status not in {"completed", "budget_exhausted", "blocked"}:
            raise ValueError("invalid roam session status")


@dataclass(frozen=True)
class OutcomeMetrics:
    verified_yield: float
    novelty_yield: float
    contradiction_yield: float
    calibration_gain: float
    predictive_value: float
    redundancy: float
    normalized_cost: float

    def __post_init__(self):
        for name, value in asdict(self).items():
            _unit(value, name)


@dataclass(frozen=True)
class UtilityWeights:
    verified_yield: float
    novelty_yield: float
    contradiction_yield: float
    calibration_gain: float
    predictive_value: float
    redundancy_penalty: float
    cost_penalty: float

    def __post_init__(self):
        values = asdict(self)
        for name, value in values.items():
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        positive = sum(
            values[k]
            for k in (
                "verified_yield",
                "novelty_yield",
                "contradiction_yield",
                "calibration_gain",
                "predictive_value",
            )
        )
        if positive <= 0:
            raise ValueError("at least one positive utility reward is required")


def score_outcome(metrics: OutcomeMetrics, weights: UtilityWeights) -> float:
    """Observed research utility.

    Deliberately excludes "agreement with the current hypothesis". Finding
    contradiction can increase utility.
    """
    return (
        weights.verified_yield * metrics.verified_yield
        + weights.novelty_yield * metrics.novelty_yield
        + weights.contradiction_yield * metrics.contradiction_yield
        + weights.calibration_gain * metrics.calibration_gain
        + weights.predictive_value * metrics.predictive_value
        - weights.redundancy_penalty * metrics.redundancy
        - weights.cost_penalty * metrics.normalized_cost
    )


@dataclass(frozen=True)
class MethodOutcome:
    outcome_id: str
    session_id: str
    method_id: str
    domain: str
    metrics: OutcomeMetrics
    utility: float
    evaluated_at: str


@dataclass(frozen=True)
class MethodStats:
    method_id: str
    observations: int
    mean_utility: float
    utility_variance: float


class MethodLedger:
    """Append-only empirical outcome ledger with SHA-256 chaining."""

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
                raise ValueError("method ledger sequence failure")
            if event["previous_digest"] != previous:
                raise ValueError("method ledger chain failure")
            body = {
                "sequence": event["sequence"],
                "previous_digest": event["previous_digest"],
                "payload": event["payload"],
            }
            digest = _hash(body)
            if digest != event["digest"]:
                raise ValueError("method ledger integrity failure")
            out.append(event)
            previous = digest
        return tuple(out)

    def append(self, outcome: MethodOutcome) -> MethodOutcome:
        events = self.events()
        body = {
            "sequence": len(events) + 1,
            "previous_digest": events[-1]["digest"] if events else None,
            "payload": {
                **asdict(outcome),
                "metrics": asdict(outcome.metrics),
            },
        }
        event = {**body, "digest": _hash(body)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(event) + "\n")
        return outcome

    def outcomes(self, *, method_id: Optional[str] = None) -> Tuple[MethodOutcome, ...]:
        results = []
        for event in self.events():
            payload = dict(event["payload"])
            payload["metrics"] = OutcomeMetrics(**payload["metrics"])
            outcome = MethodOutcome(**payload)
            if method_id is None or outcome.method_id == method_id:
                results.append(outcome)
        return tuple(results)

    def stats(self, method_id: str) -> MethodStats:
        values = [x.utility for x in self.outcomes(method_id=method_id)]
        if not values:
            return MethodStats(method_id, 0, 0.0, 0.0)
        mean = sum(values) / len(values)
        variance = (
            sum((x - mean) ** 2 for x in values) / len(values)
            if len(values) > 1 else 0.0
        )
        return MethodStats(method_id, len(values), mean, variance)


@dataclass(frozen=True)
class SelectionConfig:
    exploration_strength: float
    require_counter_search_for_hypothesis: bool

    def __post_init__(self):
        if (
            not math.isfinite(self.exploration_strength)
            or self.exploration_strength < 0
        ):
            raise ValueError("exploration_strength must be finite and >= 0")


class ResearchMethodLearner:
    """Empirical method selection using a bounded UCB-style exploration bonus."""

    def __init__(
        self,
        *,
        ledger: MethodLedger,
        config: SelectionConfig,
    ):
        self.ledger = ledger
        self.config = config
        self._methods: dict[str, ResearchMethod] = {}

    def register(self, method: ResearchMethod) -> ResearchMethod:
        old = self._methods.get(method.method_id)
        if old is not None and old != method:
            raise ValueError("method_id collision")
        self._methods[method.method_id] = method
        return method

    def _eligible(self, question: ResearchQuestion) -> Tuple[ResearchMethod, ...]:
        candidates = tuple(
            m for m in self._methods.values()
            if m.domain in {question.domain, "*"}
        )
        if self.config.require_counter_search_for_hypothesis and question.hypothesis:
            candidates = tuple(
                m for m in candidates
                if any(step.perspective == "challenge" for step in m.steps)
            )
        return candidates

    def select(self, question: ResearchQuestion) -> ResearchMethod:
        candidates = self._eligible(question)
        if not candidates:
            raise ValueError("no eligible research method")

        # Deterministic cold-start: least observed, then lexical method_id.
        stats = {m.method_id: self.ledger.stats(m.method_id) for m in candidates}
        zero = [m for m in candidates if stats[m.method_id].observations == 0]
        if zero:
            return sorted(zero, key=lambda m: m.method_id)[0]

        total = sum(stats[m.method_id].observations for m in candidates)
        scored = []
        for method in candidates:
            s = stats[method.method_id]
            exploration = self.config.exploration_strength * math.sqrt(
                math.log(max(total, 1)) / s.observations
            )
            scored.append((s.mean_utility + exploration, method.method_id, method))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][2]

    def record_outcome(
        self,
        *,
        session: RoamSession,
        metrics: OutcomeMetrics,
        weights: UtilityWeights,
    ) -> MethodOutcome:
        utility = score_outcome(metrics, weights)
        payload = {
            "session_id": session.session_id,
            "method_id": session.method_id,
            "domain": session.question.domain,
            "metrics": asdict(metrics),
            "utility": utility,
        }
        outcome = MethodOutcome(
            outcome_id=f"ro:{_hash(payload)[:32]}",
            session_id=session.session_id,
            method_id=session.method_id,
            domain=session.question.domain,
            metrics=metrics,
            utility=utility,
            evaluated_at=_now(),
        )
        return self.ledger.append(outcome)


class RoamRuntime:
    """Executes exactly one bounded research session."""

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        aura: Any,
        security_graph: AegisSecurityGraph,
        source_registry: SourceRegistry,
        adapters: Mapping[str, SearchAdapter],
        limits: RoamLimits,
        actor: str = "SYN-ROAM",
    ):
        self.graph = graph
        self.aura = aura
        self.security_graph = security_graph
        self.source_registry = source_registry
        self.adapters = dict(adapters)
        self.limits = limits
        self.actor = actor

    def _plan_glyph(
        self,
        question: ResearchQuestion,
        method: ResearchMethod,
    ) -> Glyph:
        question_glyph = self.graph.create(
            "goal",
            actor=self.actor,
            content={
                "kind": "research_question",
                "domain": question.domain,
                "question": question.question,
                "hypothesis": question.hypothesis,
            },
            external_refs=(question.question_id,),
            dedupe_external_ref=question.question_id,
        )
        return self.graph.create(
            "plan",
            actor=self.actor,
            content={
                "kind": "research_method",
                "method_id": method.method_id,
                "method_name": method.name,
                "domain": method.domain,
                "step_count": len(method.steps),
            },
            external_refs=(method.method_id, f"roam-plan:{question.question_id}:{method.method_id}"),
            derived_from=(question_glyph.glyph_id,),
            dedupe_external_ref=f"roam-plan:{question.question_id}:{method.method_id}",
        )

    def run(
        self,
        *,
        question: ResearchQuestion,
        method: ResearchMethod,
    ) -> RoamSession:
        if method.domain not in {question.domain, "*"}:
            raise ValueError("method domain does not match question domain")
        if len(method.steps) > self.limits.max_steps_per_session:
            raise ValueError("method exceeds max_steps_per_session")

        plan_glyph = self._plan_glyph(question, method)
        executions = []
        total_items = 0
        total_cost = 0.0
        status = "completed"

        for index, step in enumerate(method.steps, start=1):
            if total_items >= self.limits.max_items_per_session:
                status = "budget_exhausted"
                break
            if total_cost >= self.limits.max_budget_units:
                status = "budget_exhausted"
                break

            source = self.source_registry.get(step.source_id)
            if not source.enabled:
                raise ValueError(f"source disabled: {step.source_id}")
            if not ("*" in source.domains or question.domain in source.domains):
                raise ValueError(f"source not allowed for domain: {step.source_id}")
            adapter = self.adapters.get(step.source_id)
            if adapter is None:
                raise ValueError(f"no adapter configured for source: {step.source_id}")

            remaining_items = self.limits.max_items_per_session - total_items
            requested = min(step.max_items, source.max_items_per_query, remaining_items)
            query = step.render(question.question, question.hypothesis)

            step_glyph = self.graph.create(
                "step",
                actor=self.actor,
                content={
                    "kind": "roam_search",
                    "step_index": index,
                    "source_id": step.source_id,
                    "perspective": step.perspective,
                    "query": query,
                    "requested_max_items": requested,
                },
                external_refs=(f"roam-step:{question.question_id}:{method.method_id}:{index}",),
                derived_from=(plan_glyph.glyph_id,),
                dedupe_external_ref=f"roam-step:{question.question_id}:{method.method_id}:{index}",
            )
            self.graph.relate(
                step_glyph.glyph_id,
                plan_glyph.glyph_id,
                "part_of",
                actor=self.actor,
            )

            items = tuple(adapter.search(query=query, max_items=requested))
            if len(items) > requested:
                raise ValueError("search adapter returned more items than requested")

            evidence_ids = []
            step_cost = 0.0
            evidence_glyphs = []
            for item in items:
                if total_items >= self.limits.max_items_per_session:
                    status = "budget_exhausted"
                    break
                if total_cost + item.cost_units > self.limits.max_budget_units:
                    status = "budget_exhausted"
                    break

                evidence = self.aura.research_ingest(
                    item.source_ref,
                    item.title,
                    item.content,
                    item.source_type,
                )
                evidence_ids.append(evidence.evidence_id)
                total_items += 1
                total_cost += item.cost_units
                step_cost += item.cost_units

                matches = self.graph.ledger.find_by_external_ref(
                    evidence.evidence_id,
                    glyph_type="evidence",
                )
                if not matches:
                    raise ValueError("audited research ingestion did not create EvidenceGlyph")
                evidence_glyph = matches[-1]
                evidence_glyphs.append(evidence_glyph)

                if source.external_untrusted:
                    if self.security_graph.origin_binding(evidence_glyph.glyph_id) is None:
                        self.security_graph.bind_origin(
                            evidence_glyph.glyph_id,
                            authority_class="external_untrusted",
                            reason=f"retrieved from external source {source.source_id}",
                        )
                    self.security_graph.mark_taint(
                        evidence_glyph.glyph_id,
                        label="external_untrusted",
                        reason=f"retrieved from external source {source.source_id}",
                    )

                self.graph.relate(
                    evidence_glyph.glyph_id,
                    step_glyph.glyph_id,
                    "derived_from",
                    actor=self.actor,
                    metadata={"perspective": step.perspective},
                )

            executions.append(
                SearchExecution(
                    step_index=index,
                    source_id=step.source_id,
                    perspective=step.perspective,
                    query=query,
                    evidence_ids=tuple(evidence_ids),
                    item_count=len(evidence_ids),
                    cost_units=step_cost,
                    step_glyph_id=step_glyph.glyph_id,
                )
            )

            if status == "budget_exhausted":
                break

        session_payload = {
            "question_id": question.question_id,
            "method_id": method.method_id,
            "executions": [asdict(x) for x in executions],
            "total_items": total_items,
            "total_cost_units": total_cost,
            "status": status,
        }
        session_id = f"roam:{_hash(session_payload)[:32]}"
        cycle = self.graph.create(
            "cycle",
            actor=self.actor,
            content={
                "kind": "roam_session",
                "session_id": session_id,
                "method_id": method.method_id,
                "status": status,
                "total_items": total_items,
                "total_cost_units": total_cost,
            },
            external_refs=(session_id,),
            derived_from=tuple(
                [plan_glyph.glyph_id]
                + [x.step_glyph_id for x in executions]
            ),
            dedupe_external_ref=session_id,
        )

        return RoamSession(
            session_id=session_id,
            question=question,
            method_id=method.method_id,
            executions=tuple(executions),
            total_items=total_items,
            total_cost_units=total_cost,
            status=status,
            plan_glyph_id=plan_glyph.glyph_id,
        )


class SynRoam:
    """High-level adaptive SYN-ROAM facade.

    `research_once` selects a method and runs exactly one bounded session.
    `evaluate` records observed utility. No run-forever API is provided.
    """

    def __init__(
        self,
        *,
        learner: ResearchMethodLearner,
        runtime: RoamRuntime,
        utility_weights: UtilityWeights,
    ):
        self.learner = learner
        self.runtime = runtime
        self.utility_weights = utility_weights

    def research_once(self, question: ResearchQuestion) -> RoamSession:
        method = self.learner.select(question)
        return self.runtime.run(question=question, method=method)

    def evaluate(
        self,
        session: RoamSession,
        metrics: OutcomeMetrics,
    ) -> MethodOutcome:
        outcome = self.learner.record_outcome(
            session=session,
            metrics=metrics,
            weights=self.utility_weights,
        )

        session_glyphs = self.runtime.graph.ledger.find_by_external_ref(
            session.session_id,
            glyph_type="cycle",
        )
        parents = (session_glyphs[-1].glyph_id,) if session_glyphs else ()
        self.runtime.graph.create(
            "learning",
            actor="SYN-ROAM",
            content={
                "kind": "research_method_outcome",
                "outcome_id": outcome.outcome_id,
                "method_id": outcome.method_id,
                "domain": outcome.domain,
                "utility": outcome.utility,
                "metrics": asdict(outcome.metrics),
            },
            external_refs=(outcome.outcome_id,),
            derived_from=parents,
            dedupe_external_ref=outcome.outcome_id,
        )
        return outcome
