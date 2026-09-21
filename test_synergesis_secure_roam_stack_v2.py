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
from synergesis_planner import PlanDraft, PlanStepDraft, StepAssessment
from synergesis_perception_knowledge import PerceptionKnowledgeRule
from synergesis_multisource_fusion import (
    FusionPolicy,
    FusionSourceProfile,
)
from synergesis_perception_bus import (
    NormalizedPercept,
    PerceptionSourcePolicy,
    RawPercept,
)
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_reality import (
    FileStateProbe,
    RealityAssertion,
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
from synergesis_prediction_curiosity import PredictionCuriosityPolicy
from synergesis_provenance_receipts import (
    ProvenanceReceiptAuthority,
    ProvenanceReceiptStore,
    ProvenanceReceiptVerifier,
)
from synergesis_provenance_transport import (
    ProvenanceTransportExporter,
    ProvenanceTransportPolicy,
)
from synergesis_roam_attention import AttentionMeasurements, AttentionWeights
from synergesis_roam_evolution import EvolutionPolicy
from synergesis_roam_service import RoamServiceLimits
from synergesis_secure_roam_stack_v2 import (
    SecureRoamConfig,
    build_secure_roam_reality_stack,
)


class Reasoner:
    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "Write the file.",
                    rationale="integration test",
                ),
            ),
            ActionProposal.create(
                "file.write",
                {"path": "integrated.txt", "content": "verified"},
                rationale="integration test",
                expected_outcome="file exists",
                strategy_key="integrated-file-write",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(0.9, "Observed effective result.")


class Planner:
    def create_plan(self, context):
        return PlanDraft(
            rationale="One file step.",
            steps=(
                PlanStepDraft(
                    "Write file",
                    "file is verified",
                    "file.write",
                ),
            ),
        )

    def assess_step(self, context, step, cycle):
        return StepAssessment(
            "completed"
            if cycle.action_result and cycle.action_result.success
            else "blocked",
            "Use verified action result.",
            1.0,
        )

    def replan(self, context, previous_plan, failed_step, assessment):
        return PlanDraft(
            rationale="Retry once.",
            steps=(
                PlanStepDraft(
                    "Retry file",
                    "file is verified",
                    "file.write",
                ),
            ),
        )


class SourceAdapter:
    def search(self, *, query, max_items):
        return (
            RetrievedItem(
                "https://example.test/research",
                "Research",
                "evidence",
                "test",
                0.1,
            ),
        )[:max_items]


class PerceptionAdapter:
    def normalize(self, percept):
        return NormalizedPercept(
            "temperature_reading",
            {"celsius": percept.payload["celsius"]},
            None,
        )


class KnowledgePerceptionAdapter:
    def normalize(self, percept):
        return NormalizedPercept(
            "temperature_reading",
            {
                "device": percept.payload["device"],
                "celsius": percept.payload["celsius"],
            },
            0.9,
        )


def config(tmp_path):
    return SecureRoamConfig(
        root=tmp_path / "stack",
        identity="ZÆL-0",
        allowed_actions=frozenset({"file.write"}),
        context_max_facts=8,
        context_max_evidence=8,
        bm25_k1=1.5,
        bm25_b=0.75,
        max_steps_per_plan=3,
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


def build(
    tmp_path,
    *,
    lie=False,
    include_reality_profile=True,
    enable_curiosity=False,
    enable_transport=False,
    enable_perception=False,
    enable_perception_knowledge=False,
    enable_fusion=False,
    provisional_belief_policy=None,
    belief_research_policy=None,
    stack_overrides=None,
):
    cfg = config(tmp_path)
    runtime_root = tmp_path / "runtime"
    probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=runtime_root,
        path_parameter="path",
        max_hash_bytes=1024 * 1024,
    )

    def executor(params):
        if not lie:
            target = runtime_root / params["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(params["content"], encoding="utf-8")
        return ActionResult("file.write", True, {"claimed": "ok"})

    source_registry = SourceRegistry()
    source_registry.register(
        SourcePolicy("test", "test", ("science",), 2, True)
    )
    method = make_method(
        name="test method",
        domain="science",
        created_by="test",
        steps=(
            SearchStep("test", "challenge", "{question}", 1),
        ),
    )

    ids = IdentityRegistry(tmp_path / "ids.jsonl")
    signer = IdentitySigner("ZÆL-0")
    ids.register("ZÆL-0", signer.public_key)

    transport_bundle = None
    transport_store = None
    transport_verifier = None
    transport_policy = None
    if enable_transport:
        ingress = IdentitySigner("transport-ingress")
        relay = IdentitySigner("transport-relay")
        sender = IdentitySigner("transport-agent")
        for transport_signer in (ingress, relay, sender):
            ids.register(
                transport_signer.identity_id,
                transport_signer.public_key,
            )

        remote_graph = GlyphAuditGraph(
            GlyphLedger(tmp_path / "transport_remote_glyphs.jsonl")
        )
        remote_store = ProvenanceReceiptStore(
            tmp_path / "transport_remote_receipts.jsonl"
        )
        remote_origin = remote_graph.create(
            "observation",
            actor="sensor",
            content={"kind": "remote_test_claim", "value": 7},
        )
        origin_receipt = ProvenanceReceiptAuthority(ingress).issue_origin(
            glyph_id=remote_origin.glyph_id,
            authority_class="trusted_observation",
            rank=3,
        )
        remote_store.append(origin_receipt)
        remote_leaf = remote_graph.create(
            "fact",
            actor="transport-relay",
            content={"kind": "remote_derived_claim", "value": 7},
            derived_from=(remote_origin.glyph_id,),
        )
        leaf_receipt = ProvenanceReceiptAuthority(relay).issue_derivation(
            glyph_id=remote_leaf.glyph_id,
            parent_receipt_id=origin_receipt.receipt_id,
            transform_kind="relay",
        )
        remote_store.append(leaf_receipt)
        transport_bundle = ProvenanceTransportExporter(
            graph=remote_graph,
            receipt_store=remote_store,
            signer=sender,
        ).export(
            glyph_id=remote_leaf.glyph_id,
            leaf_receipt_id=leaf_receipt.receipt_id,
            ttl_seconds=300,
        )

        transport_store = ProvenanceReceiptStore(
            tmp_path / "transport_local_receipts.jsonl"
        )
        transport_verifier = ProvenanceReceiptVerifier(
            store=transport_store,
            identity_registry=ids,
            trusted_origin_issuers=frozenset({"transport-ingress"}),
            trusted_derivation_issuers=frozenset({"transport-relay"}),
            origin_ranks={
                "unknown": 0,
                "external_untrusted": 1,
                "external_authenticated": 2,
                "trusted_observation": 3,
                "user_intent": 4,
                "control_plane": 4,
                "runtime_attested": 5,
                "system": 6,
            },
        )
        transport_policy = ProvenanceTransportPolicy(
            trusted_senders=frozenset({"transport-agent"}),
            allowed_origin_classes=frozenset({"trusted_observation"}),
            max_lifetime_seconds=600,
            max_future_skew_seconds=60,
            max_receipts=8,
        )

    profiles = (
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
    ) if include_reality_profile else ()

    stack_kwargs = dict(
        config=cfg,
        reasoner=Reasoner(),
        planning_provider=Planner(),
        executors={"file.write": executor},
        identity_registry=ids,
        capability_store=CapabilityStore(tmp_path / "caps.jsonl"),
        trusted_capability_issuers=frozenset(),
        action_security_profiles=(
            ActionSecurityProfile("file.write", False, frozenset()),
        ),
        observation_classifier=TrustedSourceObservationClassifier(
            trusted_sources=frozenset({"user"})
        ),
        capability_resolver=NoCapabilities(),
        resource_resolver=ActionTypeResourceResolver(),
        reality_probe_bindings=(
            RealityProbeBinding("os:file", "runtime_attested", probe),
        ),
        reality_profiles=profiles,
        source_registry=source_registry,
        source_adapters={"test": SourceAdapter()},
        research_methods=(method,),
        provenance_receipt_store=transport_store,
        provenance_receipt_verifier=transport_verifier,
        provenance_transport_policy=transport_policy,
        perception_source_policies=(
            (
                (
                    PerceptionSourcePolicy(
                        "sensor:a",
                        ("temperature",),
                        "trusted_observation",
                    ),
                    PerceptionSourcePolicy(
                        "sensor:b",
                        ("temperature",),
                        "trusted_observation",
                    ),
                    PerceptionSourcePolicy(
                        "sensor:c",
                        ("temperature",),
                        "trusted_observation",
                    ),
                )
                if enable_fusion
                else (
                    PerceptionSourcePolicy(
                        "sensor:test",
                        ("temperature",),
                        "trusted_observation",
                    ),
                )
            )
            if (enable_perception or enable_perception_knowledge or enable_fusion)
            else ()
        ),
        perception_adapters=(
            (
                {
                    ("sensor:a", "temperature"): KnowledgePerceptionAdapter(),
                    ("sensor:b", "temperature"): KnowledgePerceptionAdapter(),
                    ("sensor:c", "temperature"): KnowledgePerceptionAdapter(),
                }
                if enable_fusion
                else {
                    ("sensor:test", "temperature"): (
                        KnowledgePerceptionAdapter()
                        if enable_perception_knowledge
                        else PerceptionAdapter()
                    )
                }
            )
            if (enable_perception or enable_perception_knowledge or enable_fusion)
            else {}
        ),
        perception_knowledge_rules=(
            (
                PerceptionKnowledgeRule(
                    observation_kind="temperature_reading",
                    domain="science",
                    subject_fact="device",
                    predicate="temperature_c",
                    object_fact="celsius",
                    versioned=True,
                    allow_world_commit=True,
                    minimum_confidence=0.8,
                    change_semantics="contradiction",
                    research_on_contradiction=True,
                    research_question_template=(
                        "Why did {subject} temperature change "
                        "from {old} to {new}?"
                    ),
                    research_measurements=AttentionMeasurements(
                        uncertainty=0.8,
                        expected_impact=0.7,
                        staleness=0.1,
                        novelty_gap=0.9,
                    ),
                ),
            )
            if enable_perception_knowledge
            else ()
        ),
        provisional_belief_policy=provisional_belief_policy,
        belief_research_policy=belief_research_policy,
        fusion_source_profiles=(
            (
                FusionSourceProfile("sensor:a", "shared-camera-rig", 0.8),
                FusionSourceProfile("sensor:b", "shared-camera-rig", 0.8),
                FusionSourceProfile("sensor:c", "independent-sensor", 0.9),
            )
            if enable_fusion
            else ()
        ),
        fusion_policy=(
            FusionPolicy(
                observation_kind="temperature_reading",
                subject_fact="device",
                object_fact="celsius",
                minimum_origin_rank=2,
                max_time_span_seconds=5.0,
                minimum_independent_groups=2,
                minimum_support=1.0,
                minimum_support_margin=0.2,
                minimum_reliability_observations=2,
                minimum_adjudication_origin_rank=5,
                research_on_unresolved=True,
                research_domain="science",
                research_question_template=(
                    "Resolve multisource temperature for {subject}: "
                    "claims={claims}; reason={reason}"
                ),
                research_measurements=AttentionMeasurements(
                    uncertainty=0.9,
                    expected_impact=0.7,
                    staleness=0.1,
                    novelty_gap=0.8,
                ),
            )
            if enable_fusion
            else None
        ),
        prediction_curiosity_policy=(
            PredictionCuriosityPolicy(
                min_observations=1,
                rolling_window=1,
                minimum_absolute_error=0.4,
                minimum_surprise_bits=0.9,
                rolling_brier_threshold=0.2,
                cooldown_records=2,
                surprise_scale_bits=4.0,
                default_domain="science",
                default_expected_impact=0.8,
                domain_by_action={"file.write": "science"},
                expected_impact_by_action={"file.write": 0.9},
            )
            if enable_curiosity
            else None
        ),
    )
    stack_kwargs.update(stack_overrides or {})
    stack = build_secure_roam_reality_stack(**stack_kwargs)
    if enable_transport:
        return stack, transport_bundle
    return stack


def test_v2_stack_unifies_reality_aegis_roam_and_adaptive_learning(tmp_path):
    stack = build(tmp_path)
    assert stack.agent.reality_verifier is stack.reality
    assert stack.agent.graph is stack.graph
    assert stack.aegis.security_graph is stack.security_graph
    assert stack.roam_runtime.graph is stack.graph
    assert stack.method_learner.graph is stack.graph


def test_v2_stack_verified_action_flows_to_learning(tmp_path):
    stack = build(tmp_path)
    recorded = stack.agent_audit.run_cycle(
        goal=Goal.create("write integrated file"),
        observation=AgentObservation("request", {"x": 1}, "user"),
    )
    cycle = recorded.cycle
    assert cycle.policy.allowed is True
    assert cycle.action_result.success is True
    assert cycle.action_result.output["reality"]["status"] == "confirmed"
    assert cycle.learning.score == pytest.approx(0.9)
    report = stack.reality_audit.reliability("file.write")
    assert report.executor_claim_matches == 1


def test_v2_stack_executor_lie_is_corrected_before_planning_sees_it(tmp_path):
    stack = build(tmp_path, lie=True)
    recorded = stack.agent_audit.run_cycle(
        goal=Goal.create("write integrated file"),
        observation=AgentObservation("request", {"x": 1}, "user"),
    )
    cycle = recorded.cycle
    assert cycle.action_result.success is False
    assert cycle.learning.score == 0.0
    assert stack.reality_audit.reliability(
        "file.write"
    ).executor_claim_mismatches == 1


def test_v2_stack_requires_reality_profile_for_allowed_action(tmp_path):
    with pytest.raises(ValueError, match="missing SYN-REALITY profiles"):
        build(tmp_path, include_reality_profile=False)


def test_v2_stack_keeps_single_verified_glyph_history(tmp_path):
    stack = build(tmp_path)
    stack.agent_audit.run_cycle(
        goal=Goal.create("write integrated file"),
        observation=AgentObservation("request", {"x": 1}, "user"),
    )
    checkpoint = stack.graph.ledger.verify()
    kinds = {
        g.content.get("kind")
        for g in stack.graph.ledger.glyphs()
        if isinstance(g.content, dict)
    }
    assert "executor_claim" in kinds
    assert "runtime_reality_observation" in kinds
    assert "reality_verdict" in kinds
    assert "reality_effective_outcome" in kinds
    assert checkpoint.merkle_root


def test_v2_stack_prediction_surprise_can_create_roam_need(tmp_path):
    stack = build(tmp_path, lie=True, enable_curiosity=True)
    recorded = stack.agent_audit.run_cycle(
        goal=Goal.create("write integrated file"),
        observation=AgentObservation("request", {"x": 1}, "user"),
    )
    assert recorded.cycle.action_result.success is False
    assert stack.prediction is not None
    assert stack.prediction_curiosity is not None
    pending = stack.agenda.pending()
    assert len(pending) == 1
    assert pending[0].need.domain == "science"
    assert "file.write" in pending[0].need.question

    prediction_errors = [
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "learning"
        and g.content.get("kind") == "prediction_error"
    ]
    curiosity_triggers = [
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "decision"
        and g.content.get("kind") == "prediction_curiosity_trigger"
    ]
    assert len(prediction_errors) == 1
    assert len(curiosity_triggers) == 1


def test_v2_stack_world_revision_wraps_empirical_prediction_provider(tmp_path):
    stack = build(tmp_path)
    assert stack.prediction is not None
    assert stack.world_revision is not None
    assert stack.prediction.provider is stack.world_revision
    assert stack.world_revision.estimator.ledger is stack.prediction.ledger


def test_v2_stack_verified_outcome_revises_world_belief_and_next_prediction_uses_it(tmp_path):
    stack = build(tmp_path)

    first = stack.agent_audit.run_cycle(
        goal=Goal.create("write integrated file first"),
        observation=AgentObservation("request", {"x": 1}, "user"),
    ).cycle
    assert first.action_result.success is True

    belief = stack.world_revision.current_belief(
        "file.write",
        "integrated-file-write",
    )
    assert belief is not None
    revised_probability = float(belief.object)
    assert revised_probability > 0.5

    revisions = [
        g for g in stack.graph.ledger.glyphs()
        if g.content.get("kind") == "world_model_revision"
    ]
    assert len(revisions) == 1
    assert revisions[0].content["causal_responsibility"] == "not_identified"

    second = stack.agent_audit.run_cycle(
        goal=Goal.create("write integrated file second"),
        observation=AgentObservation("request", {"x": 2}, "user"),
    ).cycle
    second_predictions = [
        g for g in stack.graph.ledger.glyphs()
        if g.glyph_type == "hypothesis"
        and g.content.get("kind") == "action_prediction"
        and g.content.get("proposal_id") == second.proposal.proposal_id
    ]
    assert len(second_predictions) >= 2
    assert second_predictions[-1].content[
        "probability_effect_success"
    ] == pytest.approx(revised_probability)


def test_v2_stack_optional_provenance_transport_imports_remote_claim_safely(tmp_path):
    stack, bundle = build(tmp_path, enable_transport=True)
    assert stack.provenance_transport is not None
    assert stack.provenance_replay is not None

    imported = stack.provenance_transport.import_bundle(bundle)
    glyph = stack.graph.ledger.get(imported.local_glyph_id)
    assert glyph.content["kind"] == "remote_signed_claim"
    assert glyph.content["channel"] == "remote_transport"
    assert glyph.content["runtime_local"] is False
    assert glyph.content["authorization_effect"] == "none"
    binding = stack.security_graph.origin_binding(glyph.glyph_id)
    assert binding.content["authority_class"] == "trusted_observation"

    with pytest.raises(ValueError, match="replay"):
        stack.provenance_transport.import_bundle(bundle)


def test_v2_stack_rejects_partial_provenance_transport_configuration(tmp_path):
    cfg = config(tmp_path)
    source_registry = SourceRegistry()
    source_registry.register(
        SourcePolicy("test", "test", ("science",), 2, True)
    )
    method = make_method(
        name="test method",
        domain="science",
        created_by="test",
        steps=(SearchStep("test", "challenge", "{question}", 1),),
    )
    ids = IdentityRegistry(tmp_path / "partial_ids.jsonl")
    signer = IdentitySigner("ZÆL-0")
    ids.register("ZÆL-0", signer.public_key)

    runtime_root = tmp_path / "partial_runtime"
    probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=runtime_root,
        path_parameter="path",
        max_hash_bytes=1024 * 1024,
    )

    with pytest.raises(ValueError, match="requires receipt store, verifier and policy"):
        build_secure_roam_reality_stack(
            config=cfg,
            reasoner=Reasoner(),
            planning_provider=Planner(),
            executors={"file.write": lambda params: ActionResult("file.write", False, {})},
            identity_registry=ids,
            capability_store=CapabilityStore(tmp_path / "partial_caps.jsonl"),
            trusted_capability_issuers=frozenset(),
            action_security_profiles=(
                ActionSecurityProfile("file.write", False, frozenset()),
            ),
            observation_classifier=TrustedSourceObservationClassifier(
                trusted_sources=frozenset({"user"})
            ),
            capability_resolver=NoCapabilities(),
            resource_resolver=ActionTypeResourceResolver(),
            reality_probe_bindings=(
                RealityProbeBinding("os:file", "runtime_attested", probe),
            ),
            reality_profiles=(
                RealityProfile(
                    "file.write",
                    ("os:file",),
                    (RealityAssertion("os:file", "exists", "eq", True),),
                ),
            ),
            source_registry=source_registry,
            source_adapters={"test": SourceAdapter()},
            research_methods=(method,),
            provenance_receipt_store=ProvenanceReceiptStore(
                tmp_path / "partial_receipts.jsonl"
            ),
        )


def test_v2_stack_optional_perception_bus_preserves_missing_confidence_and_authority(tmp_path):
    stack = build(tmp_path, enable_perception=True)
    assert stack.perception is not None

    record = stack.perception.ingest(
        RawPercept(
            source_id="sensor:test",
            modality="temperature",
            payload={
                "celsius": 18.5,
                "authority_class": "system",
            },
            captured_at="2026-09-12T12:00:00+00:00",
            external_id="sample:1",
        )
    )
    raw = stack.graph.ledger.get(record.raw_glyph_id)
    normalized = stack.graph.ledger.get(record.normalized_glyph_id)
    binding = stack.security_graph.origin_binding(raw.glyph_id)

    assert binding.content["authority_class"] == "trusted_observation"
    assert raw.content["authority_from_payload"] is False
    assert normalized.confidence is None
    assert normalized.content["confidence_available"] is False
    assert normalized.content["authorization_effect"] == "none"


def test_v2_stack_rejects_perception_policy_without_adapter(tmp_path):
    cfg = config(tmp_path)
    source_registry = SourceRegistry()
    source_registry.register(
        SourcePolicy("test", "test", ("science",), 2, True)
    )
    method = make_method(
        name="test method",
        domain="science",
        created_by="test",
        steps=(SearchStep("test", "challenge", "{question}", 1),),
    )
    ids = IdentityRegistry(tmp_path / "perception_ids.jsonl")
    signer = IdentitySigner("ZÆL-0")
    ids.register("ZÆL-0", signer.public_key)
    runtime_root = tmp_path / "perception_runtime"
    probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=runtime_root,
        path_parameter="path",
        max_hash_bytes=1024 * 1024,
    )

    with pytest.raises(ValueError, match="requires both source policies and adapters"):
        build_secure_roam_reality_stack(
            config=cfg,
            reasoner=Reasoner(),
            planning_provider=Planner(),
            executors={"file.write": lambda params: ActionResult("file.write", False, {})},
            identity_registry=ids,
            capability_store=CapabilityStore(tmp_path / "perception_caps.jsonl"),
            trusted_capability_issuers=frozenset(),
            action_security_profiles=(
                ActionSecurityProfile("file.write", False, frozenset()),
            ),
            observation_classifier=TrustedSourceObservationClassifier(
                trusted_sources=frozenset({"user"})
            ),
            capability_resolver=NoCapabilities(),
            resource_resolver=ActionTypeResourceResolver(),
            reality_probe_bindings=(
                RealityProbeBinding("os:file", "runtime_attested", probe),
            ),
            reality_profiles=(
                RealityProfile(
                    "file.write",
                    ("os:file",),
                    (RealityAssertion("os:file", "exists", "eq", True),),
                ),
            ),
            source_registry=source_registry,
            source_adapters={"test": SourceAdapter()},
            research_methods=(method,),
            perception_source_policies=(
                PerceptionSourcePolicy(
                    "sensor:test",
                    ("temperature",),
                    "trusted_observation",
                ),
            ),
            perception_adapters={},
        )


