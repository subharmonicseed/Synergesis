from pathlib import Path

import pytest

from synergesis_aegis import (
    ActionSecurityProfile,
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
    ReasoningOutput,
)
from synergesis_agent_loop_v4 import (
    ActionTypeResourceResolver,
    NoCapabilities,
    TrustedSourceObservationClassifier,
)
from synergesis_causal_credit import CausalHypothesis, CausalModel
from synergesis_causal_planning import DIRECTIVE_OBSERVATION_KIND
from synergesis_experiment_utility import (
    ExperimentImpactProfile,
    ExperimentUtilityPolicy,
)
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_planner import PlanDraft, PlanStepDraft, StepAssessment
from synergesis_prediction_curiosity import PredictionCuriosityPolicy
from synergesis_risk_learning import (
    RiskLearningPolicy,
    RiskObservationContract,
)
from synergesis_risk_budget import RiskBudgetPolicy
from synergesis_reality import (
    FunctionRealityProbe,
    RealityAssertion,
    RealityObservation,
    RealityProbeBinding,
    RealityProfile,
)
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
from synergesis_roam_adaptive import AdaptiveSelectionConfig
from synergesis_roam_attention import AttentionWeights
from synergesis_roam_evolution import EvolutionPolicy
from synergesis_roam_service import RoamServiceLimits
from synergesis_secure_roam_stack_v2 import (
    SecureRoamConfig,
    build_secure_roam_reality_stack,
)


