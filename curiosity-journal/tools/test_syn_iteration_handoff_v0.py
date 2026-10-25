"""Synthetic checks of persistent decision handoffs; not SYN model learning."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "iteration_handoff", Path(__file__).with_name("syn_iteration_handoff_v0.py"))
it = importlib.util.module_from_spec(spec)
spec.loader.exec_module(it)


def report(entry_id, *, stage="proposed", outcome="not_tested",
           score=.5, refs=None, timestamp="2026-10-25T14:00:00+01:00"):
    refs = [] if refs is None else refs
    return {"schema": "syn-curiosity-v1", "entry_id": entry_id,
            "observed_at": timestamp, "domain": "cross-domain-science",
            "question": "Can a new hypothesis generalize?",
            "stage": stage, "outcome": outcome, "gap_kind": "unverified",
            "metrics": {"selection_score": score},
            "evidence_refs": refs,
            "uncertainty_after": .5 if stage == "assessed" else None}


class HandoffTests(unittest.TestCase):
    def test_next_iteration_changes_when_refuted_result_arrives(self):
        v1 = it.advance(None, [report("a:proposal", score=.6)])
        self.assertEqual(v1["iteration"], 1)
        self.assertEqual(v1["queue"][0]["proposed_action"], "run_preregistered_test")
        v2 = it.advance(v1, [report("b:refuted", stage="assessed",
                                   outcome="refuted", score=.7,
                                   refs=["https://example.org/study"])])
        self.assertEqual(v2["iteration"], 2)
        self.assertEqual(v2["previous_digest"], v1["digest"])
        self.assertEqual(v2["queue"][0]["entry_id"], "b:refuted")
        self.assertEqual(v2["queue"][0]["proposed_action"], "investigate_refutation")
        self.assertEqual(len(v2["ledger"]), 2)
        self.assertEqual(v2["queue"][0]["state"], "queued_not_executed")

    def test_serialize_and_continue_without_new_reports(self):
        s1 = it.advance(None, [report("a")])
        s2 = it.advance(json.loads(json.dumps(s1)), [])
        self.assertEqual(s2["previous_digest"], s1["digest"])
        self.assertEqual(len(s2["ledger"]), 1)
        self.assertEqual(s2["queue"][0]["entry_id"], "a")

    def test_tamper_detected(self):
        state = it.advance(None, [report("a")])
        altered = copy.deepcopy(state)
        altered["ledger"][0]["priority_heuristic"] = 1
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            it.advance(altered, [])

    def test_duplicate_refused_even_if_identical(self):
        state = it.advance(None, [report("same")])
        with self.assertRaisesRegex(ValueError, "duplicate entry"):
            it.advance(state, [report("same")])
        with self.assertRaisesRegex(ValueError, "duplicate entry"):
            it.advance(state, [report("same", score=.9)])

    def test_unassessed_report_cannot_claim_evidence(self):
        with self.assertRaisesRegex(ValueError, "unassessed"):
            it.advance(None, [report("a", refs=["https://example.org/study"])])

    def test_assessed_report_needs_sources(self):
        with self.assertRaisesRegex(ValueError, "lacks claimed evidence"):
            it.advance(None, [report("a", stage="assessed", outcome="supported")])

    def test_bad_probabilities_and_timestamps(self):
        with self.assertRaisesRegex(ValueError, "selection_score"):
            it.advance(None, [report("a", score=float("nan"))])
        with self.assertRaisesRegex(ValueError, "timezone"):
            it.advance(None, [report("a", timestamp="2026-10-25T14:00:00")])

    def test_queue_capacity_and_determinism(self):
        rows = [report(f"item-{i}", score=i / 10) for i in range(8)]
        a = it.advance(None, rows, capacity=2)
        b = it.advance(None, list(reversed(rows)), capacity=2)
        self.assertEqual(a["digest"], b["digest"])
        self.assertEqual([x["entry_id"] for x in a["queue"]], ["item-7", "item-6"])
        with self.assertRaisesRegex(ValueError, "queue capacity"):
            it.advance(None, rows, capacity=0)

    def test_first_iteration_cannot_be_empty(self):
        with self.assertRaisesRegex(ValueError, "empty handoff"):
            it.advance(None, [])

    def test_assessed_inconclusive_branches_to_more_evidence(self):
        a = report("c", stage="assessed", outcome="inconclusive",
                   score=.4, refs=["https://example.org/study"])
        state = it.advance(None, [a])
        self.assertEqual(state["queue"][0]["proposed_action"],
                         "seek_discriminating_evidence")

    def test_previous_digest_cannot_be_rewritten_without_detection(self):
        s = it.advance(None, [report("a")])
        s["previous_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            it.advance(s, [])


if __name__ == "__main__":
    unittest.main()