def test_v2_stack_perception_can_feed_evidence_world_context_and_roam_need(tmp_path):
    stack = build(tmp_path, enable_perception_knowledge=True)
    assert stack.perception is not None
    assert stack.perception_knowledge is not None

    first_record = stack.perception.ingest(
        RawPercept(
            source_id="sensor:test",
            modality="temperature",
            payload={"device": "node:A", "celsius": 18.0},
            captured_at="2026-09-12T12:00:00+00:00",
            external_id="temperature:1",
        )
    )
    first = stack.perception_knowledge.process(first_record)
    assert first.admission_status == "committed"
    assert stack.agenda.pending() == ()

    second_record = stack.perception.ingest(
        RawPercept(
            source_id="sensor:test",
            modality="temperature",
            payload={"device": "node:A", "celsius": 24.0},
            captured_at="2026-09-12T12:01:00+00:00",
            external_id="temperature:2",
        )
    )
    second = stack.perception_knowledge.process(second_record)
    assert second.admission_status == "committed_with_contradiction"
    assert second.research_need_id is not None

    current = stack.world_beliefs.current(
        subject="node:A",
        predicate="temperature_c",
    )
    assert current is not None
    assert current.object == "24.0"
    history = stack.world_beliefs.history(
        subject="node:A",
        predicate="temperature_c",
    )
    assert [fact.object for fact in history] == ["18.0", "24.0"]

    selected = stack.perception_knowledge.select_context(
        query="node temperature"
    )
    selected_temperatures = [
        fact.object
        for fact in selected.facts
        if fact.subject == "node:A"
        and fact.predicate == "temperature_c"
    ]
    assert selected_temperatures == ["24.0"]
    assert len(selected.evidence) == 2

    pending = stack.agenda.pending()
    assert len(pending) == 1
    assert pending[0].need.need_id == second.research_need_id
    assert pending[0].status == "pending"
    # Creating the need does not itself launch a ROAM session.
    assert pending[0].session_id is None


