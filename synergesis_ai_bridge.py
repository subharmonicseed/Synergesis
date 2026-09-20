"""Strict AI-model bridge for the Synergesis bounded agent loop.

A language model is treated as an untrusted reasoning component:
- it may propose hypotheses and actions;
- it cannot execute actions;
- it cannot mutate permissions;
- its structured output is validated before entering SynAgentLoop.

No provider SDK is hard-coded here. A backend only needs to implement the
ModelBackend protocol, allowing local or remote models to be connected later.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Protocol, Sequence

from synergesis_agent_loop import (
    ActionProposal,
    ActionResult,
    AgentContext,
    Hypothesis,
    LearningSignal,
    ReasoningOutput,
)


class ModelBackend(Protocol):
    def complete(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


def _require_exact_keys(
    value: Mapping[str, Any],
    required: set[str],
    *,
    label: str,
) -> None:
    keys = set(value.keys())
    missing = sorted(required - keys)
    extra = sorted(keys - required)
    if missing:
        raise ValueError(f"{label} missing fields: {missing}")
    if extra:
        raise ValueError(f"{label} unexpected fields: {extra}")


def _as_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _as_string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    out = []
    for item in value:
        out.append(_as_string(item, label))
    return tuple(out)


class SynAIReasoner:
    """ReasoningProvider backed by a strictly validated model backend."""

    def __init__(self, backend: ModelBackend):
        self.backend = backend

    @staticmethod
    def _context_payload(context: AgentContext) -> dict[str, Any]:
        return {
            "goal": asdict(context.goal),
            "observation": {
                "kind": context.observation.kind,
                "payload": dict(context.observation.payload),
                "source": context.observation.source,
            },
            "facts": [asdict(f) for f in context.facts],
            "evidence": [asdict(e) for e in context.evidence],
            "gaps": list(context.gaps),
            "known_evidence_ids": list(context.known_evidence_ids),
            "contract": {
                "hypotheses_are_not_facts": True,
                "actions_are_proposals_only": True,
                "unknown_evidence_ids_are_invalid": True,
                "permission_changes_are_not_available": True,
            },
        }

    def reason(self, context: AgentContext) -> ReasoningOutput:
        raw = self.backend.complete("reason", self._context_payload(context))
        if not isinstance(raw, Mapping):
            raise TypeError("model reason output must be an object")
        _require_exact_keys(raw, {"hypotheses", "action"}, label="reason output")

        raw_hypotheses = raw["hypotheses"]
        if not isinstance(raw_hypotheses, list):
            raise ValueError("hypotheses must be a list")

        hypotheses = []
        for index, item in enumerate(raw_hypotheses):
            if not isinstance(item, Mapping):
                raise ValueError(f"hypotheses[{index}] must be an object")
            _require_exact_keys(
                item,
                {"statement", "evidence_ids", "rationale"},
                label=f"hypotheses[{index}]",
            )
            hypotheses.append(
                Hypothesis.create(
                    _as_string(item["statement"], f"hypotheses[{index}].statement"),
                    evidence_ids=_as_string_tuple(
                        item["evidence_ids"], f"hypotheses[{index}].evidence_ids"
                    ),
                    rationale=_as_string(
                        item["rationale"], f"hypotheses[{index}].rationale"
                    ),
                )
            )

        raw_action = raw["action"]
        action = None
        if raw_action is not None:
            if not isinstance(raw_action, Mapping):
                raise ValueError("action must be an object or null")
            _require_exact_keys(
                raw_action,
                {
                    "action_type",
                    "parameters",
                    "rationale",
                    "expected_outcome",
                    "strategy_key",
                    "evidence_ids",
                },
                label="action",
            )
            if not isinstance(raw_action["parameters"], Mapping):
                raise ValueError("action.parameters must be an object")
            action = ActionProposal.create(
                _as_string(raw_action["action_type"], "action.action_type"),
                dict(raw_action["parameters"]),
                rationale=_as_string(raw_action["rationale"], "action.rationale"),
                expected_outcome=_as_string(
                    raw_action["expected_outcome"], "action.expected_outcome"
                ),
                strategy_key=_as_string(
                    raw_action["strategy_key"], "action.strategy_key"
                ),
                evidence_ids=_as_string_tuple(
                    raw_action["evidence_ids"], "action.evidence_ids"
                ),
            )

        return ReasoningOutput(tuple(hypotheses), action)

    def evaluate(
        self,
        context: AgentContext,
        proposal: ActionProposal,
        result: ActionResult,
    ) -> LearningSignal:
        payload = {
            "context": self._context_payload(context),
            "proposal": asdict(proposal),
            "result": asdict(result),
            "contract": {
                "score_range": [0.0, 1.0],
                "evaluation_cannot_change_permissions": True,
            },
        }
        raw = self.backend.complete("evaluate", payload)
        if not isinstance(raw, Mapping):
            raise TypeError("model evaluation output must be an object")
        _require_exact_keys(raw, {"score", "lesson"}, label="evaluation output")
        score = raw["score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("evaluation score must be numeric")
        lesson = _as_string(raw["lesson"], "evaluation.lesson")
        return LearningSignal(float(score), lesson)
