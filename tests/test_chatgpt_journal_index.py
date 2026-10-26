"""The index must not silently normalize duplicate or invalid research reports."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.export_chatgpt_context import ROOT, export_journal, save_journal_bundle


class JournalIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / "curiosity-journal/entries"
        self.directory.mkdir(parents=True)
        self.raw = (ROOT / "curiosity-journal/entries/2026-10-25-01.json").read_bytes()
        self.path = self.directory / "one.json"
        self.path.write_bytes(self.raw)

    def test_index_is_bounded_and_labels_claims_as_reported(self):
        result = export_journal(self.root, "a" * 40)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["source_commit"], "a" * 40)
        entry = result["entries"][0]
        self.assertLessEqual(len(entry["question_excerpt"]), 180)
        self.assertIn("outcome_reported", entry)
        self.assertNotIn("learning", entry)
        self.assertEqual(len(entry["git_blob_sha"]), 40)
        save_journal_bundle(self.root, result)
        index = json.loads((self.root / "docs/chatgpt/journal-index.json").read_text(encoding="utf-8"))
        self.assertNotIn("entries", index)
        page = json.loads((self.root / index["pages"][0]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(page["entries"], result["entries"])

    def test_duplicate_identity_is_not_counted_twice(self):
        (self.directory / "two.json").write_bytes(self.raw)
        with self.assertRaisesRegex(ValueError, "duplicate entry ID"):
            export_journal(self.root, "a" * 40)

    def test_invalid_report_or_ambiguous_json_is_rejected(self):
        value = json.loads(self.raw)
        value["metrics"]["uncertainty"] = True
        self.path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError):
            export_journal(self.root, "a" * 40)
        self.path.write_text('{"schema": "a", "schema": "b"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            export_journal(self.root, "a" * 40)


if __name__ == "__main__":
    unittest.main()