def test_v2_stack_perception_knowledge_rule_requires_perception_bus(tmp_path):
    cfg = config(tmp_path)
    source_registry = SourceRegistry()
    source_registry.register(
        SourcePolicy("test", "test", ("science",), 2, True)
    )
    method = make_method(
        name="test method",
        domain="science",
        created_by="test",
        steps=(SearchStep("test", "challenge", "{question}", 1),),
    )
    ids = IdentityRegistry(tmp_path / "knowledge_ids.jsonl")
    signer = IdentitySigner("ZÆL-0")
    ids.register("ZÆL-0", signer.public_key)
    runtime_root = tmp_path / "knowledge_runtime"
    probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=runtime_root,
        path_parameter="path",
        max_hash_bytes=1024 * 1024,
    )

    with pytest.raises(ValueError, match="require the perception bus"):
        build_secure_roam_reality_stack(
            config=cfg,
            reasoner=Reasoner(),
            planning_provider=Planner(),
            executors={"file.write": lambda params: ActionResult("file.write", False, {})},
            identity_registry=ids,
            capability_store=CapabilityStore(tmp_path / "knowledge_caps.jsonl"),
            trusted_capability_issuers=frozenset(),
            action_security_profiles=(
                ActionSecurityProfile("file.write", False, frozenset()),
            ),
            observation_classifier=TrustedSourceObservationClassifier(
                trusted_sources=frozenset({"user"})
            ),
            capability_resolver=NoCapabilities(),
            resource_resolver=ActionTypeResourceResolver(),
            reality_probe_bindings=(
                RealityProbeBinding("os:file", "runtime_attested", probe),
            ),
            reality_profiles=(
                RealityProfile(
                    "file.write",
                    ("os:file",),
                    (RealityAssertion("os:file", "exists", "eq", True),),
                ),
            ),
            source_registry=source_registry,
            source_adapters={"test": SourceAdapter()},
            research_methods=(method,),
            perception_knowledge_rules=(
                PerceptionKnowledgeRule(
                    observation_kind="temperature_reading",
                    domain="science",
                    subject_fact="device",
                    predicate="temperature_c",
                    object_fact="celsius",
                    versioned=True,
                    allow_world_commit=False,
                    minimum_confidence=0.8,
                ),
            ),
        )


