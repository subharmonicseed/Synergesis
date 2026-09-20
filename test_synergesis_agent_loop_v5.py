from pathlib import Path

import pytest

from synergesis_aegis import (
    ActionSecurityProfile,
    AegisGuard,
    AegisSecurityGraph,
    CapabilityStore,
    IdentityRegistry,
    IdentitySigner,
)
from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentObservation,
    Goal,
    Hypothesis,
    LearningSignal,
    PermissionPolicy,
    ReasoningOutput,
    StrategyLedger,
)
from synergesis_agent_loop_v4 import (
    ActionTypeResourceResolver,
    NoCapabilities,
    TrustedSourceObservationClassifier,
)
from synergesis_agent_loop_v5 import SynAgentLoopV5
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_life import PersistentMemory, SynKernel
from synergesis_reality import (
    FileStateProbe,
    RealityAssertion,
    RealityProbeBinding,
    RealityProfile,
    RealityVerifier,
)
from synergesis_prediction import (
    PredictionEngine,
    PredictionLedger,
    StaticPredictionProvider,
)


class FileReasoner:
    def __init__(self, *, path="out.txt", content="hello"):
        self.path = path
        self.content = content

    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "Write the requested file.",
                    rationale="test",
                ),
            ),
            ActionProposal.create(
                "file.write",
                {"path": self.path, "content": self.content},
                rationale="write file",
                expected_outcome="file exists with content",
                strategy_key="file-write",
            ),
        )

    def evaluate(self, context, proposal, result):
        # Deliberately optimistic: V5 must suppress this when reality disagrees.
        return LearningSignal(0.95, "Executor outcome looks useful.")


