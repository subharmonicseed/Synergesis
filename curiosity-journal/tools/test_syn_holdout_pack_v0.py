"""Checks for toy challenge generator; NOT agent capability scores."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("pack", Path(__file__).with_name("syn_holdout_pack_v0.py"))
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


class GeneratorTests(unittest.TestCase):
    def test_three_domains_and_holdout_separation(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "pilot"
            result = pack.build(out, per_domain_train=5, per_domain_test=7, seed=789, model_id="frozen-fixture")
            self.assertEqual((result["n_train"], result["n_test"]), (15, 21))
            train = [json.loads(x) for x in (out / "release/train_examples.jsonl").read_text().splitlines()]
            test = [json.loads(x) for x in (out / "holdout/test_prompts.jsonl").read_text().splitlines()]
            oracle = [json.loads(x) for x in (out / "sealed/oracle.jsonl").read_text().splitlines()]
            self.assertEqual(len({t["prompt"] for t in train + test}), 36)
            self.assertEqual({x["domain"] for x in test}, set(pack.DOMAINS))
            self.assertTrue(all("answer" not in x for x in test))
            self.assertTrue(all("prompt" not in x for x in oracle))
            self.assertTrue(all("answer" in x for x in train))
            self.assertEqual({x["task_id"] for x in test}, {x["task_id"] for x in oracle})
            self.assertNotIn("oracle", (out / "release/manifest.json").read_text())

    def test_reproducible_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            x, y = Path(root) / "a", Path(root) / "b"
            pack.build(x, seed=17)
            pack.build(y, seed=17)
            for directory, filename in [("release", "train_examples.jsonl"),
                                        ("holdout", "test_prompts.jsonl"), ("sealed", "oracle.jsonl")]:
                self.assertEqual((x / directory / filename).read_bytes(),
                                 (y / directory / filename).read_bytes())

    def test_no_clobber(self):
        with tempfile.TemporaryDirectory() as root:
            x = Path(root) / "pack"
            pack.build(x, seed=7)
            with self.assertRaises(FileExistsError):
                pack.build(x, seed=9)

    def test_invalid_sizes(self):
        with tempfile.TemporaryDirectory() as root:
            for val in (0, -1, 501):
                with self.assertRaises(ValueError):
                    pack.build(Path(root) / "x", per_domain_test=val)

    def test_graph_oracle(self):
        self.assertEqual(pack._answer_graph([("A", "B"), ("B", "C")], "A", "C"), "YES")
        self.assertEqual(pack._answer_graph([("A", "B")], "A", "C"), "NO")

    def test_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            x = Path(root) / "pack"
            pack.build(x, seed=7)
            self.assertEqual((x / "sealed/oracle.jsonl").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