def test_v2_stack_perception_contradiction_can_drive_one_explicit_bounded_roam_tick(tmp_path):
    stack = build(tmp_path, enable_perception_knowledge=True)

    for external_id, value, captured_at in (
        ("temperature:a", 18.0, "2026-09-12T12:00:00+00:00"),
        ("temperature:b", 24.0, "2026-09-12T12:01:00+00:00"),
    ):
        record = stack.perception.ingest(
            RawPercept(
                source_id="sensor:test",
                modality="temperature",
                payload={"device": "node:A", "celsius": value},
                captured_at=captured_at,
                external_id=external_id,
            )
        )
        stack.perception_knowledge.process(record)

    pending = stack.agenda.pending()
    assert len(pending) == 1
    need_id = pending[0].need.need_id
    evidence_before = len(stack.aura.research.store.all())

    tick = stack.service.tick_once()
    assert tick.status == "researched"
    assert tick.need_id == need_id
    assert tick.session is not None
    assert tick.session.total_items == 1
    assert tick.session.status == "completed"

    state = stack.agenda.get(need_id)
    assert state.status == "researched"
    assert state.session_id == tick.session.session_id
    assert len(stack.aura.research.store.all()) == evidence_before + 1

    service_records = stack.service.ledger.records()
    assert service_records[-1].need_id == need_id
    assert service_records[-1].status == "researched"


