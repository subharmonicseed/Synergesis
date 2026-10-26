"""Source-retrieval tests, not an evaluation of a language model."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.export_chatgpt_context import SOURCES, export_scene, validate_scene


class PublicSceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        for key, (_kind, path, _description) in SOURCES.items():
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("PUBLIC TEST SOURCE: " + key, encoding="utf-8")

    def test_native_graph_is_connected_and_exports_only_references(self):
        result = export_scene(self.root)
        validate_scene(self.root, result)
        self.assertEqual(len(result["glyphs"]), 7)
        self.assertEqual(len(result["edges"]), 9)
        self.assertEqual({g["schema_version"] for g in result["glyphs"]}, {"synergesis.glyph.v1"})
        ids = {g["glyph_id"]: g["content"]["scene_key"] for g in result["glyphs"]}
        links = {(ids[e["source"]], ids[e["target"]]) for e in result["edges"]}
        self.assertIn(("chatgpt-state", "chatgpt-engine"), links)
        self.assertIn(("chatgpt-engine", "continuity"), links)
        self.assertNotIn("PUBLIC TEST SOURCE", str(result["glyphs"]))

    def test_source_revision_is_detected_before_claiming_fresh_context(self):
        result = export_scene(self.root)
        (self.root / "docs/chatgpt/STATE.md").write_text("changed state", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale scene source"):
            validate_scene(self.root, result)

    def test_missing_or_escaping_source_cannot_be_exported(self):
        file = self.root / "docs/chatgpt/STATE.md"
        file.unlink()
        with self.assertRaises(FileNotFoundError):
            export_scene(self.root)
        outside = Path(self.tmp.name) / "private.txt"
        outside.write_text("NOT FOR EXPORT", encoding="utf-8")
        file.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes"):
            export_scene(self.root)


if __name__ == "__main__":
    unittest.main()