def build(tmp_path, executor, *, prediction_probability=None):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    kernel = SynKernel(
        "ZÆL-0",
        PersistentMemory(tmp_path / "episodic.jsonl"),
    )

    identities = IdentityRegistry(tmp_path / "identities.jsonl")
    syn_signer = IdentitySigner("ZÆL-0")
    identities.register("ZÆL-0", syn_signer.public_key)

    security = AegisSecurityGraph(graph)
    aegis = AegisGuard(
        graph=graph,
        identity_registry=identities,
        capability_store=CapabilityStore(tmp_path / "caps.jsonl"),
        trusted_capability_issuers=frozenset(),
        allowed_actions=frozenset({"file.write"}),
        profiles=(
            ActionSecurityProfile(
                "file.write",
                requires_capability=False,
                forbidden_taints=frozenset(),
            ),
        ),
        security_graph=security,
    )

    probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=tmp_path / "runtime",
        path_parameter="path",
        max_hash_bytes=1024 * 1024,
    )
    reality = RealityVerifier(
        graph=graph,
        security_graph=security,
        probe_bindings=(
            RealityProbeBinding(
                "os:file",
                "runtime_attested",
                probe,
            ),
        ),
        profiles=(
            RealityProfile(
                "file.write",
                ("os:file",),
                (
                    RealityAssertion("os:file", "exists", "eq", True),
                    RealityAssertion(
                        "os:file",
                        "sha256",
                        "sha256_parameter_utf8",
                        parameter_key="content",
                    ),
                ),
            ),
        ),
    )

    prediction_engine = None
    if prediction_probability is not None:
        prediction_engine = PredictionEngine(
            graph=graph,
            provider=StaticPredictionProvider(prediction_probability),
            ledger=PredictionLedger(tmp_path / "prediction.jsonl"),
        )

    loop = SynAgentLoopV5(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(frozenset({"file.write"})),
        reasoner=FileReasoner(),
        executors={"file.write": executor(probe.allowed_root)},
        strategy_ledger=StrategyLedger(tmp_path / "strategy.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
        graph=graph,
        aegis_guard=aegis,
        observation_classifier=TrustedSourceObservationClassifier(
            trusted_sources=frozenset({"user"})
        ),
        capability_resolver=NoCapabilities(),
        resource_resolver=ActionTypeResourceResolver(),
        reality_verifier=reality,
        prediction_engine=prediction_engine,
    )
    return loop, graph, security, probe


def honest_executor(root):
    def execute(params):
        target = root / params["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(params["content"], encoding="utf-8")
        return ActionResult("file.write", True, {"path": str(target)})
    return execute


def lying_success_executor(root):
    def execute(params):
        return ActionResult("file.write", True, {"claimed": "written"})
    return execute


def failure_but_side_effect_executor(root):
    def execute(params):
        target = root / params["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(params["content"], encoding="utf-8")
        return ActionResult(
            "file.write",
            False,
            {"claimed": "failed"},
            "timeout",
        )
    return execute


def run(loop):
    return loop.run_cycle(
        goal=Goal.create("Write a test file"),
        observation=AgentObservation(
            "request",
            {"text": "write file"},
            "user",
        ),
    )


def test_v5_honest_executor_learns_from_verified_result(tmp_path):
    loop, graph, security, probe = build(tmp_path, honest_executor)
    cycle = run(loop)
    assert cycle.policy.allowed is True
    assert cycle.action_result.success is True
    assert cycle.action_result.output["reality"]["status"] == "confirmed"
    assert cycle.learning.score == pytest.approx(0.95)
    assert (probe.allowed_root / "out.txt").read_text() == "hello"


def test_v5_false_success_is_corrected_before_learning(tmp_path):
    loop, graph, security, probe = build(tmp_path, lying_success_executor)
    cycle = run(loop)
    assert cycle.policy.allowed is True
    assert cycle.action_result.success is False
    assert cycle.action_result.output["executor_claim"]["success"] is True
    assert cycle.action_result.output["reality"]["status"] == "contradicted"
    assert cycle.learning.score == 0.0
    assert "invalidated executor-derived learning" in cycle.learning.lesson


def test_v5_side_effect_despite_executor_failure_is_visible_but_not_rewarded(tmp_path):
    loop, graph, security, probe = build(
        tmp_path,
        failure_but_side_effect_executor,
    )
    cycle = run(loop)
    assert cycle.action_result.success is True
    assert cycle.action_result.output["executor_claim"]["success"] is False
    assert cycle.action_result.output["reality"]["status"] == "confirmed"
    assert cycle.learning.score == 0.0


def test_strategy_ledger_uses_reality_effective_success(tmp_path):
    loop, graph, security, probe = build(tmp_path, lying_success_executor)
    cycle = run(loop)
    stats = loop.strategy_ledger.stats("file-write")
    assert stats.observations == 1
    assert stats.successes == 0
    assert stats.success_rate == 0.0
    assert stats.mean_score == 0.0


def test_reality_verdict_is_linked_to_action_in_glyph_graph(tmp_path):
    loop, graph, security, probe = build(tmp_path, honest_executor)
    cycle = run(loop)
    verdicts = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "decision"
        and g.content.get("kind") == "reality_verdict"
    ]
    assert len(verdicts) == 1
    action = graph.ledger.find_by_external_ref(
        cycle.proposal.proposal_id,
        glyph_type="action",
    )[-1]
    edges = graph.ledger.edges()
    assert any(
        e.source == verdicts[0].glyph_id
        and e.target == action.glyph_id
        and e.relation == "evaluates"
        for e in edges
    )


def test_v5_requires_reality_profile_for_every_allowed_action(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    core = GlyphAuditedCognitiveCore(
        tmp_path / "semantic.jsonl",
        graph=graph,
        actor="ZÆL-0",
    )
    aura = GlyphAuditedAura(core, graph=graph)
    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))
    identities = IdentityRegistry(tmp_path / "ids.jsonl")
    signer = IdentitySigner("ZÆL-0")
    identities.register("ZÆL-0", signer.public_key)
    security = AegisSecurityGraph(graph)
    aegis = AegisGuard(
        graph=graph,
        identity_registry=identities,
        capability_store=CapabilityStore(tmp_path / "caps.jsonl"),
        trusted_capability_issuers=frozenset(),
        allowed_actions=frozenset({"file.write"}),
        profiles=(
            ActionSecurityProfile("file.write", False, frozenset()),
        ),
        security_graph=security,
    )
    empty_reality = RealityVerifier(
        graph=graph,
        security_graph=security,
        probe_bindings=(),
        profiles=(),
    )

    with pytest.raises(ValueError, match="missing SYN-REALITY profiles"):
        SynAgentLoopV5(
            kernel=kernel,
            cognitive_core=core,
            aura=aura,
            policy=PermissionPolicy(frozenset({"file.write"})),
            reasoner=FileReasoner(),
            executors={},
            strategy_ledger=StrategyLedger(tmp_path / "strategy.jsonl"),
            context_selector=LexicalContextSelector(
                budget=ContextBudget(8, 8),
                k1=1.5,
                b=0.75,
            ),
            graph=graph,
            aegis_guard=aegis,
            observation_classifier=TrustedSourceObservationClassifier(
                trusted_sources=frozenset({"user"})
            ),
            capability_resolver=NoCapabilities(),
            resource_resolver=ActionTypeResourceResolver(),
            reality_verifier=empty_reality,
        )


def test_v5_prediction_is_recorded_before_executor_claim_and_scored_after_reality(tmp_path):
    loop, graph, security, probe = build(
        tmp_path,
        honest_executor,
        prediction_probability=0.8,
    )
    cycle = run(loop)

    predictions = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "hypothesis"
        and g.content.get("kind") == "action_prediction"
    ]
    claims = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "outcome"
        and g.content.get("kind") == "executor_claim"
    ]
    errors = [
        g for g in graph.ledger.glyphs()
        if g.glyph_type == "learning"
        and g.content.get("kind") == "prediction_error"
    ]
    assert len(predictions) == len(claims) == len(errors) == 1

    events = graph.ledger.events()
    sequence_by_glyph = {
        event.payload["glyph_id"]: event.sequence
        for event in events
        if event.event_type == "glyph"
    }
    assert sequence_by_glyph[predictions[0].glyph_id] < sequence_by_glyph[claims[0].glyph_id]
    assert sequence_by_glyph[claims[0].glyph_id] < sequence_by_glyph[errors[0].glyph_id]
    assert errors[0].content["brier_score"] == pytest.approx(0.04)
    assert "Prediction calibration" in cycle.learning.lesson


def test_v5_prediction_error_does_not_replace_outcome_learning_score(tmp_path):
    loop, graph, security, probe = build(
        tmp_path,
        honest_executor,
        prediction_probability=0.1,
    )
    cycle = run(loop)
    assert cycle.action_result.success is True
    assert cycle.learning.score == pytest.approx(0.95)

    settlement = loop._prediction_by_proposal[cycle.proposal.proposal_id]
    assert settlement.brier_score == pytest.approx(0.81)
    assert settlement.absolute_error == pytest.approx(0.9)