def _fusion_percept(stack, source_id, celsius, external_id):
    return stack.perception.ingest(
        RawPercept(
            source_id=source_id,
            modality="temperature",
            payload={"device": "node:A", "celsius": celsius},
            captured_at="2026-09-12T12:00:00+00:00",
            external_id=external_id,
        )
    )


def test_v2_stack_multisource_fusion_collapses_correlated_sources_and_emits_evidence(tmp_path):
    stack = build(tmp_path, enable_fusion=True)
    assert stack.perception is not None
    assert stack.multisource_fusion is not None

    result = stack.multisource_fusion.fuse(
        (
            _fusion_percept(stack, "sensor:a", 21.0, "fusion:a"),
            _fusion_percept(stack, "sensor:b", 21.0, "fusion:b"),
            _fusion_percept(stack, "sensor:c", 21.0, "fusion:c"),
        )
    )

    assert result.status == "resolved"
    assert result.selected_claim == "21.0"
    # sensor:a and sensor:b share one independence group, so they contribute
    # max(0.8, 0.8), not 1.6. sensor:c contributes 0.9 independently.
    assert result.winner_support == pytest.approx(1.7)
    assert result.independent_groups_supporting_winner == 2
    assert result.evidence_id is not None
    assert result.evidence_glyph_id is not None
    evidence = stack.aura.research.store.get(result.evidence_id)
    assert evidence.source_type == "perception_fusion"

    selection = stack.agent.context_selector.select(
        query="multisource fusion node temperature 21.0",
        facts=stack.world_beliefs.materialized_facts(),
        evidence=stack.aura.research.store.all(),
    )
    assert any(
        item.evidence_id == result.evidence_id
        for item in selection.evidence
    )

    fusion_glyph = stack.graph.ledger.get(result.inference_glyph_id)
    assert fusion_glyph.content["source_count_is_not_independence"] is True
    assert fusion_glyph.content["authority_semantics"] == "eligibility_only"
    assert fusion_glyph.content["authorization_effect"] == "none"
    assert stack.agenda.pending() == ()


