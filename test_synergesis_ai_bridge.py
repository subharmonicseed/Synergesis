import pytest

from synergesis_ai_bridge import SynAIReasoner
from synergesis_agent_loop import (
    ActionResult,
    AgentContext,
    AgentObservation,
    Goal,
)
from synergesis_cognitive_core import Fact


class FixedBackend:
    def __init__(self, reason_output, evaluate_output=None):
        self.reason_output = reason_output
        self.evaluate_output = evaluate_output or {
            "score": 1.0,
            "lesson": "Observed outcome matched the expectation.",
        }
        self.calls = []

    def complete(self, operation, payload):
        self.calls.append((operation, payload))
        if operation == "reason":
            return self.reason_output
        if operation == "evaluate":
            return self.evaluate_output
        raise AssertionError(operation)


def context():
    return AgentContext(
        goal=Goal.create("Keep a verified note"),
        observation=AgentObservation("text", {"text": "signal"}, "sensor"),
        facts=(),
        gaps=("verified",),
        evidence=(Fact(
            subject="evidence",
            predicate="reference",
            object="ev-1",
            source="test",
            confidence=1.0,
            observed_at="2026-01-01T00:00:00+00:00",
            evidence_id="ev-1",
        ),),
    )


def valid_reason_output(action_type="note.write"):
    return {
        "hypotheses": [
            {
                "statement": "The signal may matter.",
                "evidence_ids": ["ev-1"],
                "rationale": "It is supported by the referenced evidence.",
            }
        ],
        "action": {
            "action_type": action_type,
            "parameters": {"text": "signal"},
            "rationale": "Preserve the observation.",
            "expected_outcome": "The note is stored.",
            "strategy_key": "store-signal",
            "evidence_ids": ["ev-1"],
        },
    }


def test_valid_model_output_becomes_proposals_only():
    backend = FixedBackend(valid_reason_output())
    reasoner = SynAIReasoner(backend)
    output = reasoner.reason(context())
    assert len(output.hypotheses) == 1
    assert output.action.action_type == "note.write"
    assert backend.calls[0][0] == "reason"


def test_extra_fields_are_rejected():
    raw = valid_reason_output()
    raw["self_grant"] = "system.admin"
    reasoner = SynAIReasoner(FixedBackend(raw))
    with pytest.raises(ValueError, match="unexpected fields"):
        reasoner.reason(context())


def test_missing_required_action_field_is_rejected():
    raw = valid_reason_output()
    del raw["action"]["strategy_key"]
    reasoner = SynAIReasoner(FixedBackend(raw))
    with pytest.raises(ValueError, match="missing fields"):
        reasoner.reason(context())


def test_unknown_action_name_is_not_filtered_by_bridge():
    # The bridge validates structure, while PermissionPolicy decides authorization.
    reasoner = SynAIReasoner(FixedBackend(valid_reason_output("system.admin")))
    output = reasoner.reason(context())
    assert output.action.action_type == "system.admin"


def test_evaluation_is_bounded_by_learning_signal():
    backend = FixedBackend(
        valid_reason_output(),
        {"score": 1.5, "lesson": "invalid range"},
    )
    reasoner = SynAIReasoner(backend)
    proposal = reasoner.reason(context()).action
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        reasoner.evaluate(
            context(),
            proposal,
            ActionResult("note.write", True, {"stored": True}),
        )


def test_contract_exposes_no_permission_mutation_surface():
    backend = FixedBackend(valid_reason_output())
    reasoner = SynAIReasoner(backend)
    reasoner.reason(context())
    payload = backend.calls[0][1]
    assert payload["contract"]["permission_changes_are_not_available"] is True
    assert "policy" not in payload
