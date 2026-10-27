"""Offline stdlib tests; synthetic answers verify arithmetic, not SYN competence."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("syn_eval", Path(__file__).with_name("syn_skill_transfer_eval_v0.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def data():
    manifest = {
        "schema": "syn-skill-transfer-eval-v0",
        "study_id": "synthetic-fixture-not-real-results",
        "model_id": "frozen-mock-0",
        "arms": ["baseline", "journal", "research", "skills"],
        "train_task_ids": ["train-1"],
        "test_tasks": [{"task_id": f"{d}{i}", "domain": d} for d in "ab" for i in range(1, 3)],
        "token_budget_per_arm": 200,
    }
    truth = [{"task_id": x["task_id"], "answer": "Y"} for x in manifest["test_tasks"]]
    by_arm = {
        "baseline": [1, 0, 1, 0],
        "journal": [1, 0, 1, 0],
        "research": [1, 1, 0, 0],
        "skills": [1, 1, 0, 1],
    }
    attempts = []
    for arm, correctness in by_arm.items():
        for task, passed in zip(manifest["test_tasks"], correctness):
            attempts.append({"task_id": task["task_id"], "arm": arm,
                             "model_id": "frozen-mock-0", "answer": "Y" if passed else "N",
                             "tokens_used": 10, "skill_ids": ["sk-1"] if arm == "skills" else []})
    return manifest, truth, attempts


class Tests(unittest.TestCase):
    def test_paired_and_regressions(self):
        m, o, a = data()
        x = mod.evaluate(m, o, a)
        self.assertEqual(x["paired_gain_skills_minus_baseline"], 0.25)
        self.assertEqual(x["repaired_tasks"], ["a2", "b2"])
        self.assertEqual(x["regressed_tasks"], ["b1"])
        self.assertEqual(x["skill_id_domains_observed"]["sk-1"], ["a", "b"])
        self.assertIn("DESCRIPTIVE_ONLY", x["claims"])

    def test_train_leak(self):
        m, o, a = data()
        m["train_task_ids"].append("a1")
        with self.assertRaisesRegex(mod.EvaluationError, "leakage"):
            mod.evaluate(m, o, a)

    def test_duplicate(self):
        m, o, a = data()
        with self.assertRaisesRegex(mod.EvaluationError, "duplicate"):
            mod.evaluate(m, o, a + [a[0]])

    def test_missing_arm(self):
        m, o, a = data()
        with self.assertRaisesRegex(mod.EvaluationError, "all tasks"):
            mod.evaluate(m, o, a[:-1])

    def test_model_mismatch(self):
        m, o, a = data()
        a[0]["model_id"] = "other"
        with self.assertRaisesRegex(mod.EvaluationError, "model"):
            mod.evaluate(m, o, a)

    def test_budget(self):
        m, o, a = data()
        m["token_budget_per_arm"] = 39
        with self.assertRaisesRegex(mod.EvaluationError, "budget"):
            mod.evaluate(m, o, a)

    def test_fake_oracle_and_missing(self):
        m, o, a = data()
        with self.assertRaisesRegex(mod.EvaluationError, "incomplete oracle"):
            mod.evaluate(m, o[:-1], a)
        o[0]["answer"] = False
        with self.assertRaisesRegex(mod.EvaluationError, "oracle answer"):
            mod.evaluate(m, o, a)

    def test_banned_skills_in_control(self):
        m, o, a = data()
        a[0]["skill_ids"] = ["secret-skill"]
        with self.assertRaisesRegex(mod.EvaluationError, "outside"):
            mod.evaluate(m, o, a)

    def test_invalid_attempt_token_boolean(self):
        m, o, a = data()
        a[0]["tokens_used"] = True
        with self.assertRaisesRegex(mod.EvaluationError, "tokens_used"):
            mod.evaluate(m, o, a)

    def test_invalid_domains(self):
        m, o, a = data()
        for t in m["test_tasks"]:
            t["domain"] = "a"
        with self.assertRaisesRegex(mod.EvaluationError, "two test domains"):
            mod.evaluate(m, o, a)

    def test_no_wrong_claim_on_zero(self):
        m, o, a = data()
        for row in a:
            if row["arm"] == "skills":
                row["answer"] = "N"
        x = mod.evaluate(m, o, a)
        self.assertEqual(x["paired_gain_skills_minus_baseline"], -.5)
        self.assertEqual(x["repaired_tasks"], [])
        self.assertEqual(x["regressed_tasks"], ["a1", "b1"])


if __name__ == "__main__":
    unittest.main()
