from hashlib import sha256
from pathlib import Path

import pytest

from synergesis_aegis import AegisSecurityGraph
from synergesis_agent_loop_v2 import ActionProposal, ActionResult
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_reality import (
    FileStateProbe,
    FunctionRealityProbe,
    RealityAssertion,
    RealityAuditService,
    RealityObservation,
    RealityProbeBinding,
    RealityProfile,
    RealityVerifier,
)


def proposal(path="out.txt", content="hello"):
    return ActionProposal.create(
        "file.write",
        {"path": path, "content": content},
        rationale="write test file",
        expected_outcome="file exists with requested content",
        strategy_key="file-write",
    )


def setup_verifier(tmp_path, *, extra_bindings=(), profile=None):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    file_probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=tmp_path / "sandbox",
        path_parameter="path",
        max_hash_bytes=1024 * 1024,
    )
    bindings = (
        RealityProbeBinding(
            observer_id="os:file",
            authority_class="runtime_attested",
            probe=file_probe,
        ),
        *extra_bindings,
    )
    profile = profile or RealityProfile(
        action_type="file.write",
        required_observer_ids=("os:file",),
        assertions=(
            RealityAssertion("os:file", "exists", "eq", True),
            RealityAssertion(
                "os:file",
                "sha256",
                "sha256_parameter_utf8",
                parameter_key="content",
            ),
        ),
    )
    verifier = RealityVerifier(
        graph=graph,
        security_graph=security,
        probe_bindings=bindings,
        profiles=(profile,),
    )
    return graph, security, verifier, file_probe


def action_glyph(graph, p):
    return graph.create(
        "action",
        actor="ZÆL-0",
        content={
            "action_type": p.action_type,
            "parameters": dict(p.parameters),
        },
        external_refs=(p.proposal_id,),
    )


def test_truthful_file_write_is_verified(tmp_path):
    graph, security, verifier, probe = setup_verifier(tmp_path)
    p = proposal(content="verified")
    target = probe.allowed_root / p.parameters["path"]
    target.write_text(p.parameters["content"], encoding="utf-8")

    assessment = verifier.verify(
        proposal=p,
        action_glyph_id=action_glyph(graph, p).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult("file.write", True, {"claimed": "ok"}),
    )
    assert assessment.status == "confirmed"
    assert assessment.effect_observed is True
    assert assessment.executor_claim_matches_reality is True
    assert assessment.effective_result.success is True


def test_executor_false_success_is_overridden_by_runtime_reality(tmp_path):
    graph, security, verifier, probe = setup_verifier(tmp_path)
    p = proposal()

    assessment = verifier.verify(
        proposal=p,
        action_glyph_id=action_glyph(graph, p).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult("file.write", True, {"claimed": "written"}),
    )
    assert assessment.status == "contradicted"
    assert assessment.effect_observed is False
    assert assessment.executor_claim_matches_reality is False
    assert assessment.effective_result.success is False
    assert assessment.effective_result.error == "reality:effect_not_observed"
    assert "executor_claim_mismatch" in security.active_taints(
        assessment.executor_outcome_glyph_id
    )


def test_effect_can_exist_even_when_executor_claims_failure(tmp_path):
    graph, security, verifier, probe = setup_verifier(tmp_path)
    p = proposal(content="side effect happened")
    target = probe.allowed_root / p.parameters["path"]
    target.write_text(p.parameters["content"], encoding="utf-8")

    assessment = verifier.verify(
        proposal=p,
        action_glyph_id=action_glyph(graph, p).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult(
            "file.write",
            False,
            {"claimed": "failed"},
            "executor_timeout",
        ),
    )
    assert assessment.status == "confirmed"
    assert assessment.effect_observed is True
    assert assessment.executor_claim_matches_reality is False
    assert assessment.effective_result.success is True


def test_wrong_file_content_is_a_real_contradiction(tmp_path):
    graph, security, verifier, probe = setup_verifier(tmp_path)
    p = proposal(content="expected")
    target = probe.allowed_root / p.parameters["path"]
    target.write_text("different", encoding="utf-8")

    assessment = verifier.verify(
        proposal=p,
        action_glyph_id=action_glyph(graph, p).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult("file.write", True, {}),
    )
    assert assessment.status == "contradicted"
    assert assessment.effective_result.success is False


