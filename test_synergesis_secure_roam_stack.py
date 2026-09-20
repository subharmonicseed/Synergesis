from dataclasses import dataclass

import pytest

from synergesis_aegis import (
    ActionSecurityProfile,
    CapabilityStore,
    IdentityRegistry,
)
from synergesis_agent_loop_v2 import (
    ActionProposal,
    ActionResult,
    AgentObservation,
    Goal,
    Hypothesis,
    LearningSignal,
    ReasoningOutput,
)
from synergesis_agent_loop_v4 import (
    ActionTypeResourceResolver,
    NoCapabilities,
    TrustedSourceObservationClassifier,
)
from synergesis_planner import PlanDraft, PlanStepDraft, StepAssessment
from synergesis_roam import (
    RetrievedItem,
    RoamLimits,
    SearchStep,
    SelectionConfig,
    SourcePolicy,
    SourceRegistry,
    UtilityWeights,
    make_method,
)
from synergesis_roam_attention import (
    AttentionMeasurements,
    AttentionWeights,
    ResearchNeed,
)
from synergesis_roam_evolution import EvolutionPolicy
from synergesis_roam_service import RoamServiceLimits
from synergesis_secure_roam_stack import (
    SecureRoamConfig,
    build_secure_roam_stack,
)


class Adapter:
    def __init__(self):
        self.calls = 0

    def search(self, *, query, max_items):
        self.calls += 1
        return (
            RetrievedItem(
                "https://example.test/paper",
                "Danger signal paper",
                "danger signal evidence",
                "mock_web",
                0.1,
            ),
        )[:max_items]


class Reasoner:
    def reason(self, context):
        evidence_ids = (
            (context.evidence[0].evidence_id,)
            if context.evidence
            else ()
        )
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "The signal may justify a note.",
                    evidence_ids=evidence_ids,
                    rationale="Use selected evidence if present.",
                ),
            ),
            ActionProposal.create(
                "note.write",
                {"text": "danger signal"},
                rationale="Record the signal.",
                expected_outcome="A note is written.",
                strategy_key="secure-roam-note",
                evidence_ids=evidence_ids,
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            1.0 if result.success else 0.0,
            "Observed executor result.",
        )


class Planner:
    def create_plan(self, context):
        return PlanDraft(
            rationale="One bounded step.",
            steps=(
                PlanStepDraft(
                    "Record signal",
                    "note.write succeeds",
                    "note.write",
                ),
            ),
        )

    def assess_step(self, context, step, cycle):
        return StepAssessment(
            "completed" if cycle.action_result and cycle.action_result.success else "blocked",
            "Use observed executor result.",
            1.0,
        )

    def replan(self, context, previous_plan, failed_step, assessment):
        return PlanDraft(
            rationale="Replacement.",
            steps=(
                PlanStepDraft(
                    "Replacement",
                    "note.write succeeds",
                    "note.write",
                ),
            ),
        )


def config(tmp_path):
    return SecureRoamConfig(
        root=tmp_path / "syn",
        identity="ZÆL-0",
        allowed_actions=frozenset({"note.write"}),
        context_max_facts=8,
        context_max_evidence=8,
        bm25_k1=1.5,
        bm25_b=0.75,
        max_steps_per_plan=4,
        max_replans=1,
        max_attempts_per_step=2,
        roam_limits=RoamLimits(
            max_steps_per_session=3,
            max_items_per_session=5,
            max_budget_units=5.0,
        ),
        selection_config=SelectionConfig(
            exploration_strength=0.0,
            require_counter_search_for_hypothesis=True,
        ),
        utility_weights=UtilityWeights(
            verified_yield=1.0,
            novelty_yield=1.0,
            contradiction_yield=1.0,
            calibration_gain=1.0,
            predictive_value=1.0,
            redundancy_penalty=1.0,
            cost_penalty=1.0,
        ),
        attention_weights=AttentionWeights(
            uncertainty=1.0,
            expected_impact=1.0,
            staleness=1.0,
            novelty_gap=1.0,
        ),
        service_limits=RoamServiceLimits(
            max_ticks_per_batch=2,
            stop_when_idle=True,
        ),
        evolution_policy=EvolutionPolicy(
            max_steps_per_method=3,
            min_trials_per_method=1,
            promotion_margin=0.1,
            require_counter_search=True,
        ),
    )