class CausalReasoner:
    def __init__(self):
        self.intervention = "check"
        self.ignore_prepared_directive = False

    def reason(self, context):
        intervention = self.intervention
        if (
            context is not None
            and context.observation.kind == DIRECTIVE_OBSERVATION_KIND
            and not self.ignore_prepared_directive
        ):
            intervention = context.observation.payload["selected_intervention"]
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "One of two registered faults explains the outcome.",
                    rationale="controlled causal-credit integration test",
                ),
            ),
            ActionProposal.create(
                "file.write",
                {
                    "path": f"{intervention}.txt",
                    "content": "verified",
                    "intervention": intervention,
                },
                rationale="apply registered diagnostic intervention",
                expected_outcome="runtime observer verifies the effect",
                strategy_key="diagnose",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(
            0.8 if result.success else 0.2,
            "Learning uses the independently verified effective result.",
        )


class Planner:
    def create_plan(self, context):
        return PlanDraft(
            rationale="single controlled diagnostic action",
            steps=(
                PlanStepDraft(
                    "diagnose",
                    "verified runtime effect",
                    "file.write",
                ),
            ),
        )

    def assess_step(self, context, step, cycle):
        return StepAssessment(
            "completed" if cycle.action_result is not None else "blocked",
            "integration test",
            1.0,
        )

    def replan(self, context, previous_plan, failed_step, assessment):
        return self.create_plan(context)


class SourceAdapter:
    def search(self, *, query, max_items):
        return (
            RetrievedItem(
                "https://example.test/causal",
                "Causal evidence",
                "controlled evidence",
                "test",
                0.1,
            ),
        )[:max_items]


def config(root):
    return SecureRoamConfig(
        root=root,
        identity="ZÆL-0",
        allowed_actions=frozenset({"file.write"}),
        context_max_facts=8,
        context_max_evidence=8,
        bm25_k1=1.5,
        bm25_b=0.75,
        max_steps_per_plan=2,
        max_replans=1,
        max_attempts_per_step=2,
        roam_limits=RoamLimits(2, 4, 2.0),
        selection_config=SelectionConfig(0.0, True),
        adaptive_selection_config=AdaptiveSelectionConfig(
            rolling_window_per_method=4,
            max_selection_gap=3,
            exploration_strength=0.1,
            decay_half_life_events=3.0,
        ),
        utility_weights=UtilityWeights(1, 1, 1, 1, 1, 1, 1),
        attention_weights=AttentionWeights(1, 1, 1, 1),
        service_limits=RoamServiceLimits(2, True),
        evolution_policy=EvolutionPolicy(
            max_steps_per_method=2,
            min_trials_per_method=1,
            promotion_margin=0.1,
            require_counter_search=True,
        ),
    )


def build_stack(
    tmp_path,
    *,
    requires_capability=False,
    utility_profiles=(),
    utility_policy=None,
    risk_contracts=(),
    risk_policy=None,
    risk_budget_policy=None,
):
    root = tmp_path / "stack"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    # Ground candidate beliefs in the same persistent World Model that the
    # composition root will reopen.
    pre_graph = GlyphAuditGraph(GlyphLedger(root / "glyph_ledger.jsonl"))
    pre_core = GlyphAuditedCognitiveCore(
        root / "semantic_memory.jsonl",
        graph=pre_graph,
        actor="ZÆL-0",
    )
    storage = pre_core.remember(
        "system",
        "possible_fault",
        "storage",
        "operator",
        0.5,
        "belief:storage",
    )
    network = pre_core.remember(
        "system",
        "possible_fault",
        "network",
        "operator",
        0.5,
        "belief:network",
    )

    model = CausalModel(
        action_type="file.write",
        strategy_key="diagnose",
        intervention_parameter="intervention",
        observer_id="probe:state",
        observed_intervention_fact="intervention",
        hypotheses=(
            CausalHypothesis(
                storage.evidence_id,
                0.5,
                (("check", 0.2), ("repair", 0.9)),
            ),
            CausalHypothesis(
                network.evidence_id,
                0.5,
                (("check", 0.2), ("repair", 0.1)),
            ),
        ),
    )

    reasoner = CausalReasoner()
    applied_override = {"value": None, "adverse": False}

    def executor(params):
        # Record what the runtime actually applied in a separate receipt.
        # The observer reads this receipt instead of trusting requested params.
        requested = params["intervention"]
        applied = applied_override["value"] or requested
        target = runtime_root / params["path"]
        intervention_receipt = runtime_root / (params["path"] + ".intervention")
        intervention_receipt.write_text(applied, encoding="utf-8")
        adverse_receipt = runtime_root / (params["path"] + ".adverse")
        if applied_override["adverse"]:
            adverse_receipt.write_text("adverse", encoding="utf-8")
        elif adverse_receipt.exists():
            adverse_receipt.unlink()

        # The baseline check fails; the repair intervention produces the effect.
        success = applied == "repair"
        if success:
            target.write_text(params["content"], encoding="utf-8")
        return ActionResult(
            "file.write",
            success,
            {
                "path": str(target),
                "intervention_receipt": str(intervention_receipt),
            },
            None if success else "baseline_effect_absent",
        )

    def observe(action_type, resource, params):
        target = runtime_root / params["path"]
        intervention_receipt = runtime_root / (params["path"] + ".intervention")
        adverse_receipt = runtime_root / (params["path"] + ".adverse")
        effect = target.is_file() and target.read_text(encoding="utf-8") == params["content"]
        applied = (
            intervention_receipt.read_text(encoding="utf-8")
            if intervention_receipt.is_file()
            else None
        )
        return (
            RealityObservation.create(
                observer_id="probe:state",
                channel="filesystem_diagnostic",
                resource=resource,
                facts={
                    "effect": effect,
                    "intervention": applied,
                    "adverse_event": adverse_receipt.is_file(),
                },
            ),
        )

    probe = FunctionRealityProbe(
        observer_id="probe:state",
        callback=observe,
    )

    source_registry = SourceRegistry()
    source_registry.register(
        SourcePolicy("test", "test", ("systems",), 2, True)
    )
    method = make_method(
        name="test method",
        domain="systems",
        created_by="test",
        steps=(SearchStep("test", "challenge", "{question}", 1),),
    )

    ids = IdentityRegistry(tmp_path / "ids.jsonl")
    signer = IdentitySigner("ZÆL-0")
    ids.register("ZÆL-0", signer.public_key)

    stack = build_secure_roam_reality_stack(
        config=config(root),
        reasoner=reasoner,
        planning_provider=Planner(),
        executors={"file.write": executor},
        identity_registry=ids,
        capability_store=CapabilityStore(tmp_path / "caps.jsonl"),
        trusted_capability_issuers=frozenset(),
        action_security_profiles=(
            ActionSecurityProfile(
                "file.write",
                requires_capability,
                frozenset(),
            ),
        ),
        observation_classifier=TrustedSourceObservationClassifier(
            trusted_sources=frozenset({"user"})
        ),
        capability_resolver=NoCapabilities(),
        resource_resolver=ActionTypeResourceResolver(),
        reality_probe_bindings=(
            RealityProbeBinding(
                "probe:state",
                "runtime_attested",
                probe,
            ),
        ),
        reality_profiles=(
            RealityProfile(
                "file.write",
                ("probe:state",),
                (
                    RealityAssertion(
                        "probe:state",
                        "effect",
                        "truthy",
                    ),
                ),
            ),
        ),
        source_registry=source_registry,
        source_adapters={"test": SourceAdapter()},
        research_methods=(method,),
        prediction_curiosity_policy=PredictionCuriosityPolicy(
            min_observations=1,
            rolling_window=1,
            minimum_absolute_error=0.9,
            minimum_surprise_bits=10.0,
            rolling_brier_threshold=1.0,
            cooldown_records=3,
            surprise_scale_bits=4.0,
            default_domain="systems",
            default_expected_impact=0.8,
            domain_by_action={"file.write": "systems"},
            expected_impact_by_action={"file.write": 0.8},
        ),
        causal_models=(model,),
        causal_experiment_utility_profiles=tuple(utility_profiles),
        causal_experiment_utility_policy=utility_policy,
        risk_observation_contracts=tuple(risk_contracts),
        risk_learning_policy=risk_policy,
        risk_budget_policy=risk_budget_policy,
    )
    return stack, reasoner, applied_override


def run(stack):
    return stack.agent_audit.run_cycle(
        goal=Goal.create("Run controlled causal diagnostic"),
        observation=AgentObservation(
            "request",
            {"text": "diagnose"},
            "user",
        ),
    ).cycle


def test_full_stack_chains_world_revision_then_causal_credit(tmp_path):
    stack, _, _ = build_stack(tmp_path)
    assert stack.prediction is not None
    assert stack.world_revision is not None
    assert stack.causal_credit is not None
    assert stack.prediction.provider is stack.causal_credit
    assert stack.causal_credit.fallback is stack.world_revision
    assert stack.world_revision.estimator is not stack.causal_credit


def test_full_stack_indeterminate_then_targeted_90_10_revision(tmp_path):
    stack, reasoner, _ = build_stack(tmp_path)

    reasoner.intervention = "check"
    first = run(stack)
    assert first.action_result.success is False
    first_receipts = [
        g for g in stack.graph.ledger.glyphs()
        if g.content.get("kind") == "causal_credit"
    ]
    assert first_receipts[-1].content["status"] == "indeterminate"
    assert first_receipts[-1].content["causal_responsibility"] == "not_identified"
    assert stack.causal_credit.posterior(
        "file.write", "diagnose"
    ) == pytest.approx({
        "belief:storage": 0.5,
        "belief:network": 0.5,
    })

    reasoner.intervention = "repair"
    second = run(stack)
    assert second.action_result.success is True
    posterior = stack.causal_credit.posterior("file.write", "diagnose")
    assert posterior["belief:storage"] == pytest.approx(0.9)
    assert posterior["belief:network"] == pytest.approx(0.1)

    receipts = [
        g for g in stack.graph.ledger.glyphs()
        if g.content.get("kind") == "causal_credit"
    ]
    assert [g.content["status"] for g in receipts] == [
        "indeterminate",
        "conditional_update",
    ]
    assert receipts[-1].content["causal_responsibility"] == "conditional_on_registered_models"

    # The next prediction actually uses the revised 90/10 posterior.
    reasoner.intervention = "repair"
    proposal = reasoner.reason(None).action
    prediction = stack.prediction.provider.predict(
        context=None,
        proposal=proposal,
    )
    # 0.9*0.9 + 0.1*0.1 = 0.82
    assert prediction.probability_effect_success == pytest.approx(0.82)


def test_full_stack_causal_credit_does_not_mutate_source_belief_confidence(tmp_path):
    stack, reasoner, _ = build_stack(tmp_path)
    reasoner.intervention = "repair"
    run(stack)
    source = {
        f.evidence_id: f
        for f in stack.core.memory.query(subject="system")
    }
    assert source["belief:storage"].confidence == pytest.approx(0.5)
    assert source["belief:network"].confidence == pytest.approx(0.5)
    assert any(
        fact.predicate == stack.causal_credit.predicate
        for fact in stack.core.world.snapshot().facts
    )


def test_full_stack_rejects_requested_intervention_when_runtime_applied_another(tmp_path):
    stack, reasoner, applied_override = build_stack(tmp_path)

    reasoner.intervention = "repair"
    applied_override["value"] = "check"
    cycle = run(stack)
    assert cycle.action_result.success is False

    receipts = [
        g for g in stack.graph.ledger.glyphs()
        if g.content.get("kind") == "causal_credit"
    ]
    assert receipts[-1].content["status"] == "intervention_unverified"
    assert receipts[-1].content["causal_responsibility"] == "not_identified"
    assert stack.causal_credit.posterior(
        "file.write", "diagnose"
    ) == pytest.approx({
        "belief:storage": 0.5,
        "belief:network": 0.5,
    })

    observations = [
        g for g in stack.graph.ledger.glyphs()
        if g.content.get("kind") == "runtime_reality_observation"
        and g.content.get("observer_id") == "probe:state"
    ]
    assert observations[-1].content["facts"]["intervention"] == "check"
    assert reasoner.intervention == "repair"


def test_full_stack_recommends_most_informative_registered_intervention(tmp_path):
    stack, _, _ = build_stack(tmp_path)
    assert stack.causal_experiment is not None

    recommendation = stack.causal_experiment.recommend(
        action_type="file.write",
        strategy_key="diagnose",
    )
    scores = {score.intervention: score for score in recommendation.scores}
    assert recommendation.status == "informative"
    assert recommendation.selected_intervention == "repair"
    assert scores["check"].information_gain_bits == pytest.approx(0.0)
    assert scores["repair"].information_gain_bits > 0.5

    glyph = stack.graph.ledger.get(recommendation.recommendation_glyph_id)
    assert glyph.content["kind"] == "causal_experiment_recommendation"
    assert glyph.content["authorization_effect"] == "none"


def test_full_stack_recommends_after_indeterminate_observation_without_auto_execution(tmp_path):
    stack, reasoner, _ = build_stack(tmp_path)
    reasoner.intervention = "check"
    first = run(stack)
    assert first.action_result.success is False
    posterior = stack.causal_credit.posterior("file.write", "diagnose")
    assert posterior == pytest.approx({
        "belief:storage": 0.5,
        "belief:network": 0.5,
    })

    recommendation = stack.causal_experiment.recommend(
        action_type="file.write",
        strategy_key="diagnose",
    )
    assert recommendation.selected_intervention == "repair"
    # Recommendation is advisory only: the reasoner's intended intervention was
    # not rewritten by the selector and no second action was executed.
    assert reasoner.intervention == "check"
    action_glyphs = [
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ]
    assert len(action_glyphs) == 1


def test_prepared_causal_experiment_requires_explicit_execution(tmp_path):
    stack, _, _ = build_stack(tmp_path)
    assert stack.causal_planning is not None

    before_actions = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ])
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    assert prepared.executable is True
    assert prepared.directive is not None
    assert prepared.mission is not None
    assert prepared.mission.status == "active"

    after_prepare_actions = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ])
    assert after_prepare_actions == before_actions
    assert stack.causal_planning.registry.consumed(
        prepared.directive.directive_id
    ) is False


