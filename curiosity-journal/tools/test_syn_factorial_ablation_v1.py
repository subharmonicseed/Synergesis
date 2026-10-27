"""Synthetic factorial-design checks. No LLM or SYN runs in these tests."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

s = importlib.util.spec_from_file_location("factorial", Path(__file__).with_name("syn_factorial_ablation_v1.py"))
f = importlib.util.module_from_spec(s)
s.loader.exec_module(f)


def fixture():
    manifest = {"model_id": "frozen-model-v0"}
    train = [{"task_id": f"train-{d}", "domain": d, "prompt": f"example {d}", "answer": "yes"}
             for d in ("arithmetic", "calendar", "graph")]
    test = [{"task_id": f"test-{i:02d}", "domain": ("arithmetic", "calendar", "graph")[i % 3],
             "prompt": f"question-{i:02d}"} for i in range(24)]
    cards = {"schema": "syn-factorial-skill-cards-v1", "cards": [
        {"domain": d, "skill_id": f"card-{d}", "procedure": f"procedure for {d}",
         "origin": "syn_candidate", "training_evidence_ids": [f"train-{d}"]}
        for d in ("arithmetic", "calendar", "graph")]}
    return manifest, train, test, cards


def mock_old():
    return SimpleNamespace(_rows=lambda manifest, train, test: (
        test, {d: [r for r in train if r["domain"] == d]
               for d in ("arithmetic", "calendar", "graph")}))


class FactorialTests(unittest.TestCase):
    def test_balanced_four_cells(self):
        m, train, test, c = fixture()
        with patch.object(f, "_module", return_value=mock_old()):
            q = f.build(m, train, test, c, seed=33)
        self.assertEqual(len(q), 96)
        self.assertEqual(len({(r["task_id"], r["arm"]) for r in q}), 96)
        self.assertEqual({a: sum(r["arm"] == a for r in q) for a in f.ARMS},
                         {a: 24 for a in f.ARMS})
        self.assertEqual({a: sum(q[4*i]["arm"] == a for i in range(24)) for a in f.ARMS},
                         {a: 6 for a in f.ARMS})
        for req in q:
            memory, skill = f.FACTORS[req["arm"]]
            self.assertEqual("Training examples from this domain" in req["prompt"], bool(memory))
            self.assertEqual("Candidate procedure" in req["prompt"], bool(skill))
            self.assertEqual(len(req["skill_ids"]), skill)
            self.assertNotIn("oracle", req["prompt"].lower())

    def test_repeatable_seed(self):
        m, tr, ts, c = fixture()
        with patch.object(f, "_module", return_value=mock_old()):
            self.assertEqual(f.build(m, tr, ts, c, seed=8), f.build(m, tr, ts, c, seed=8))
            self.assertNotEqual(f.build(m, tr, ts, c, seed=8), f.build(m, tr, ts, c, seed=9))

    def test_missing_or_duplicate_card_rejected(self):
        m, tr, ts, c = fixture()
        c["cards"] = c["cards"][:2]
        with patch.object(f, "_module", return_value=mock_old()):
            with self.assertRaisesRegex(ValueError, "one skill card"):
                f.build(m, tr, ts, c)
        c["cards"].append(c["cards"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            f.validate_cards(c, tr, ts)

    def test_invalid_candidate_evidence(self):
        m, tr, ts, c = fixture()
        c["cards"][0]["training_evidence_ids"] = ["test-00"]
        with self.assertRaisesRegex(ValueError, "evidence"):
            f.validate_cards(c, tr, ts)
        c["cards"][0]["training_evidence_ids"] = [{"unsafe": "dict"}]
        with self.assertRaisesRegex(ValueError, "evidence"):
            f.validate_cards(c, tr, ts)

    def test_test_leak_detected(self):
        m, tr, ts, c = fixture()
        c["cards"][0]["procedure"] = "anything " + ts[0]["prompt"]
        with self.assertRaisesRegex(ValueError, "leaked"):
            f.validate_cards(c, tr, ts)

    def test_origin_annotation(self):
        m, tr, ts, c = fixture()
        c["cards"][0]["origin"] = "human_authored"
        c["cards"][0]["training_evidence_ids"] = []
        self.assertEqual(len(f.validate_cards(c, tr, ts)), 3)
        c["cards"][0]["origin"] = "syn_candidate"
        with self.assertRaisesRegex(ValueError, "needs training evidence"):
            f.validate_cards(c, tr, ts)

    def test_factorial_interaction(self):
        scored = {"study_id": "synthetic", "results_by_arm": {
            a: {"pass_rate": rate} for a, rate in [
                ("baseline", .25), ("journal", .5), ("research", .375), ("skills", .875)]}}
        summary = f.summarize(scored)
        self.assertAlmostEqual(summary["memory_effect_without_skill"], .25)
        self.assertAlmostEqual(summary["memory_effect_with_skill"], .5)
        self.assertAlmostEqual(summary["skill_effect_without_memory"], .125)
        self.assertAlmostEqual(summary["skill_effect_with_memory"], .375)
        self.assertAlmostEqual(summary["interaction"], .25)
        self.assertIn("DESCRIPTIVE_ONLY", summary["interpretation"])

    def test_negative_effect(self):
        scored = {"study_id": "mock", "results_by_arm": {
            a: {"pass_rate": rate} for a, rate in [
                ("baseline", 1), ("journal", 1), ("research", 0), ("skills", 0)]}}
        self.assertEqual(f.summarize(scored)["skill_effect_with_memory"], -1)

    def test_bad_seed(self):
        m, tr, ts, c = fixture()
        with self.assertRaisesRegex(ValueError, "invalid seed"):
            f.build(m, tr, ts, c, seed=True)


    def test_end_to_end_with_real_pack_and_scorer(self):
        """Full existing modules, synthetic responses: no external model used."""
        import json
        import tempfile
        gen = f._module("syn_holdout_pack_v0")
        old = f._module("syn_four_arm_trial_v0")
        score = f._module("syn_skill_transfer_eval_v0")
        with tempfile.TemporaryDirectory() as t:
            pack = Path(t) / "pack"
            gen.build(pack, model_id="frozen-mock-v1", seed=771)
            manifest = old._read_json(pack / "release/manifest.json")
            train = old._read_jsonl(pack / "release/train_examples.jsonl")
            test = old._read_jsonl(pack / "holdout/test_prompts.jsonl")
            cards = {"schema": "syn-factorial-skill-cards-v1", "cards": [
                {"domain": dom, "skill_id": "human-" + dom,
                 "procedure": "Read carefully, check each step, then answer.",
                 "origin": "human_authored", "training_evidence_ids": []}
                for dom in ("arithmetic", "calendar", "graph")]}
            req = f.build(manifest, train, test, cards, seed=33)
            self.assertEqual(len(req), 96)
            attempts = [{"task_id": q["task_id"], "arm": q["arm"],
                         "model_id": q["model_id"], "answer": "synthetic-no-answer",
                         "tokens_used": 1, "skill_ids": q["skill_ids"]} for q in req]
            truth = score._read_jsonl(pack / "sealed/oracle.jsonl")
            outcome = score.evaluate(manifest, truth, attempts)
            self.assertEqual(outcome["n_tasks"], 24)
            self.assertEqual(outcome["results_by_arm"]["research"]["total"], 24)
            self.assertEqual(set(f.summarize(outcome)["accuracy"]), set(f.ARMS))


if __name__ == "__main__":
    unittest.main()