def test_v2_stack_unresolved_multisource_fusion_creates_research_need_then_bounded_roam_tick(tmp_path):
    stack = build(tmp_path, enable_fusion=True)

    result = stack.multisource_fusion.fuse(
        (
            _fusion_percept(stack, "sensor:a", 18.0, "fusion:a"),
            _fusion_percept(stack, "sensor:b", 18.0, "fusion:b"),
            _fusion_percept(stack, "sensor:c", 24.0, "fusion:c"),
        )
    )
    assert result.status == "unresolved"
    assert result.reason == "insufficient_independent_groups"
    assert result.selected_claim is None
    assert result.research_need_id is not None

    pending = stack.agenda.get(result.research_need_id)
    assert pending.status == "pending"
    assert pending.session_id is None

    evidence_before = len(stack.aura.research.store.all())
    tick = stack.service.tick_once()
    assert tick.status == "researched"
    assert tick.need_id == result.research_need_id
    assert tick.session is not None
    assert tick.session.status == "completed"
    assert len(stack.aura.research.store.all()) == evidence_before + 1


def test_v2_stack_rejects_partial_multisource_fusion_configuration(tmp_path):
    cfg = config(tmp_path)
    source_registry = SourceRegistry()
    source_registry.register(
        SourcePolicy("test", "test", ("science",), 2, True)
    )
    method = make_method(
        name="test method",
        domain="science",
        created_by="test",
        steps=(SearchStep("test", "challenge", "{question}", 1),),
    )
    ids = IdentityRegistry(tmp_path / "fusion_ids.jsonl")
    signer = IdentitySigner("ZÆL-0")
    ids.register("ZÆL-0", signer.public_key)
    runtime_root = tmp_path / "fusion_runtime"
    probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=runtime_root,
        path_parameter="path",
        max_hash_bytes=1024 * 1024,
    )

    with pytest.raises(ValueError, match="requires both source profiles and a fusion policy"):
        build_secure_roam_reality_stack(
            config=cfg,
            reasoner=Reasoner(),
            planning_provider=Planner(),
            executors={
                "file.write": lambda params: ActionResult(
                    "file.write", False, {}
                )
            },
            identity_registry=ids,
            capability_store=CapabilityStore(tmp_path / "fusion_caps.jsonl"),
            trusted_capability_issuers=frozenset(),
            action_security_profiles=(
                ActionSecurityProfile("file.write", False, frozenset()),
            ),
            observation_classifier=TrustedSourceObservationClassifier(
                trusted_sources=frozenset({"user"})
            ),
            capability_resolver=NoCapabilities(),
            resource_resolver=ActionTypeResourceResolver(),
            reality_probe_bindings=(
                RealityProbeBinding("os:file", "runtime_attested", probe),
            ),
            reality_profiles=(
                RealityProfile(
                    "file.write",
                    ("os:file",),
                    (RealityAssertion("os:file", "exists", "eq", True),),
                ),
            ),
            source_registry=source_registry,
            source_adapters={"test": SourceAdapter()},
            research_methods=(method,),
            perception_source_policies=(
                PerceptionSourcePolicy(
                    "sensor:a",
                    ("temperature",),
                    "trusted_observation",
                ),
            ),
            perception_adapters={
                ("sensor:a", "temperature"): KnowledgePerceptionAdapter(),
            },
            fusion_source_profiles=(
                FusionSourceProfile("sensor:a", "group:a", 0.8),
            ),
            fusion_policy=None,
        )