def test_prepared_causal_experiment_runs_through_planner_aegis_reality_and_credit(tmp_path):
    stack, _, _ = build_stack(tmp_path)
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    directive = prepared.directive
    assert directive is not None
    assert directive.intervention == "repair"

    advance = stack.causal_planning.execute_prepared(
        directive.directive_id
    )
    assert advance.cycle is not None
    assert advance.cycle.policy.allowed is True
    assert advance.cycle.proposal.parameters["intervention"] == "repair"
    assert advance.assessment.outcome == "completed"
    assert advance.mission.status == "completed"

    posterior = stack.causal_credit.posterior("file.write", "diagnose")
    assert posterior == pytest.approx({
        "belief:storage": 0.9,
        "belief:network": 0.1,
    })
    assert stack.causal_planning.registry.consumed(
        directive.directive_id
    ) is True

    with pytest.raises(ValueError, match="already consumed"):
        stack.causal_planning.execute_prepared(directive.directive_id)


def test_reasoner_cannot_substitute_a_different_intervention(tmp_path):
    stack, reasoner, _ = build_stack(tmp_path)
    reasoner.ignore_prepared_directive = True
    reasoner.intervention = "check"

    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    directive = prepared.directive
    assert directive is not None
    assert directive.intervention == "repair"

    advance = stack.causal_planning.execute_prepared(
        directive.directive_id
    )
    assert advance.cycle is not None
    assert advance.cycle.proposal is None
    assert advance.cycle.action_result is None
    assert advance.assessment.outcome == "blocked"
    assert advance.mission.status == "blocked"
    assert stack.causal_planning.registry.consumed(
        directive.directive_id
    ) is False

    rejections = [
        g for g in stack.graph.ledger.glyphs()
        if g.content.get("kind") == "causal_experiment_binding_rejected"
    ]
    assert rejections[-1].content["reason"] == "intervention_mismatch"
    assert stack.causal_credit.posterior(
        "file.write", "diagnose"
    ) == pytest.approx({
        "belief:storage": 0.5,
        "belief:network": 0.5,
    })