def source_setup():
    registry = SourceRegistry()
    registry.register(
        SourcePolicy(
            source_id="mock",
            source_type="mock_web",
            domains=("science",),
            max_items_per_query=2,
            external_untrusted=True,
        )
    )
    method = make_method(
        name="skeptical mock search",
        domain="science",
        created_by="test",
        steps=(
            SearchStep(
                "mock",
                "challenge",
                "{question} {hypothesis}",
                1,
            ),
        ),
    )
    adapter = Adapter()
    return registry, method, adapter


def build(tmp_path, *, profiles=True, include_adapter=True):
    registry, method, adapter = source_setup()
    called = {"count": 0}

    def executor(params):
        called["count"] += 1
        return ActionResult("note.write", True, {"stored": True})

    profile_values = (
        (
            ActionSecurityProfile(
                "note.write",
                requires_capability=False,
                forbidden_taints=frozenset({"external_untrusted"}),
            ),
        )
        if profiles
        else ()
    )
    adapters = {"mock": adapter} if include_adapter else {}

    stack = build_secure_roam_stack(
        config=config(tmp_path),
        reasoner=Reasoner(),
        planning_provider=Planner(),
        executors={"note.write": executor},
        identity_registry=IdentityRegistry(tmp_path / "identities.jsonl"),
        capability_store=CapabilityStore(tmp_path / "capabilities.jsonl"),
        trusted_capability_issuers=frozenset(),
        action_security_profiles=profile_values,
        observation_classifier=TrustedSourceObservationClassifier(
            trusted_sources=frozenset({"user"})
        ),
        capability_resolver=NoCapabilities(),
        resource_resolver=ActionTypeResourceResolver(),
        source_registry=registry,
        source_adapters=adapters,
        research_methods=(method,),
    )
    return stack, adapter, called


def test_secure_roam_stack_wires_all_major_subsystems(tmp_path):
    stack, adapter, called = build(tmp_path)
    assert stack.graph is stack.security_graph.graph
    assert stack.agent.graph is stack.graph
    assert stack.roam_runtime.graph is stack.graph
    assert stack.roam_runtime.aura is stack.aura
    assert stack.planner.runtime.agent.agent is stack.agent
    assert stack.goals.manager.runtime is stack.planner


def test_roaming_evidence_is_tainted_then_blocks_sensitive_agent_action(tmp_path):
    stack, adapter, called = build(tmp_path)

    need = ResearchNeed.create(
        domain="science",
        question="danger signal",
        hypothesis="danger signal is important",
        reason="test live roaming lineage",
        measurements=AttentionMeasurements(
            uncertainty=1.0,
            expected_impact=1.0,
            staleness=0.5,
            novelty_gap=1.0,
        ),
    )
    stack.agenda.add(need)
    ticks = stack.service.run_bounded()
    assert ticks[0].status == "researched"
    assert adapter.calls == 1

    evidence = stack.aura.research.store.all()[0]
    evidence_glyph = stack.graph.ledger.find_by_external_ref(
        evidence.evidence_id,
        glyph_type="evidence",
    )[-1]
    assert "external_untrusted" in stack.security_graph.active_taints(
        evidence_glyph.glyph_id
    )

    recorded = stack.agent_audit.run_cycle(
        goal=Goal.create("danger signal"),
        observation=AgentObservation(
            "text",
            {"text": "danger signal"},
            "user",
        ),
    )
    assert recorded.cycle.policy.allowed is False
    assert "forbidden_taint" in recorded.cycle.policy.reason
    assert called["count"] == 0


def test_stack_refuses_global_action_without_aegis_profile(tmp_path):
    with pytest.raises(ValueError, match="requires an AEGIS profile"):
        build(tmp_path, profiles=False)


def test_stack_refuses_enabled_source_without_adapter(tmp_path):
    with pytest.raises(ValueError, match="missing adapters"):
        build(tmp_path, include_adapter=False)


def test_roam_and_agent_share_single_tamper_evident_glyph_history(tmp_path):
    stack, adapter, called = build(tmp_path)
    stack.agenda.add(
        ResearchNeed.create(
            domain="science",
            question="danger signal",
            hypothesis="H",
            reason="test",
            measurements=AttentionMeasurements(1.0, 1.0, 1.0, 1.0),
        )
    )
    stack.service.run_bounded()
    stack.agent_audit.run_cycle(
        goal=Goal.create("danger signal"),
        observation=AgentObservation("text", {"text": "danger signal"}, "user"),
    )
    checkpoint = stack.graph.ledger.verify()
    assert checkpoint.event_count > 0
    types = {g.glyph_type for g in stack.graph.ledger.glyphs()}
    assert "evidence" in types
    assert "plan" in types
    assert "policy" in types
    assert checkpoint.chain_head
    assert checkpoint.merkle_root
