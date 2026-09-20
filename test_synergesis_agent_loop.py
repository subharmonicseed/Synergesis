from pathlib import Path

import pytest

from synergesis_agent_loop import (
    ActionProposal,
    ActionResult,
    AgentObservation,
    Goal,
    Hypothesis,
    LearningSignal,
    PermissionPolicy,
    ReasoningOutput,
    StrategyLedger,
    SynAgentLoop,
)
from synergesis_cognitive_core import SynCognitiveCore
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_life import PersistentMemory, SynKernel
from synergesis_research_layer import Aura


class DeterministicReasoner:
    def __init__(self, action_type="note.write", evidence_ids=()):
        self.action_type = action_type
        self.evidence_ids = tuple(evidence_ids)

    def reason(self, context):
        h = Hypothesis.create(
            "The observation may be relevant to the current goal.",
            evidence_ids=self.evidence_ids,
            rationale="It is explicitly related to the supplied observation.",
        )
        proposal = ActionProposal.create(
            self.action_type,
            {"text": "record observation"},
            rationale="Persist a concise operational note.",
            expected_outcome="A note is recorded.",
            strategy_key="record-relevant-observation",
            evidence_ids=self.evidence_ids,
        )
        return ReasoningOutput((h,), proposal)

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "The strategy succeeded." if result.success else "The strategy failed.",
        )


class NoActionReasoner:
    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "More information is required.",
                    rationale="The current observation is insufficient for action.",
                ),
            ),
            None,
        )

    def evaluate(self, context, proposal, result):
        raise AssertionError("evaluate must not run when there is no action")


def build_loop(tmp_path: Path, reasoner, policy_actions=("note.write",), executors=None):
    core = SynCognitiveCore(tmp_path / "semantic.jsonl")
    aura = Aura(core)
    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))
    policy = PermissionPolicy(frozenset(policy_actions))
    ledger = StrategyLedger(tmp_path / "strategies.jsonl")
    return SynAgentLoop(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=policy,
        reasoner=reasoner,
        executors=executors or {},
        strategy_ledger=ledger,
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
    )


def successful_note_executor(params):
    assert params["text"] == "record observation"
    return ActionResult("note.write", True, {"stored": True})


def test_allowed_action_executes_and_learns(tmp_path):
    loop = build_loop(
        tmp_path,
        DeterministicReasoner(),
        executors={"note.write": successful_note_executor},
    )
    result = loop.run_cycle(
        goal=Goal.create("Track relevant observations"),
        observation=AgentObservation("text", {"text": "signal"}, "sensor"),
    )
    assert result.policy.allowed is True
    assert result.action_result.success is True
    assert result.learning.score == 1.0
    assert result.strategy_stats.observations == 1
    assert result.strategy_stats.success_rate == 1.0
    assert result.cognitive_cycle == 1
    assert result.reflexive_cycle == 1


def test_denied_action_never_reaches_executor(tmp_path):
    called = {"value": False}

    def executor(params):
        called["value"] = True
        return ActionResult("system.admin", True, {})

    loop = build_loop(
        tmp_path,
        DeterministicReasoner(action_type="system.admin"),
        policy_actions=("note.write",),
        executors={"system.admin": executor},
    )
    result = loop.run_cycle(
        goal=Goal.create("Respect permission boundaries"),
        observation=AgentObservation("event", {"x": 1}, "test"),
    )
    assert result.policy.allowed is False
    assert result.policy.reason == "action_type_not_allowlisted"
    assert result.action_result is None
    assert result.learning is None
    assert called["value"] is False


def test_learning_cannot_expand_permissions(tmp_path):
    loop = build_loop(
        tmp_path,
        DeterministicReasoner(),
        executors={"note.write": successful_note_executor},
    )
    before = loop.policy.allowed_actions
    loop.run_cycle(
        goal=Goal.create("Learn bounded strategies"),
        observation=AgentObservation("event", {"x": 2}, "test"),
    )
    assert loop.policy.allowed_actions == before
    assert "system.admin" not in loop.policy.allowed_actions


def test_missing_executor_is_explicit_failure_and_is_learned(tmp_path):
    loop = build_loop(tmp_path, DeterministicReasoner(), executors={})
    result = loop.run_cycle(
        goal=Goal.create("Record a note"),
        observation=AgentObservation("event", {"x": 3}, "test"),
    )
    assert result.policy.allowed is True
    assert result.action_result.success is False
    assert result.action_result.error == "no_executor_registered"
    assert result.strategy_stats.observations == 1
    assert result.strategy_stats.success_rate == 0.0


def test_hypotheses_do_not_become_semantic_facts_automatically(tmp_path):
    loop = build_loop(tmp_path, NoActionReasoner())
    result = loop.run_cycle(
        goal=Goal.create("Avoid fabricating facts"),
        observation=AgentObservation("text", {"text": "uncertain"}, "sensor"),
    )
    assert len(result.hypotheses) == 1
    assert loop.core.memory.count() == 0
    assert result.proposal is None


def test_unknown_evidence_reference_is_rejected(tmp_path):
    loop = build_loop(
        tmp_path,
        DeterministicReasoner(evidence_ids=("not-known",)),
        executors={"note.write": successful_note_executor},
    )
    with pytest.raises(ValueError, match="unknown evidence ids"):
        loop.run_cycle(
            goal=Goal.create("Use only known evidence"),
            observation=AgentObservation("text", {"text": "x"}, "sensor"),
        )


def test_known_evidence_reference_is_accepted(tmp_path):
    core = SynCognitiveCore(tmp_path / "semantic.jsonl")
    aura = Aura(core)
    evidence = aura.research_ingest(
        "https://example.test/source",
        "Source",
        "Observed material",
        "web",
    )
    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))
    loop = SynAgentLoop(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(frozenset({"note.write"})),
        reasoner=DeterministicReasoner(evidence_ids=(evidence.evidence_id,)),
        executors={"note.write": successful_note_executor},
        strategy_ledger=StrategyLedger(tmp_path / "strategies.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
    )
    result = loop.run_cycle(
        goal=Goal.create("Use sourced evidence"),
        observation=AgentObservation("text", {"text": "x"}, "sensor"),
    )
    assert result.action_result.success is True


def test_learning_score_is_bounded():
    with pytest.raises(ValueError):
        LearningSignal(1.01, "invalid")


def test_no_action_cycle_still_reflects(tmp_path):
    loop = build_loop(tmp_path, NoActionReasoner())
    result = loop.run_cycle(
        goal=Goal.create("Observe only"),
        observation=AgentObservation("sensor", {"value": 4}, "device"),
    )
    assert result.policy is None
    assert result.action_result is None
    assert result.cognitive_cycle == 1
    assert result.reflexive_cycle == 1
    assert result.memory_count > 0