def test_aegis_can_deny_even_a_correct_prepared_experiment(tmp_path):
    stack, _, _ = build_stack(
        tmp_path,
        requires_capability=True,
    )
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    directive = prepared.directive
    assert directive is not None

    advance = stack.causal_planning.execute_prepared(
        directive.directive_id
    )
    assert advance.cycle is not None
    assert advance.cycle.proposal is not None
    assert advance.cycle.policy.allowed is False
    assert advance.cycle.action_result is None
    assert advance.assessment.outcome == "blocked"
    assert stack.causal_planning.registry.consumed(
        directive.directive_id
    ) is False
    assert stack.causal_credit.posterior(
        "file.write", "diagnose"
    ) == pytest.approx({
        "belief:storage": 0.5,
        "belief:network": 0.5,
    })


def test_causal_directive_is_durably_linked_to_plan_and_has_no_authority(tmp_path):
    stack, _, _ = build_stack(tmp_path)
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    directive = prepared.directive
    assert directive is not None
    glyph = stack.graph.ledger.get(directive.directive_glyph_id)
    assert glyph.content["authorization_effect"] == "none"
    assert glyph.content["single_use"] is True

    plan = prepared.mission.plan
    plan_glyph = stack.graph.ledger.find_by_external_ref(
        plan.plan_id,
        glyph_type="plan",
    )[-1]
    assert any(
        edge.source == plan_glyph.glyph_id
        and edge.target == directive.directive_glyph_id
        and edge.relation == "derived_from"
        for edge in stack.graph.ledger.edges_from(plan_glyph.glyph_id)
    )


