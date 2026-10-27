"""Tests for triaging curated science leads; no web or model calls."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "syn_science_scout", Path(__file__).with_name("syn_science_anomaly_scout_v0.py"))
scout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scout)


def example(i, domain, checked=True, *, surprise=.8, testability=.7, cross=.6):
    return {
        "schema": scout.SCHEMA, "id": f"signal-{i}",
        "headline": "Unexpected new finding about physical systems", "domain": domain,
        "lead_url": "https://www.youtube.com/watch?v=4Op_5mnXTWI",
        "primary_url": "https://arxiv.org/abs/2605.16504",
        "primary_status": "primary_checked" if checked else "primary_unchecked",
        "publication_date": "2026-05-15", "evidence_kind": "simulation",
        "finding": "A schematic simulation shows a shift in an outcome distribution",
        "baseline_expectation": "Earlier models omitted the effect",
        "competing_explanation": "Assumptions in a simplified simulation are responsible",
        "falsifier": "Compare independent simulations and new observations",
        "cross_domain_question": "Could an analogous effect exist in another dynamical system?",
        "heuristics": {
            "surprise": surprise, "testability": testability,
            "cross_domain_relevance": cross,
        },
    }


class ScoutTests(unittest.TestCase):
    def test_checked_primary(self):
        item = scout.assess([example(1, "astro")])["selected"][0]
        self.assertEqual(item["conclusion"], "research_candidate")
        self.assertEqual(item["primary_check"], "curator_checked_primary")
        self.assertTrue(item["cited_primary_url"].startswith("https://"))

    def test_unverified_paper_is_not_citable(self):
        item = scout.assess([example(1, "astro", checked=False)])["selected"][0]
        self.assertEqual(item["conclusion"], "verification_only")
        self.assertIsNone(item["cited_primary_url"])

    def test_headline_only_rejected(self):
        row = example(1, "astro")
        row["finding"] = ""
        with self.assertRaisesRegex(ValueError, "finding"):
            scout.assess([row])

    def test_domain_diversity(self):
        rows = [example(1, "astro", surprise=1),
                example(2, "astro", surprise=.9),
                example(3, "biology", surprise=.3)]
        self.assertEqual([i["id"] for i in scout.assess(rows)["selected"]],
                         ["signal-1", "signal-3"])

    def test_bad_source_rejected(self):
        row = example(1, "astro")
        row["primary_url"] = "http://example.com/paper"
        with self.assertRaisesRegex(ValueError, "primary_url"):
            scout.assess([row])

    def test_checked_primary_needs_url(self):
        row = example(1, "astro")
        row["primary_url"] = None
        with self.assertRaisesRegex(ValueError, "checked primary"):
            scout.assess([row])

    def test_duplicate_story(self):
        row = example(1, "astro")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            scout.assess([row, row])

    def test_invalid_priority_not_converted_to_probability(self):
        row = example(1, "astro")
        row["heuristics"]["surprise"] = 1.5
        with self.assertRaisesRegex(ValueError, "heuristic"):
            scout.assess([row])
        self.assertIn("never calibrated", scout.assess([example(1, "astro")])
                      ["scoring_policy"])

    def test_expected_model_survives_triage(self):
        row = example(1, "astro")
        result = scout.assess([row])["selected"][0]
        self.assertEqual(result["baseline_expectation"], row["baseline_expectation"])
        self.assertEqual(result["publication_date"], row["publication_date"])

    def test_empty_input(self):
        self.assertEqual(scout.assess([])["selected"], [])

    def test_no_promotion(self):
        self.assertTrue(scout.assess([example(1, "astro")])["promotion"].startswith("NONE"))


if __name__ == "__main__":
    unittest.main()