def test_v2_stack_fusion_provisional_beliefs_are_automatic_and_separate(tmp_path):
    from datetime import datetime, timezone, timedelta
    from synergesis_provisional_beliefs import ProvisionalBeliefPolicy
    stack = build(tmp_path, enable_fusion=True,
                  provisional_belief_policy=ProvisionalBeliefPolicy("temperature_reading", 60))
    now = datetime(2026, 9, 12, 12, 0, 1, tzinfo=timezone.utc)
    stack.provisional_beliefs.clock = lambda: now
    before = stack.core.memory.count()
    result = stack.multisource_fusion.fuse(tuple(
        _fusion_percept(stack, source, 21.0, "provisional:" + source)
        for source in ("sensor:a", "sensor:b", "sensor:c")))
    belief = stack.provisional_beliefs.current("node:A")
    assert belief.claim == "21.0" and belief.confidence is None
    assert belief.winner_support == pytest.approx(1.7)
    assert stack.core.world.snapshot().provisional_beliefs == (belief,)
    assert stack.core.memory.count() == before
    assert stack.aura.research.store.get(result.evidence_id).source_type == "perception_fusion"
    stack.provisional_beliefs.clock = lambda: now + timedelta(seconds=60)
    assert stack.core.world.snapshot().provisional_beliefs == ()