def utility_policy(**overrides):
    values = dict(
        risk_weight=1.0,
        cost_weight=1.0,
        irreversibility_weight=1.0,
        minimum_utility=0.01,
        minimum_information_gain_bits=1e-9,
        maximum_risk=1.0,
        maximum_irreversibility=1.0,
        tie_tolerance=1e-12,
    )
    values.update(overrides)
    return ExperimentUtilityPolicy(**values)


def impact(intervention, *, risk=0.0, cost=0.0, irreversibility=0.0):
    return ExperimentImpactProfile(
        action_type="file.write",
        strategy_key="diagnose",
        intervention=intervention,
        risk=risk,
        cost=cost,
        irreversibility=irreversibility,
    )


def test_stack_utility_gate_can_refuse_to_create_experiment_plan(tmp_path):
    stack, _, _ = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.9),
        ),
        utility_policy=utility_policy(maximum_risk=0.5),
    )
    assert stack.causal_experiment_utility is not None
    before_plans = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "plan"
    ])
    before_actions = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ])

    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )

    assert prepared.executable is False
    assert prepared.directive is None
    assert prepared.mission is None
    assert prepared.utility_decision is not None
    assert prepared.utility_decision.status == "no_safe_candidate"
    assert len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "plan"
    ]) == before_plans
    assert len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ]) == before_actions


