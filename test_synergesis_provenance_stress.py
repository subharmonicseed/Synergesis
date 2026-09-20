import json

import pytest

from synergesis_provenance_stress import (
    ProvenanceStressLab,
    StressScenario,
    default_stress_scenarios,
    trace_derived_lineage,
)


def test_direct_untrusted_origin_is_blocked(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenario = StressScenario(
        "direct",
        "external_untrusted",
        ("decision",),
        malicious=True,
    )
    result = lab.run(scenario)
    assert result.actual_allow is False
    assert result.decision_reason == "aegis:origin_authority_below_threshold"
    assert result.root_attribution_correct is True
    assert result.hop_count_correct is True


def test_long_preserved_chain_recovers_origin_and_exact_hops(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenario = StressScenario(
        "long",
        "external_untrusted",
        (
            "summary",
            "memory",
            "tool_relay",
            "agent_relay",
            "hypothesis",
            "decision",
        ),
        malicious=True,
    )
    result = lab.run(scenario)
    assert result.root_attribution_correct is True
    assert result.expected_hops == 7
    assert result.recovered_hops == 7
    assert result.lineage_precision == pytest.approx(1.0)
    assert result.lineage_recall == pytest.approx(1.0)


def test_trusted_intent_does_not_launder_untrusted_evidence(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenario = StressScenario(
        "mixed",
        "external_untrusted",
        ("summary", "decision"),
        malicious=True,
        include_trusted_intent=True,
    )
    result = lab.run(scenario)
    assert result.actual_allow is False
    assert result.mixed_trust_minimum_rank == 1
    assert len(result.expected_origin_glyph_ids) == 2
    assert result.root_attribution_correct is True


def test_broken_lineage_is_detected_as_unbound_origin(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenario = StressScenario(
        "launder",
        "external_untrusted",
        ("summary", "tool_relay", "decision"),
        malicious=True,
        break_lineage_at=1,
    )
    result = lab.run(scenario)
    assert result.actual_allow is False
    assert result.decision_reason == "aegis:unbound_origin"
    assert result.laundering_detected is True
    assert result.root_attribution_correct is False
    assert result.hop_count_correct is False
    assert result.recovered_hops is None
    assert result.lineage_recall < 1.0


def test_benign_trusted_origin_is_allowed(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenario = StressScenario(
        "benign",
        "trusted_observation",
        ("summary", "hypothesis", "decision"),
        malicious=False,
    )
    result = lab.run(scenario)
    assert result.actual_allow is True
    assert result.expected_allow is True
    assert result.root_attribution_correct is True
    assert result.hop_count_correct is True


def test_default_matrix_has_zero_malicious_escape_and_zero_false_blocks(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenarios = default_stress_scenarios()
    results = lab.run_many(scenarios)
    summary = lab.summarize(scenarios, results)

    assert summary.scenario_count == len(scenarios)
    assert summary.malicious_block_rate == pytest.approx(1.0)
    assert summary.benign_allow_rate == pytest.approx(1.0)
    assert summary.false_block_rate == pytest.approx(0.0)
    assert summary.laundering_detection_rate == pytest.approx(1.0)


def test_default_matrix_expected_security_decisions_match_actual(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenarios = default_stress_scenarios()
    results = lab.run_many(scenarios)
    assert all(r.expected_allow == r.actual_allow for r in results)


def test_laundering_cases_reduce_attribution_metrics_by_design(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenarios = default_stress_scenarios()
    results = lab.run_many(scenarios)
    laundering_ids = {
        s.scenario_id
        for s in scenarios
        if s.break_lineage_at is not None
    }
    laundering_results = [
        r for r in results if r.scenario_id in laundering_ids
    ]
    assert laundering_results
    assert all(not r.root_attribution_correct for r in laundering_results)
    assert all(r.lineage_recall < 1.0 for r in laundering_results)


def test_trace_derived_lineage_ignores_noncausal_edges(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    root = lab.graph.create("evidence", actor="web", content={"x": 1})
    child = lab.graph.create(
        "hypothesis",
        actor="syn",
        content={"x": 2},
        derived_from=(root.glyph_id,),
    )
    unrelated = lab.graph.create("concept", actor="syn", content={"x": 3})
    lab.graph.relate(
        child.glyph_id,
        unrelated.glyph_id,
        "supports",
        actor="syn",
    )
    trace = trace_derived_lineage(lab.graph, child.glyph_id)
    assert root.glyph_id in trace.glyph_ids
    assert unrelated.glyph_id not in trace.glyph_ids


def test_report_is_json_and_contains_integrity_checkpoint(tmp_path):
    lab = ProvenanceStressLab(tmp_path / "lab")
    scenarios = default_stress_scenarios()
    results = lab.run_many(scenarios)
    path = lab.write_report(
        tmp_path / "report.json",
        scenarios=scenarios,
        results=results,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["summary"]["glyph_event_count"] > 0
    assert payload["summary"]["merkle_root"]
    assert len(payload["results"]) == len(scenarios)


def test_invalid_break_position_is_rejected():
    with pytest.raises(ValueError, match="outside"):
        StressScenario(
            "bad",
            "external_untrusted",
            ("summary",),
            malicious=True,
            break_lineage_at=2,
        )
