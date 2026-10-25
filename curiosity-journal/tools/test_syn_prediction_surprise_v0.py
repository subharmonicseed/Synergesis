"""Synthetic timestamped forecast tests; no live forecasts or external verification."""
import importlib.util
from pathlib import Path
import math
import tempfile
import json
import unittest

spec = importlib.util.spec_from_file_location(
    "surprise", Path(__file__).with_name("syn_prediction_surprise_v0.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def forecast(name="f1", domain="astronomy", p=.9):
    return {"schema": mod.SCHEMA, "event_id": name, "domain": domain,
            "question": "Will a hypothetical binary event occur?",
            "forecast_at": "2026-09-29T08:00:00+00:00",
            "window_start": "2026-10-01T00:00:00Z",
            "window_end": "2026-10-02T00:00:00Z",
            "p_true": p, "forecast_ref": "https://example.org/immutable/fictional-forecast"}


def observation(name="f1", value=False, verified=True):
    return {"schema": mod.SCHEMA, "event_id": name,
            "resolved_at": "2026-10-03T13:00:00+00:00",
            "outcome": value, "evidence_url": "https://example.org/fictional-oracle",
            "externally_verified": verified, "verifier_id": "synthetic-test-only"}


class SurpriseTests(unittest.TestCase):
    def test_surprise_brier_and_bad_forecast_are_not_learning(self):
        result = mod.assess([forecast()], [observation()])
        self.assertEqual(len(result["surprise_candidates"]), 1)
        e = result["surprise_candidates"][0]
        self.assertAlmostEqual(e["surprisal_bits"], -math.log2(.1), places=6)
        self.assertEqual(e["brier"], .81)
        self.assertFalse(e["promoted_to_knowledge"])
        self.assertAlmostEqual(result["mean_brier"], .81)
        self.assertIn("NOT learning", result["interpretation"])

    def test_unsurprising_correct_prediction(self):
        result = mod.assess([forecast(p=.9)], [observation(value=True)])
        self.assertEqual(result["surprise_candidates"], [])
        self.assertAlmostEqual(result["mean_brier"], .01)

    def test_unverified_is_blocked(self):
        result = mod.assess([forecast()], [observation(verified=False)])
        self.assertEqual(result["n_externally_marked"], 0)
        self.assertEqual(result["mean_brier"], None)
        self.assertEqual(result["unscored"][0]["reason"], "external_review_required")

    def test_no_observation_not_inferred_false(self):
        r = mod.assess([forecast()], [])
        self.assertEqual(r["unscored"][0]["reason"], "no_outcome")
        self.assertEqual(r["n_outcomes"], 0)
        self.assertEqual(r["surprise_candidates"], [])

    def test_postdiction_rejected(self):
        f = forecast()
        f["forecast_at"] = f["window_start"]
        with self.assertRaisesRegex(ValueError, "precede"):
            mod.assess([f], [])

    def test_early_outcome_rejected(self):
        o = observation()
        o["resolved_at"] = "2026-10-01T13:00:00Z"
        with self.assertRaisesRegex(ValueError, "before"):
            mod.assess([forecast()], [o])

    def test_duplicates_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate forecast"):
            mod.assess([forecast(), forecast()], [])
        with self.assertRaisesRegex(ValueError, "duplicate outcome"):
            mod.assess([forecast()], [observation(), observation()])

    def test_unknown_outcome_rejected(self):
        with self.assertRaisesRegex(ValueError, "lacks preceding"):
            mod.assess([], [observation()])

    def test_bad_probabilities(self):
        for p in (0, 1, float("nan"), float("inf"), -1, True):
            with self.subTest(p=p), self.assertRaisesRegex(ValueError, "finite probability"):
                mod.assess([forecast(p=p)], [])

    def test_bad_verifier_claim(self):
        o = observation()
        o["externally_verified"] = "yes"
        with self.assertRaisesRegex(ValueError, "verification"):
            mod.assess([forecast()], [o])

    def test_timezone_required(self):
        f = forecast()
        f["forecast_at"] = "2026-09-29T08:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            mod.assess([f], [])

    def test_insecure_refs_rejected(self):
        f = forecast()
        f["forecast_ref"] = "http://insecure.example/forecast"
        with self.assertRaisesRegex(ValueError, "https"):
            mod.assess([f], [])

    def test_diversity_limit_and_ordering(self):
        fs = [forecast("f1", "astro", p=.99),
              forecast("f2", "astro", p=.9),
              forecast("f3", "marine", p=.8)]
        os = [observation(x["event_id"]) for x in fs]
        scored = mod.assess(fs, os, capacity=3)
        self.assertEqual([x["event_id"] for x in scored["surprise_candidates"]],
                         ["f1", "f3"])
        self.assertEqual(scored["n_externally_marked"], 3)

    def test_exact_two_bits_threshold(self):
        result = mod.assess([forecast(p=.75)], [observation()])
        self.assertEqual(result["surprise_candidates"][0]["surprisal_bits"], 2)

    def test_invalid_threshold(self):
        for x in (0, float("inf"), True, 25):
            with self.subTest(x=x), self.assertRaisesRegex(ValueError, "threshold"):
                mod.assess([], [], threshold_bits=x)

    def test_empty_records(self):
        r = mod.assess([], [])
        self.assertIsNone(r["mean_brier"])
        self.assertIsNone(r["naive_half_probability_brier"])
        self.assertIn("not certification", r["integrity_warning"])

    def test_jsonl_reader_rejects_blank(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.jsonl"
            p.write_text(json.dumps(forecast()) + "\n\n")
            with self.assertRaisesRegex(ValueError, "empty JSONL"):
                mod._read_jsonl(p)


if __name__ == "__main__":
    unittest.main()