def test_runtime_observation_receives_runtime_attested_origin(tmp_path):
    graph, security, verifier, probe = setup_verifier(tmp_path)
    p = proposal(content="x")
    (probe.allowed_root / p.parameters["path"]).write_text("x", encoding="utf-8")

    assessment = verifier.verify(
        proposal=p,
        action_glyph_id=action_glyph(graph, p).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult("file.write", True, {}),
    )
    observation_id = assessment.observation_glyph_ids[0]
    binding = security.origin_binding(observation_id)
    assert binding is not None
    assert binding.content["authority_class"] == "runtime_attested"
    assert binding.content["rank"] == security.ORIGIN_CLASSES["runtime_attested"]


def test_filesystem_probe_rejects_path_escape(tmp_path):
    probe = FileStateProbe(
        observer_id="os:file",
        allowed_root=tmp_path / "sandbox",
        path_parameter="path",
        max_hash_bytes=100,
    )
    with pytest.raises(ValueError, match="escapes allowed_root"):
        probe.observe(
            action_type="file.write",
            resource="action:file.write",
            parameters={"path": "../escape.txt"},
        )


def test_missing_required_fact_is_unverified_and_fails_closed(tmp_path):
    def callback(action_type, resource, params):
        return (
            RealityObservation.create(
                observer_id="runtime",
                channel="runtime",
                resource=resource,
                facts={"exists": True},
            ),
        )

    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    verifier = RealityVerifier(
        graph=graph,
        security_graph=security,
        probe_bindings=(
            RealityProbeBinding(
                "runtime",
                "runtime_attested",
                FunctionRealityProbe(
                    observer_id="runtime",
                    callback=callback,
                ),
            ),
        ),
        profiles=(
            RealityProfile(
                "file.write",
                ("runtime",),
                (
                    RealityAssertion("runtime", "exists", "eq", True),
                    RealityAssertion("runtime", "sha256", "eq", "abc"),
                ),
            ),
        ),
    )
    p = proposal()
    assessment = verifier.verify(
        proposal=p,
        action_glyph_id=action_glyph(graph, p).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult("file.write", True, {}),
    )
    assert assessment.status == "unverified"
    assert assessment.effect_observed is None
    assert assessment.effective_result.success is False


def test_conflicting_runtime_observers_fail_closed(tmp_path):
    resource = "action:file.write"

    def yes(action_type, resource, params):
        return (
            RealityObservation.create(
                observer_id="observer:yes",
                channel="runtime",
                resource=resource,
                facts={"effect": True},
            ),
        )

    def no(action_type, resource, params):
        return (
            RealityObservation.create(
                observer_id="observer:no",
                channel="runtime",
                resource=resource,
                facts={"effect": False},
            ),
        )

    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    security = AegisSecurityGraph(graph)
    verifier = RealityVerifier(
        graph=graph,
        security_graph=security,
        probe_bindings=(
            RealityProbeBinding(
                "observer:yes",
                "runtime_attested",
                FunctionRealityProbe(observer_id="observer:yes", callback=yes),
            ),
            RealityProbeBinding(
                "observer:no",
                "runtime_attested",
                FunctionRealityProbe(observer_id="observer:no", callback=no),
            ),
        ),
        profiles=(
            RealityProfile(
                "file.write",
                ("observer:yes", "observer:no"),
                (
                    RealityAssertion("observer:yes", "effect", "eq", True),
                    RealityAssertion("observer:no", "effect", "eq", True),
                ),
            ),
        ),
    )
    p = proposal()
    assessment = verifier.verify(
        proposal=p,
        action_glyph_id=action_glyph(graph, p).glyph_id,
        resource=resource,
        raw_result=ActionResult("file.write", True, {}),
    )
    assert assessment.status == "observer_conflict"
    assert assessment.effect_observed is None
    assert assessment.effective_result.success is False


def test_reality_audit_service_measures_executor_reliability(tmp_path):
    graph, security, verifier, probe = setup_verifier(tmp_path)

    good = proposal(path="good.txt", content="ok")
    (probe.allowed_root / "good.txt").write_text("ok", encoding="utf-8")
    verifier.verify(
        proposal=good,
        action_glyph_id=action_glyph(graph, good).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult("file.write", True, {}),
    )

    lie = proposal(path="missing.txt", content="never")
    verifier.verify(
        proposal=lie,
        action_glyph_id=action_glyph(graph, lie).glyph_id,
        resource="action:file.write",
        raw_result=ActionResult("file.write", True, {}),
    )

    report = RealityAuditService(graph).reliability("file.write")
    assert report.assessments == 2
    assert report.verified == 2
    assert report.executor_claim_matches == 1
    assert report.executor_claim_mismatches == 1
    assert report.match_rate_on_verified == pytest.approx(0.5)