def test_stack_approved_utility_decision_is_in_directive_provenance(tmp_path):
    stack, _, _ = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check"),
            impact("repair", risk=0.05, cost=0.02),
        ),
        utility_policy=utility_policy(),
    )
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    assert prepared.executable is True
    assert prepared.utility_decision is not None
    assert prepared.utility_decision.status == "approved"
    assert prepared.utility_decision.selected_intervention == "repair"
    directive = prepared.directive
    assert directive is not None

    upstream = stack.graph.upstream(directive.directive_glyph_id, max_depth=3)
    ids = {g.glyph_id for g in upstream.glyphs}
    assert prepared.recommendation.recommendation_glyph_id in ids
    assert prepared.utility_decision.decision_glyph_id in ids

    advance = stack.causal_planning.execute_prepared(
        directive.directive_id
    )
    assert advance.assessment.outcome == "completed"
    assert stack.causal_credit.posterior(
        "file.write", "diagnose"
    ) == pytest.approx({
        "belief:storage": 0.9,
        "belief:network": 0.1,
    })


def test_stack_rejects_partial_utility_configuration(tmp_path):
    with pytest.raises(ValueError, match="requires both"):
        build_stack(
            tmp_path,
            utility_profiles=(impact("repair"),),
            utility_policy=None,
        )


def risk_contract():
    return RiskObservationContract(
        action_type="file.write",
        strategy_key="diagnose",
        observer_id="probe:state",
        adverse_event_fact="adverse_event",
    )


def risk_policy(**overrides):
    values = dict(
        prior_alpha=1.0,
        prior_beta=1.0,
        half_life_events=32.0,
        uncertainty_margin_weight=0.5,
    )
    values.update(overrides)
    return RiskLearningPolicy(**values)


def test_failed_action_is_not_automatically_counted_as_adverse(tmp_path):
    stack, reasoner, _ = build_stack(
        tmp_path,
        risk_contracts=(risk_contract(),),
        risk_policy=risk_policy(),
    )
    assert stack.risk_learning is not None

    reasoner.intervention = "check"
    cycle = run(stack)
    assert cycle.action_result.success is False

    records = stack.risk_learning.ledger.records(
        action_type="file.write",
        strategy_key="diagnose",
        intervention="check",
    )
    assert len(records) == 1
    assert records[0].adverse_event is False


def test_observed_adverse_event_can_raise_risk_and_block_next_experiment(tmp_path):
    stack, reasoner, runtime = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.05),
        ),
        utility_policy=utility_policy(maximum_risk=0.5),
        risk_contracts=(risk_contract(),),
        risk_policy=risk_policy(),
    )
    assert stack.risk_learning is not None
    assert stack.causal_experiment_utility is not None

    # A technically successful repair has a separately observed adverse event.
    runtime["adverse"] = True
    reasoner.intervention = "repair"
    cycle = run(stack)
    assert cycle.action_result.success is True

    estimate = stack.risk_learning.estimate(
        action_type="file.write",
        strategy_key="diagnose",
        intervention="repair",
    )
    assert estimate.observations == 1
    assert estimate.posterior_mean > 0.5
    assert estimate.conservative_risk > 0.5

    before_plans = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "plan"
    ])
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    assert prepared.executable is False
    assert prepared.utility_decision is not None
    assert prepared.utility_decision.status == "no_safe_candidate"
    repair = {
        candidate.intervention: candidate
        for candidate in prepared.utility_decision.candidates
    }["repair"]
    assert repair.configured_risk_floor == pytest.approx(0.05)
    assert repair.learned_conservative_risk == pytest.approx(
        estimate.conservative_risk
    )
    assert repair.risk == pytest.approx(estimate.conservative_risk)
    assert "risk_above_policy_maximum" in repair.block_reasons

    # Rejection happens before a new Planner mission is created.
    assert len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "plan"
    ]) == before_plans


def test_learning_cannot_lower_trusted_risk_floor(tmp_path):
    configured_floor = 0.45
    stack, reasoner, runtime = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=configured_floor),
        ),
        utility_policy=utility_policy(
            maximum_risk=1.0,
            risk_weight=0.0,
        ),
        risk_contracts=(risk_contract(),),
        risk_policy=risk_policy(
            uncertainty_margin_weight=0.0,
        ),
    )
    runtime["adverse"] = False
    reasoner.intervention = "repair"

    # Accumulate safe observations so the empirical posterior mean falls below
    # the configured governance floor.
    for _ in range(6):
        run(stack)

    estimate = stack.risk_learning.estimate(
        action_type="file.write",
        strategy_key="diagnose",
        intervention="repair",
    )
    assert estimate.posterior_mean < configured_floor

    recommendation = stack.causal_experiment.recommend(
        action_type="file.write",
        strategy_key="diagnose",
    )
    decision = stack.causal_experiment_utility.evaluate(recommendation)
    repair = {
        candidate.intervention: candidate
        for candidate in decision.candidates
    }["repair"]
    assert repair.learned_conservative_risk == pytest.approx(
        estimate.conservative_risk
    )
    assert repair.risk == pytest.approx(configured_floor)
    assert repair.configured_risk_floor == pytest.approx(configured_floor)