def test_v2_stack_rejects_provisional_policy_without_fusion(tmp_path):
    from synergesis_provisional_beliefs import ProvisionalBeliefPolicy
    with pytest.raises(ValueError, match="matching fusion"):
        build(tmp_path, provisional_belief_policy=ProvisionalBeliefPolicy("temperature_reading", 60))


def test_v2_expired_belief_tick_produces_roam_evidence(tmp_path):
    from datetime import datetime, timezone, timedelta
    from synergesis_provisional_beliefs import ProvisionalBeliefPolicy
    from synergesis_belief_research import BeliefResearchPolicy
    stack=build(tmp_path,enable_fusion=True,
        provisional_belief_policy=ProvisionalBeliefPolicy("temperature_reading",60),
        belief_research_policy=BeliefResearchPolicy("science", AttentionMeasurements(0.8,0.5,0.8,0.5)))
    now=datetime(2026,9,12,12,0,1,tzinfo=timezone.utc)
    stack.provisional_beliefs.clock=lambda:now
    stack.belief_research.clock=lambda:now
    stack.multisource_fusion.fuse(tuple(_fusion_percept(stack,s,21.0,'review:'+s)
        for s in ('sensor:a','sensor:b','sensor:c')))
    assert stack.belief_research.scan_once()==()
    before=len(stack.aura.research.store.all())
    now=now+timedelta(seconds=60)
    tick=stack.service.tick_once()
    assert tick.status=='researched' and tick.session is not None
    assert stack.agenda.get(tick.need_id).status=='researched'
    assert len(stack.aura.research.store.all())>before
    assert stack.core.world.snapshot().provisional_beliefs==()
    assert stack.service.tick_once().status=='idle'


def test_v2_belief_research_requires_belief_projection(tmp_path):
    from synergesis_belief_research import BeliefResearchPolicy
    with pytest.raises(ValueError,match="requires provisional"):
        build(tmp_path,belief_research_policy=BeliefResearchPolicy("science",AttentionMeasurements(0.5,0.5,0.5,0.5)))
