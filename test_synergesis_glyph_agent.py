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
    SynAgentLoop,
)
from synergesis_cognitive_core import SynCognitiveCore
from synergesis_context import ContextBudget, LexicalContextSelector
from synergesis_glyph_agent import SynGlyphAuditAdapter
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_life import PersistentMemory, SynKernel
from synergesis_research_layer import Aura


class Reasoner:
    def __init__(self, evidence_id=None, action_type="note.write"):
        self.evidence_id = evidence_id
        self.action_type = action_type

    def reason(self, context):
        refs = (self.evidence_id,) if self.evidence_id else ()
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "The observation deserves a note.",
                    evidence_ids=refs,
                    rationale="The current observation is relevant.",
                ),
            ),
            ActionProposal.create(
                self.action_type,
                {"text": "record"},
                rationale="Preserve the observation.",
                expected_outcome="A note is recorded.",
                strategy_key="record-observation",
                evidence_ids=refs,
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "The action succeeded." if result.success else "The action failed.",
        )


def build(tmp_path, *, evidence=False, allowed=("note.write",), action_type="note.write"):
    core = SynCognitiveCore(tmp_path / "semantic.jsonl")
    aura = Aura(core)
    evidence_id = None
    if evidence:
        ev = aura.research_ingest(
            "https://example.test/source",
            "Observed source",
            "Evidence body",
            "web",
        )
        evidence_id = ev.evidence_id

    kernel = SynKernel("ZÆL-0", PersistentMemory(tmp_path / "episodic.jsonl"))
    agent = SynAgentLoop(
        kernel=kernel,
        cognitive_core=core,
        aura=aura,
        policy=PermissionPolicy(frozenset(allowed)),
        reasoner=Reasoner(evidence_id=evidence_id, action_type=action_type),
        executors={
            "note.write": lambda params: ActionResult(
                "note.write", True, {"stored": True}
            )
        },
        strategy_ledger=StrategyLedger(tmp_path / "strategy.jsonl"),
        context_selector=LexicalContextSelector(
            budget=ContextBudget(max_facts=8, max_evidence=8),
            k1=1.5,
            b=0.75,
        ),
    )
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    return SynGlyphAuditAdapter(agent=agent, graph=graph), graph, evidence_id


def test_successful_cycle_has_complete_audit_chain(tmp_path):
    audited, graph, _ = build(tmp_path, evidence=True)
    recorded = audited.run_cycle(
        goal=Goal.create("Record relevant observations"),
        observation=AgentObservation("text", {"text": "signal"}, "sensor"),
    )

    assert recorded.action_glyph_id is not None
    assert recorded.policy_glyph_id is not None
    assert recorded.outcome_glyph_id is not None
    assert recorded.learning_glyph_id is not None

    trace = graph.explain_decision(recorded.decision_glyph_id)
    types = {g.glyph_type for g in trace.glyphs}
    assert {"goal", "observation", "hypothesis", "decision", "evidence"} <= types

    checkpoint = graph.ledger.verify()
    assert checkpoint.event_count > 0


def test_denied_action_is_audited_without_fake_outcome(tmp_path):
    audited, graph, _ = build(
        tmp_path,
        allowed=("note.write",),
        action_type="system.admin",
    )
    recorded = audited.run_cycle(
        goal=Goal.create("Respect permissions"),
        observation=AgentObservation("event", {"x": 1}, "test"),
    )
    assert recorded.policy_glyph_id is not None
    assert recorded.outcome_glyph_id is None
    assert recorded.learning_glyph_id is None

    policy = graph.ledger.get(recorded.policy_glyph_id)
    assert policy.content["allowed"] is False


def test_invalidated_evidence_can_find_impacted_decision(tmp_path):
    audited, graph, evidence_id = build(tmp_path, evidence=True)
    recorded = audited.run_cycle(
        goal=Goal.create("Use evidence"),
        observation=AgentObservation("text", {"text": "signal"}, "sensor"),
    )
    evidence_glyph = graph.ledger.find_by_external_ref(
        evidence_id,
        glyph_type="evidence",
    )[0]
    impact = graph.impacted_by(evidence_glyph.glyph_id)
    impacted_ids = {g.glyph_id for g in impact.glyphs}
    assert recorded.decision_glyph_id in impacted_ids
    assert recorded.action_glyph_id in impacted_ids


def test_audit_does_not_claim_private_chain_of_thought(tmp_path):
    audited, graph, _ = build(tmp_path)
    audited.run_cycle(
        goal=Goal.create("Audit observable transitions"),
        observation=AgentObservation("event", {"x": 2}, "test"),
    )
    raw = (tmp_path / "glyphs.jsonl").read_text(encoding="utf-8").casefold()
    assert "chain_of_thought" not in raw
    assert "private_reasoning" not in raw


def test_goal_glyph_is_reused_across_cycles(tmp_path):
    audited, graph, _ = build(tmp_path)
    goal = Goal.create("Persistent objective")
    audited.run_cycle(
        goal=goal,
        observation=AgentObservation("event", {"x": 1}, "test"),
    )
    audited.run_cycle(
        goal=goal,
        observation=AgentObservation("event", {"x": 2}, "test"),
    )
    goals = graph.ledger.find_by_external_ref(goal.goal_id, glyph_type="goal")
    assert len(goals) == 1


def test_evidence_content_is_not_duplicated_into_audit_graph(tmp_path):
    audited, graph, evidence_id = build(tmp_path, evidence=True)
    audited.run_cycle(
        goal=Goal.create("Minimize duplicated sensitive content"),
        observation=AgentObservation("event", {"x": 1}, "test"),
    )
    ev = graph.ledger.find_by_external_ref(evidence_id, glyph_type="evidence")[0]
    assert ev.content["content_digest_only"] is True
    assert "Evidence body" not in str(ev.content)