def test_stack_rejects_partial_risk_learning_configuration(tmp_path):
    with pytest.raises(ValueError, match="risk learning requires both"):
        build_stack(
            tmp_path,
            risk_contracts=(risk_contract(),),
            risk_policy=None,
        )


def budget_policy(limit=0.45, single=1.0):
    return RiskBudgetPolicy(
        budget_limit=limit,
        maximum_single_reservation=single,
    )


def test_cumulative_risk_budget_blocks_repeated_small_exposures(tmp_path):
    stack, _, _ = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.2),
        ),
        utility_policy=utility_policy(risk_weight=0.0),
        risk_budget_policy=budget_policy(limit=0.45),
    )
    assert stack.risk_budget is not None

    for expected_consumed in (0.2, 0.4):
        prepared = stack.causal_planning.prepare(
            action_type="file.write",
            strategy_key="diagnose",
        )
        assert prepared.executable is True
        advance = stack.causal_planning.execute_prepared(
            prepared.directive.directive_id
        )
        assert advance.cycle.action_result is not None
        assert stack.risk_budget.state().consumed == pytest.approx(
            expected_consumed
        )

    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    assert prepared.executable is True
    before_actions = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ])
    with pytest.raises(ValueError, match="budget exhausted"):
        stack.causal_planning.execute_prepared(
            prepared.directive.directive_id
        )
    assert len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ]) == before_actions
    state = stack.risk_budget.state()
    assert state.consumed == pytest.approx(0.4)
    assert state.reserved == pytest.approx(0.0)
    assert state.available == pytest.approx(0.05)


def test_aegis_denial_releases_risk_reservation(tmp_path):
    stack, _, _ = build_stack(
        tmp_path,
        requires_capability=True,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.2),
        ),
        utility_policy=utility_policy(risk_weight=0.0),
        risk_budget_policy=budget_policy(limit=0.25),
    )
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    advance = stack.causal_planning.execute_prepared(
        prepared.directive.directive_id
    )
    assert advance.cycle.policy.allowed is False
    assert advance.cycle.action_result is None
    state = stack.risk_budget.state()
    assert state.consumed == pytest.approx(0.0)
    assert state.reserved == pytest.approx(0.0)
    assert state.available == pytest.approx(0.25)
    events = stack.risk_budget.ledger.events()
    assert [event.event_type for event in events] == [
        "reserved", "released"
    ]


def test_reasoner_binding_rejection_releases_risk_reservation(tmp_path):
    stack, reasoner, _ = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.2),
        ),
        utility_policy=utility_policy(risk_weight=0.0),
        risk_budget_policy=budget_policy(limit=0.25),
    )
    reasoner.ignore_prepared_directive = True
    reasoner.intervention = "check"
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    advance = stack.causal_planning.execute_prepared(
        prepared.directive.directive_id
    )
    assert advance.cycle.proposal is None
    assert advance.cycle.action_result is None
    state = stack.risk_budget.state()
    assert state.consumed == pytest.approx(0.0)
    assert state.reserved == pytest.approx(0.0)


def test_executed_but_unverified_intervention_still_consumes_budget(tmp_path):
    stack, _, runtime = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.2),
        ),
        utility_policy=utility_policy(risk_weight=0.0),
        risk_budget_policy=budget_policy(limit=0.25),
    )
    # The reasoner requests repair, but executor runtime receipt says check.
    runtime["value"] = "check"
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    advance = stack.causal_planning.execute_prepared(
        prepared.directive.directive_id
    )
    assert advance.cycle.action_result is not None
    assert advance.assessment.outcome == "blocked"
    assert "intervention_unverified" in advance.assessment.rationale
    state = stack.risk_budget.state()
    assert state.consumed == pytest.approx(0.2)
    assert state.reserved == pytest.approx(0.0)


