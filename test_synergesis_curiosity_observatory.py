"""Behavioral tests for the bounded SYN-CURIOSITY observatory."""
from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from synergesis_curiosity_observatory import (
    CuriosityJournal,
    CuriosityObserver,
    validate_entry,
)
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_roam_attention import (
    AttentionMeasurements,
    AttentionWeights,
    ResearchAgenda,
    ResearchNeed,
)


NOW = datetime(2026, 10, 25, 8, 0, tzinfo=timezone.utc)


def agenda_at(tmp_path):
    graph = GlyphAuditGraph(GlyphLedger(tmp_path / "glyphs.jsonl"))
    agenda = ResearchAgenda(
        tmp_path / "agenda.jsonl",
        graph=graph,
        weights=AttentionWeights(1, 2, 1, 1),
    )
    return agenda


def make_need(question, impact):
    return ResearchNeed.create(
        domain="energy",
        question=question,
        hypothesis="A stated, testable hypothesis",
        reason="Unverified cross-domain assumption",
        measurements=AttentionMeasurements(
            uncertainty=0.8,
            expected_impact=impact,
            staleness=0.3,
            novelty_gap=0.4,
        ),
    )


def test_persistent_priority_and_restart_without_network(tmp_path):
    agenda = agenda_at(tmp_path)
    low = agenda.add(make_need("minor risk", 0.2))
    high = agenda.add(make_need("major risk", 0.9))
    path = tmp_path / "curiosity.jsonl"
    observer = CuriosityObserver(CuriosityJournal(path))

    proposals = observer.propose(
        agenda, limit=2,
        modes={high.need.need_id: "adversarial"},
        gap_kinds={high.need.need_id: "contradiction"},
        clock=lambda: NOW,
    )
    assert [p["need_id"] for p in proposals] == [
        high.need.need_id, low.need.need_id,
    ]
    assert proposals[0]["research_mode"] == "adversarial"
    assert proposals[0]["gap_kind"] == "contradiction"
    assert proposals[1]["research_mode"] == "unclassified"
    assert proposals[0]["metrics"]["selection_score"] > proposals[1]["metrics"]["selection_score"]
    assert all(p["stage"] == "proposed" and not p["evidence_refs"] for p in proposals)

    reopened = CuriosityJournal(path)
    assert reopened.records() == proposals
    assert len(CuriosityObserver(reopened).propose(agenda, limit=2, clock=lambda: NOW)) == 2
    assert len(reopened.records()) == 2


def test_integrity_detects_modification(tmp_path):
    journal = CuriosityJournal(tmp_path / "journal.jsonl")
    agenda = agenda_at(tmp_path)
    agenda.add(make_need("test hypothesis", 0.7))
    CuriosityObserver(journal).propose(agenda, clock=lambda: NOW)
    lines = journal.path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["entry"]["question"] = "altered without rehashing"
    journal.path.write_text(json.dumps(first) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        journal.records()


def test_invalid_policy_and_no_unapproved_actions(tmp_path):
    journal = CuriosityJournal(tmp_path / "journal.jsonl")
    agenda = agenda_at(tmp_path)
    agenda.add(make_need("risk", 0.5))
    observer = CuriosityObserver(journal)
    for invalid in (0, 4, True):
        with pytest.raises(ValueError):
            observer.propose(agenda, limit=invalid)
    with pytest.raises(ValueError):
        observer.propose(agenda, modes={agenda.pending()[0].need.need_id: "self_authorized"})
    assert journal.records() == ()


def test_assessment_requires_sources_and_explicit_uncertainty(tmp_path):
    journal = CuriosityJournal(tmp_path / "journal.jsonl")
    agenda = agenda_at(tmp_path)
    agenda.add(make_need("economic-model gap", 0.5))
    proposal = CuriosityObserver(journal).propose(agenda, clock=lambda: NOW)[0]
    assessed = {
        **proposal,
        "entry_id": "assessment:2026-10-25:1",
        "producer": "chatgpt",
        "stage": "assessed",
        "evidence_refs": ["https://www.iea.org/reports/energy-and-ai"],
        "outcome": "refuted",
        "uncertainty_after": 0.9,
        "learning": "The initial hypothesis was not supported by the cited source.",
    }
    assert validate_entry(assessed)["uncertainty_after"] == pytest.approx(0.9)
    assert journal.append(assessed)["outcome"] == "refuted"
    stats = journal.summary()
    assert stats["refutations"] == 1
    assert stats["assessments"] == 1
    assert stats["average_signed_uncertainty_reduction"] == pytest.approx(-0.1)
    assert journal.append(assessed) == assessed
    with pytest.raises(ValueError, match="conflicting"):
        journal.append({**assessed, "learning": "Silent rewrite"})
    with pytest.raises(ValueError, match="require sources"):
        validate_entry({**assessed, "evidence_refs": []})
    with pytest.raises(ValueError, match="cannot claim"):
        validate_entry({**proposal, "outcome": "supported"})


def test_cross_channel_json_import_and_no_secret_metadata(tmp_path):
    journal = CuriosityJournal(tmp_path / "journal.jsonl")
    agenda = agenda_at(tmp_path)
    agenda.add(make_need("governance", 0.7))
    proposal = CuriosityObserver(journal).propose(agenda, clock=lambda: NOW)[0]
    external = {
        **proposal,
        "entry_id": "chatgpt:2026-10-25:governance",
        "producer": "chatgpt",
        "stage": "assessed",
        "evidence_refs": ["https://www.oecd.org/en/publications/"],
        "outcome": "inconclusive",
        "uncertainty_after": 0.6,
        "learning": "More evidence required; no verified policy effect.",
    }
    report_path = tmp_path / "external.json"
    report_path.write_text(json.dumps(external), encoding="utf-8")
    journal.import_report(report_path)
    assert journal.import_report(report_path) == external
    assert len(journal.records()) == 2
    with pytest.raises(ValueError):
        validate_entry({**external, "api_key": "forbidden"})


def test_rejects_nan_and_broken_public_contract(tmp_path):
    agenda = agenda_at(tmp_path)
    agenda.add(make_need("unknown question", 0.4))
    proposal = CuriosityObserver(CuriosityJournal(tmp_path / "j.jsonl")).propose(
        agenda, clock=lambda: NOW,
    )[0]
    for bad in (
        {**proposal, "metrics": {**proposal["metrics"], "uncertainty": float("nan")}},
        {**proposal, "observed_at": "2026-10-25T08:00:00"},
        {**proposal, "evidence_refs": ["http://untrusted.test"]},
        {**proposal, "outcome": "supported"},
    ):
        with pytest.raises(ValueError):
            validate_entry(bad)
