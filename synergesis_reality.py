"""SYN-REALITY: independent verification of agent action effects.

The executor is not treated as ground truth.

For every profiled consequential action, SYN-REALITY can compare:
    model intent -> executor claim -> independent runtime observations

The independent observers are trusted control-plane components configured outside
the model. Their observations are written as Glyphs with explicit origin
authority before a final reality verdict is produced.

Security invariants
-------------------
1. Executor success != observed success.
2. The model cannot choose its own observers or reality contract.
3. Missing/ambiguous runtime evidence fails closed when verification is required.
4. Conflicting runtime observers fail closed.
5. A contradicted executor claim is tainted and cannot silently become learning.
6. Runtime observations are audit artifacts, not reconstructed chain-of-thought.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, Tuple

from synergesis_aegis import AegisSecurityGraph
from synergesis_agent_loop_v2 import ActionProposal, ActionResult
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass(frozen=True)
class RealityObservation:
    observer_id: str
    channel: str
    resource: str
    facts: Mapping[str, Any]
    observed_at: str
    event_id: str

    @classmethod
    def create(
        cls,
        *,
        observer_id: str,
        channel: str,
        resource: str,
        facts: Mapping[str, Any],
        observed_at: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> "RealityObservation":
        if not observer_id.strip() or not channel.strip() or not resource.strip():
            raise ValueError("observer_id, channel and resource are required")
        at = observed_at or _now()
        body = {
            "observer_id": observer_id,
            "channel": channel,
            "resource": resource,
            "facts": dict(facts),
            "observed_at": at,
        }
        return cls(
            observer_id=observer_id,
            channel=channel,
            resource=resource,
            facts=dict(facts),
            observed_at=at,
            event_id=event_id or f"reality:{_digest(body)[:32]}",
        )


class RealityProbe(Protocol):
    def observe(
        self,
        *,
        action_type: str,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[RealityObservation]:
        ...


@dataclass(frozen=True)
class RealityProbeBinding:
    observer_id: str
    authority_class: str
    probe: RealityProbe

    def __post_init__(self):
        if not self.observer_id.strip() or not self.authority_class.strip():
            raise ValueError("observer_id and authority_class are required")


@dataclass(frozen=True)
class RealityAssertion:
    """A deterministic assertion over one observer's facts.

    Supported operators:
    - eq: fact == expected_value
    - truthy: bool(fact) is True
    - eq_parameter: fact == proposal.parameters[parameter_key]
    - sha256_parameter_utf8: fact == sha256(str(parameter).encode()).hexdigest()
    """

    observer_id: str
    fact_key: str
    operator: str
    expected_value: Any = None
    parameter_key: Optional[str] = None

    def __post_init__(self):
        if not self.observer_id.strip() or not self.fact_key.strip():
            raise ValueError("assertion observer_id and fact_key are required")
        allowed = {
            "eq",
            "truthy",
            "eq_parameter",
            "sha256_parameter_utf8",
        }
        if self.operator not in allowed:
            raise ValueError(f"unsupported reality assertion operator: {self.operator}")
        if self.operator in {"eq_parameter", "sha256_parameter_utf8"}:
            if self.parameter_key is None or not self.parameter_key.strip():
                raise ValueError(
                    f"{self.operator} requires parameter_key"
                )


@dataclass(frozen=True)
class RealityProfile:
    action_type: str
    required_observer_ids: Tuple[str, ...]
    assertions: Tuple[RealityAssertion, ...]
    verification_required: bool = True
    max_observations: int = 16

    def __post_init__(self):
        if not self.action_type.strip():
            raise ValueError("reality profile action_type is required")
        if not self.required_observer_ids:
            raise ValueError("at least one required observer is required")
        if len(set(self.required_observer_ids)) != len(self.required_observer_ids):
            raise ValueError("required observer ids must be unique")
        if not self.assertions:
            raise ValueError("at least one reality assertion is required")
        if self.max_observations < 1:
            raise ValueError("max_observations must be >= 1")
        required = set(self.required_observer_ids)
        unknown = sorted(
            {a.observer_id for a in self.assertions} - required
        )
        if unknown:
            raise ValueError(
                "assertions reference observers outside the required set: "
                + ",".join(unknown)
            )


@dataclass(frozen=True)
class ObserverEvaluation:
    observer_id: str
    status: str
    passed_assertions: int
    failed_assertions: int
    unknown_assertions: int

    def __post_init__(self):
        if self.status not in {"confirmed", "contradicted", "unknown", "missing"}:
            raise ValueError("invalid observer evaluation status")


@dataclass(frozen=True)
class RealityAssessment:
    proposal_id: str
    action_type: str
    resource: str
    status: str
    effect_observed: Optional[bool]
    executor_claim_matches_reality: Optional[bool]
    raw_result: ActionResult
    effective_result: ActionResult
    observer_evaluations: Tuple[ObserverEvaluation, ...]
    observation_glyph_ids: Tuple[str, ...]
    executor_outcome_glyph_id: str
    verdict_glyph_id: str
    effective_outcome_glyph_id: str

    def __post_init__(self):
        if self.status not in {
            "confirmed",
            "contradicted",
            "unverified",
            "observer_conflict",
        }:
            raise ValueError("invalid reality assessment status")


@dataclass(frozen=True)
class RealityReliabilityReport:
    action_type: str
    assessments: int
    verified: int
    executor_claim_matches: int
    executor_claim_mismatches: int
    unverified_or_conflicted: int
    match_rate_on_verified: Optional[float]


class FileStateProbe:
    """Read-only filesystem observer with an explicit sandbox root."""

    def __init__(
        self,
        *,
        observer_id: str,
        allowed_root: str | Path,
        path_parameter: str,
        max_hash_bytes: int,
    ):
        if not observer_id.strip() or not path_parameter.strip():
            raise ValueError("observer_id and path_parameter are required")
        if max_hash_bytes < 1:
            raise ValueError("max_hash_bytes must be >= 1")
        self.observer_id = observer_id
        self.allowed_root = Path(allowed_root).resolve()
        self.allowed_root.mkdir(parents=True, exist_ok=True)
        self.path_parameter = path_parameter
        self.max_hash_bytes = max_hash_bytes

    def _resolve(self, raw_path: Any) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("file path parameter must be a non-empty string")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.allowed_root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.allowed_root)
        except ValueError as exc:
            raise ValueError("filesystem reality probe path escapes allowed_root") from exc
        return resolved

    def observe(
        self,
        *,
        action_type: str,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[RealityObservation]:
        path = self._resolve(parameters.get(self.path_parameter))
        facts: dict[str, Any] = {
            "exists": path.exists(),
            "is_file": path.is_file(),
            "path": str(path),
        }
        if path.is_file():
            size = path.stat().st_size
            facts["size_bytes"] = size
            if size <= self.max_hash_bytes:
                facts["sha256"] = sha256(path.read_bytes()).hexdigest()
            else:
                facts["sha256"] = None
                facts["hash_skipped_reason"] = "file_exceeds_max_hash_bytes"
        else:
            facts["size_bytes"] = None
            facts["sha256"] = None

        return (
            RealityObservation.create(
                observer_id=self.observer_id,
                channel="filesystem",
                resource=resource,
                facts=facts,
            ),
        )


class FunctionRealityProbe:
    """Adapter for a trusted deterministic observer callback.

    This is useful for OS/network/process integrations without coupling the
    core protocol to a particular platform.
    """

    def __init__(
        self,
        *,
        observer_id: str,
        callback: Callable[
            [str, str, Mapping[str, Any]],
            Sequence[RealityObservation],
        ],
    ):
        if not observer_id.strip():
            raise ValueError("observer_id is required")
        self.observer_id = observer_id
        self.callback = callback

    def observe(
        self,
        *,
        action_type: str,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[RealityObservation]:
        values = tuple(self.callback(action_type, resource, parameters))
        for observation in values:
            if observation.observer_id != self.observer_id:
                raise ValueError(
                    "function reality probe returned observation for different observer"
                )
        return values


class RealityVerifier:
    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        security_graph: AegisSecurityGraph,
        probe_bindings: Sequence[RealityProbeBinding],
        profiles: Sequence[RealityProfile],
        actor: str = "SYN-REALITY",
    ):
        self.graph = graph
        self.security_graph = security_graph
        self.actor = actor
        probe_bindings = tuple(probe_bindings)
        profiles = tuple(profiles)
        self._bindings = {b.observer_id: b for b in probe_bindings}
        if len(self._bindings) != len(probe_bindings):
            raise ValueError("duplicate reality probe observer_id")
        self._profiles = {p.action_type: p for p in profiles}
        if len(self._profiles) != len(profiles):
            raise ValueError("duplicate reality profile action_type")

        for profile in self._profiles.values():
            missing = sorted(
                set(profile.required_observer_ids) - set(self._bindings)
            )
            if missing:
                raise ValueError(
                    "reality profile references unregistered observers: "
                    + ",".join(missing)
                )
        for binding in self._bindings.values():
            if binding.authority_class not in self.security_graph.ORIGIN_CLASSES:
                raise ValueError(
                    "reality observer uses unknown AEGIS authority class: "
                    + binding.authority_class
                )

    def require_profiles_for(self, action_types: Sequence[str]) -> None:
        missing = sorted(set(action_types) - set(self._profiles))
        if missing:
            raise ValueError(
                "missing SYN-REALITY profiles for action types: "
                + ",".join(missing)
            )

    def _expected(
        self,
        assertion: RealityAssertion,
        parameters: Mapping[str, Any],
    ) -> tuple[bool, Any]:
        if assertion.operator == "eq":
            return True, assertion.expected_value
        if assertion.operator == "truthy":
            return True, True
        if assertion.parameter_key not in parameters:
            return False, None
        value = parameters[assertion.parameter_key]
        if assertion.operator == "eq_parameter":
            return True, value
        if assertion.operator == "sha256_parameter_utf8":
            return True, sha256(str(value).encode("utf-8")).hexdigest()
        raise AssertionError("unreachable reality assertion operator")

    def _evaluate_observer(
        self,
        observer_id: str,
        observations: Sequence[RealityObservation],
        assertions: Sequence[RealityAssertion],
        parameters: Mapping[str, Any],
    ) -> ObserverEvaluation:
        relevant_observations = [
            o for o in observations if o.observer_id == observer_id
        ]
        if not relevant_observations:
            return ObserverEvaluation(observer_id, "missing", 0, 0, len(assertions))

        # Multiple observations from the same observer must agree with all
        # assertions. Any explicit contradiction fails the observer.
        passed = 0
        failed = 0
        unknown = 0
        for assertion in assertions:
            expected_known, expected = self._expected(assertion, parameters)
            if not expected_known:
                unknown += 1
                continue

            assertion_seen = False
            assertion_failed = False
            assertion_passed = False
            for observation in relevant_observations:
                if assertion.fact_key not in observation.facts:
                    continue
                assertion_seen = True
                actual = observation.facts[assertion.fact_key]
                if assertion.operator == "truthy":
                    ok = bool(actual) is True
                else:
                    ok = actual == expected
                if ok:
                    assertion_passed = True
                else:
                    assertion_failed = True

            if assertion_failed:
                failed += 1
            elif assertion_seen and assertion_passed:
                passed += 1
            else:
                unknown += 1

        if failed:
            status = "contradicted"
        elif unknown:
            status = "unknown"
        else:
            status = "confirmed"
        return ObserverEvaluation(
            observer_id=observer_id,
            status=status,
            passed_assertions=passed,
            failed_assertions=failed,
            unknown_assertions=unknown,
        )

    def _effective_result(
        self,
        *,
        raw_result: ActionResult,
        status: str,
        effect_observed: Optional[bool],
        claim_matches: Optional[bool],
        verdict_id: str,
        verification_required: bool,
    ) -> ActionResult:
        if effect_observed is True:
            success = True
            error = None
        elif effect_observed is False:
            success = False
            error = "reality:effect_not_observed"
        else:
            success = raw_result.success if not verification_required else False
            error = None if success else f"reality:{status}"

        return ActionResult(
            action_type=raw_result.action_type,
            success=success,
            output={
                "executor_claim": {
                    "success": raw_result.success,
                    "output": dict(raw_result.output),
                    "error": raw_result.error,
                },
                "reality": {
                    "status": status,
                    "effect_observed": effect_observed,
                    "executor_claim_matches_reality": claim_matches,
                    "verdict_glyph_id": verdict_id,
                },
            },
            error=error,
        )

    def verify(
        self,
        *,
        proposal: ActionProposal,
        action_glyph_id: str,
        resource: str,
        raw_result: ActionResult,
    ) -> RealityAssessment:
        profile = self._profiles.get(proposal.action_type)
        if profile is None:
            # An unprofiled consequential action cannot manufacture its own
            # reality contract. Record the executor claim, then fail closed.
            profile = RealityProfile(
                action_type=proposal.action_type,
                required_observer_ids=("__missing_profile__",),
                assertions=(
                    RealityAssertion(
                        "__missing_profile__",
                        "verified",
                        "eq",
                        True,
                    ),
                ),
                verification_required=True,
            )
            observations: tuple[RealityObservation, ...] = ()
        else:
            collected: list[RealityObservation] = []
            for observer_id in profile.required_observer_ids:
                binding = self._bindings[observer_id]
                values = tuple(
                    binding.probe.observe(
                        action_type=proposal.action_type,
                        resource=resource,
                        parameters=proposal.parameters,
                    )
                )
                for observation in values:
                    if observation.observer_id != observer_id:
                        raise ValueError(
                            "reality probe returned observation for a different observer"
                        )
                    if observation.resource != resource:
                        raise ValueError(
                            "reality probe returned observation for a different resource"
                        )
                    collected.append(observation)
                    if len(collected) > profile.max_observations:
                        raise ValueError(
                            "reality probe observations exceed profile max_observations"
                        )
            observations = tuple(collected)

        raw_glyph = self.graph.create(
            "outcome",
            actor=f"executor:{proposal.action_type}",
            content={
                "kind": "executor_claim",
                "proposal_id": proposal.proposal_id,
                "action_type": raw_result.action_type,
                "success": raw_result.success,
                "output": dict(raw_result.output),
                "error": raw_result.error,
                "resource": resource,
            },
            external_refs=(f"executor-claim:{proposal.proposal_id}",),
            derived_from=(action_glyph_id,),
        )

        observation_glyphs: list[Glyph] = []
        for observation in observations:
            glyph = self.graph.create(
                "observation",
                actor=f"observer:{observation.observer_id}",
                content={
                    "kind": "runtime_reality_observation",
                    "observer_id": observation.observer_id,
                    "channel": observation.channel,
                    "resource": observation.resource,
                    "facts": dict(observation.facts),
                    "observed_at": observation.observed_at,
                },
                external_refs=(observation.event_id,),
                dedupe_external_ref=observation.event_id,
            )
            binding = self._bindings[observation.observer_id]
            if self.security_graph.origin_binding(glyph.glyph_id) is None:
                self.security_graph.bind_origin(
                    glyph.glyph_id,
                    authority_class=binding.authority_class,
                    reason=(
                        "independent runtime observation admitted by "
                        f"SYN-REALITY observer {observation.observer_id}"
                    ),
                )
            self.graph.relate(
                glyph.glyph_id,
                action_glyph_id,
                "observes",
                actor=self.actor,
            )
            observation_glyphs.append(glyph)

        evaluations = []
        for observer_id in profile.required_observer_ids:
            assertions = tuple(
                a for a in profile.assertions if a.observer_id == observer_id
            )
            evaluations.append(
                self._evaluate_observer(
                    observer_id,
                    observations,
                    assertions,
                    proposal.parameters,
                )
            )

        statuses = {e.status for e in evaluations}
        if "contradicted" in statuses and "confirmed" in statuses:
            status = "observer_conflict"
            effect_observed = None
        elif "contradicted" in statuses:
            status = "contradicted"
            effect_observed = False
        elif statuses == {"confirmed"}:
            status = "confirmed"
            effect_observed = True
        else:
            status = "unverified"
            effect_observed = None

        claim_matches = (
            raw_result.success == effect_observed
            if effect_observed is not None
            else None
        )

        verdict_glyph = self.graph.create(
            "decision",
            actor=self.actor,
            content={
                "kind": "reality_verdict",
                "proposal_id": proposal.proposal_id,
                "action_type": proposal.action_type,
                "resource": resource,
                "status": status,
                "effect_observed": effect_observed,
                "executor_claim_success": raw_result.success,
                "executor_claim_matches_reality": claim_matches,
                "verification_required": profile.verification_required,
                "observer_evaluations": [asdict(e) for e in evaluations],
            },
            external_refs=(f"reality-verdict:{proposal.proposal_id}",),
            derived_from=(
                raw_glyph.glyph_id,
                *(g.glyph_id for g in observation_glyphs),
            ),
        )
        self.graph.relate(
            verdict_glyph.glyph_id,
            action_glyph_id,
            "evaluates",
            actor=self.actor,
        )

        effective = self._effective_result(
            raw_result=raw_result,
            status=status,
            effect_observed=effect_observed,
            claim_matches=claim_matches,
            verdict_id=verdict_glyph.glyph_id,
            verification_required=profile.verification_required,
        )
        effective_glyph = self.graph.create(
            "outcome",
            actor=self.actor,
            content={
                "kind": "reality_effective_outcome",
                "proposal_id": proposal.proposal_id,
                "action_type": effective.action_type,
                "success": effective.success,
                "output": dict(effective.output),
                "error": effective.error,
            },
            external_refs=(f"reality-outcome:{proposal.proposal_id}",),
            derived_from=(verdict_glyph.glyph_id,),
        )
        self.graph.relate(
            effective_glyph.glyph_id,
            action_glyph_id,
            "produces",
            actor=self.actor,
        )

        if claim_matches is False:
            critique = self.graph.create(
                "critique",
                actor=self.actor,
                content={
                    "kind": "executor_reality_mismatch",
                    "proposal_id": proposal.proposal_id,
                    "executor_claim_success": raw_result.success,
                    "effect_observed": effect_observed,
                },
                derived_from=(verdict_glyph.glyph_id, raw_glyph.glyph_id),
            )
            self.graph.relate(
                critique.glyph_id,
                raw_glyph.glyph_id,
                "critiques",
                actor=self.actor,
            )
            self.security_graph.mark_taint(
                raw_glyph.glyph_id,
                label="executor_claim_mismatch",
                reason="independent runtime observation contradicts executor claim",
            )

        return RealityAssessment(
            proposal_id=proposal.proposal_id,
            action_type=proposal.action_type,
            resource=resource,
            status=status,
            effect_observed=effect_observed,
            executor_claim_matches_reality=claim_matches,
            raw_result=raw_result,
            effective_result=effective,
            observer_evaluations=tuple(evaluations),
            observation_glyph_ids=tuple(g.glyph_id for g in observation_glyphs),
            executor_outcome_glyph_id=raw_glyph.glyph_id,
            verdict_glyph_id=verdict_glyph.glyph_id,
            effective_outcome_glyph_id=effective_glyph.glyph_id,
        )


class RealityAuditService:
    def __init__(self, graph: GlyphAuditGraph):
        self.graph = graph

    def verdict_glyphs(self) -> Tuple[Glyph, ...]:
        return tuple(
            g for g in self.graph.ledger.glyphs()
            if g.glyph_type == "decision"
            and g.content.get("kind") == "reality_verdict"
        )

    def reliability(self, action_type: str) -> RealityReliabilityReport:
        values = [
            g for g in self.verdict_glyphs()
            if g.content.get("action_type") == action_type
        ]
        verified = [
            g for g in values
            if g.content.get("effect_observed") is not None
        ]
        matches = [
            g for g in verified
            if g.content.get("executor_claim_matches_reality") is True
        ]
        mismatches = [
            g for g in verified
            if g.content.get("executor_claim_matches_reality") is False
        ]
        unresolved = [
            g for g in values
            if g.content.get("effect_observed") is None
        ]
        return RealityReliabilityReport(
            action_type=action_type,
            assessments=len(values),
            verified=len(verified),
            executor_claim_matches=len(matches),
            executor_claim_mismatches=len(mismatches),
            unverified_or_conflicted=len(unresolved),
            match_rate_on_verified=(
                len(matches) / len(verified) if verified else None
            ),
        )
