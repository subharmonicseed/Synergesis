"""Regression tests for the bounded Git ↔ Glyph scene bridge."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synergesis_scene_glyph_bridge import (
    SCENE_DOCS, ingest_scene, recall_scene,
)
from synergesis_glyph_protocol import GlyphLedger


class SceneBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.ledger = self.base / "private" / "scene.jsonl"
        for key, _kind, relative, _summary in SCENE_DOCS:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("curated: " + key, encoding="utf-8")

    def test_ingest_is_idempotent_and_returns_related_sources(self):
        first = ingest_scene(self.root, self.ledger)
        second = ingest_scene(self.root, self.ledger)
        self.assertEqual(first["new_versions"], len(SCENE_DOCS))
        self.assertEqual(second["new_versions"], 0)
        self.assertEqual(len(GlyphLedger(self.ledger).glyphs()), len(SCENE_DOCS))
        recalled = recall_scene(self.root, self.ledger, "possible")
        self.assertEqual(recalled["focus"], "frontier")
        self.assertEqual(
            {n["scene_key"] for n in recalled["nodes"]},
            {"frontier", "scaphandre", "scope"},
        )
        self.assertEqual(len(recalled["relations"]), 2)
        self.assertTrue(all(
            n["status"] == "source_digest_verified" for n in recalled["nodes"]
        ))

    def test_supersedes_document_revision_without_erasing_history(self):
        ingest_scene(self.root, self.ledger)
        (self.root / "docs/SYN_FRONTIERE_DU_POSSIBLE_V1.md").write_text(
            "curated: frontier, version 2", encoding="utf-8"
        )
        refreshed = ingest_scene(self.root, self.ledger)
        self.assertEqual(refreshed["new_versions"], 1)
        recalled = recall_scene(self.root, self.ledger, "frontier")
        self.assertEqual(
            {n["status"] for n in recalled["nodes"]},
            {"source_digest_verified", "historical_source_not_in_current_checkout"},
        )
        self.assertIn("supersedes", {e["relation"] for e in recalled["relations"]})
        self.assertEqual(len(GlyphLedger(self.ledger).glyphs()), len(SCENE_DOCS) + 1)

    def test_stale_source_fails_closed_before_reingestion(self):
        ingest_scene(self.root, self.ledger)
        (self.root / "docs/SYN_FRONTIERE_DU_POSSIBLE_V1.md").write_text(
            "changed without re-ingestion", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "re-ingest"):
            recall_scene(self.root, self.ledger, "frontier")

    def test_invalid_focus_and_ledger_inside_repo_are_rejected(self):
        ingest_scene(self.root, self.ledger)
        with self.assertRaisesRegex(ValueError, "unknown scene focus"):
            recall_scene(self.root, self.ledger, "entire private history")
        with self.assertRaisesRegex(ValueError, "outside"):
            ingest_scene(self.root, self.root / "tracked-ledger.jsonl")

    def test_missing_source_does_not_create_partial_graph(self):
        (self.root / "docs/SYN_AGENT_CONTINUITY.md").unlink()
        with self.assertRaises(FileNotFoundError):
            ingest_scene(self.root, self.ledger)
        self.assertFalse(self.ledger.exists())


if __name__ == "__main__":
    unittest.main()