def test_budget_is_not_replenished_by_safe_risk_learning(tmp_path):
    stack, reasoner, runtime = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.2),
        ),
        utility_policy=utility_policy(
            risk_weight=0.0,
            maximum_risk=1.0,
        ),
        risk_contracts=(risk_contract(),),
        risk_policy=risk_policy(uncertainty_margin_weight=0.0),
        risk_budget_policy=budget_policy(limit=0.65),
    )
    runtime["adverse"] = False
    reasoner.intervention = "repair"

    for _ in range(2):
        prepared = stack.causal_planning.prepare(
            action_type="file.write",
            strategy_key="diagnose",
        )
        stack.causal_planning.execute_prepared(
            prepared.directive.directive_id
        )

    estimate = stack.risk_learning.estimate(
        action_type="file.write",
        strategy_key="diagnose",
        intervention="repair",
    )
    assert estimate.posterior_mean < 0.5
    consumed_after_two = stack.risk_budget.state().consumed
    assert consumed_after_two > 0.4
    assert consumed_after_two < 0.65

    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    with pytest.raises(ValueError, match="budget exhausted"):
        stack.causal_planning.execute_prepared(
            prepared.directive.directive_id
        )
    assert stack.risk_budget.state().consumed == pytest.approx(
        consumed_after_two
    )


def test_stack_rejects_risk_budget_without_utility_configuration(tmp_path):
    with pytest.raises(ValueError, match="risk budget requires"):
        build_stack(
            tmp_path,
            risk_budget_policy=budget_policy(),
        )


def test_prepared_directive_is_revalidated_against_new_learned_risk(tmp_path):
    stack, reasoner, runtime = build_stack(
        tmp_path,
        utility_profiles=(
            impact("check", risk=0.0),
            impact("repair", risk=0.05),
        ),
        utility_policy=utility_policy(maximum_risk=0.5),
        risk_contracts=(risk_contract(),),
        risk_policy=risk_policy(),
    )
    prepared = stack.causal_planning.prepare(
        action_type="file.write",
        strategy_key="diagnose",
    )
    assert prepared.executable is True
    directive = prepared.directive
    assert directive is not None
    assert directive.intervention == "repair"

    # New verified evidence arrives before the prepared mission is executed:
    # repair succeeds technically but produces a separately observed adverse event.
    runtime["adverse"] = True
    reasoner.intervention = "repair"
    ordinary_cycle = run(stack)
    assert ordinary_cycle.action_result.success is True

    estimate = stack.risk_learning.estimate(
        action_type="file.write",
        strategy_key="diagnose",
        intervention="repair",
    )
    assert estimate.conservative_risk > 0.5

    before_actions = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ])
    with pytest.raises(ValueError, match="stale causal experiment directive"):
        stack.causal_planning.execute_prepared(directive.directive_id)
    after_actions = len([
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "action"
    ])
    assert after_actions == before_actions

    checks = [
        g for g in stack.graph.ledger.glyphs()
        if g.content.get("kind") == "causal_experiment_freshness_check"
        and g.content.get("directive_id") == directive.directive_id
    ]
    assert checks[-1].content["status"] == "stale"
    assert checks[-1].content["current_utility_status"] == "no_safe_candidate"
    assert checks[-1].content["authorization_effect"] == "none"


def test_stack_current_belief_view_keeps_history_but_exposes_only_latest_heads(tmp_path):
    stack, reasoner, _ = build_stack(tmp_path)
    reasoner.intervention = "repair"

    first = run(stack)
    second = run(stack)
    assert first.action_result.success is True
    assert second.action_result.success is True

    model = stack.causal_credit.models[("file.write", "diagnose")]
    history = stack.world_beliefs.history(
        subject=model.model_id,
        predicate=stack.causal_credit.predicate,
    )
    assert len(history) == 2
    current = stack.world_beliefs.current(
        subject=model.model_id,
        predicate=stack.causal_credit.predicate,
    )
    assert current == history[-1]

    materialized = stack.world_beliefs.materialized_facts()
    current_ids = {
        fact.evidence_id for fact in materialized
        if (
            fact.subject == model.model_id
            and fact.predicate == stack.causal_credit.predicate
        )
    }
    assert current_ids == {history[-1].evidence_id}
    assert stack.core.memory.count() > len(materialized)
