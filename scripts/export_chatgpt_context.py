"""Export public source references with SYN's native glyph classes; no model call.

Run scene export on POSIX (the existing ledger lock requires fcntl). Journal
indexing and receipt checking also work on Windows. Neither mode reads profiles,
transcripts, environment variables or arbitrary repository files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from synergesis_glyph_protocol import Glyph, GlyphEdge, GlyphAuditGraph, GlyphLedger, to_wire
from synergesis_scene_glyph_bridge import SCENE_DOCS, ingest_scene

EXTRA_DOCS = (
    ("chatgpt-engine", "decision", "docs/SYN_CHATGPT_ENGINE_V1.md",
     "ChatGPT is the selected reasoning engine; dialogue is the default mode"),
    ("chatgpt-state", "decision", "docs/chatgpt/STATE.md",
     "Compact current decisions, negative results and unresolved objections"),
)
SOURCES = {key: (kind, path, description)
           for key, kind, path, description in (*SCENE_DOCS, *EXTRA_DOCS)}


def receipt(root: Path, path: str) -> dict:
    source = root / path
    if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
        raise ValueError("source escapes root")
    data = source.read_bytes()
    if len(data) > 200_000:
        raise ValueError("source exceeds bound")
    data.decode("utf-8")
    return {"path": path, "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha": hashlib.sha1(
                b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()}


def export_scene(root: Path) -> dict:
    sources = {key: receipt(root, source[1]) for key, source in SOURCES.items()}
    # Fresh public projection, not an import/export of any user's runtime ledger.
    with tempfile.TemporaryDirectory(prefix="syn-public-scene-") as tmp:
        ledger_path = Path(tmp) / "scene.jsonl"
        ingest_scene(root, ledger_path)
        graph = GlyphAuditGraph(GlyphLedger(ledger_path))
        ids = {g.content["scene_key"]: g.glyph_id for g in graph.ledger.glyphs()}
        for key, kind, path, description in EXTRA_DOCS:
            g = graph.create(kind, actor="SYN-CHATGPT-PUBLIC-CONTEXT",
                content={"kind": "curated_git_scene_reference", "scene_key": key,
                         "description": description, "source_path": path,
                         "source_sha256": sources[key]["sha256"],
                         "epistemic_status": "design_decision_not_performance_evidence"},
                external_refs=("syn-scene:" + key,))
            ids[key] = g.glyph_id
        for child, parent in (("chatgpt-engine", "continuity"),
                              ("chatgpt-engine", "glyph-protocol"),
                              ("chatgpt-state", "chatgpt-engine")):
            graph.relate(ids[child], ids[parent], "derived_from",
                         actor="SYN-CHATGPT-PUBLIC-CONTEXT",
                         metadata={"scope": "editorial_dependency_not_empirical_proof"})
        graph.ledger.verify()
        result = {"schema": "syn-chatgpt-context-v1",
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "scope": "public_documentary_projection_only",
                  "sources": sources,
                  "glyphs": [to_wire(g) for g in graph.ledger.glyphs()],
                  "edges": [to_wire(e) for e in graph.ledger.edges()],
                  "limits": ["No private conversation or runtime profile imported",
                             "File identity is not claim truth or cognitive improvement",
                             "Fresh projection; earlier snapshots remain in Git history"]}
    validate_scene(root, result)
    return result


def validate_scene(root: Path, snapshot: dict) -> None:
    if (snapshot.get("schema") != "syn-chatgpt-context-v1"
            or snapshot.get("scope") != "public_documentary_projection_only"
            or set(snapshot.get("sources", {})) != set(SOURCES)):
        raise ValueError("invalid public scene")
    for key, source in SOURCES.items():
        if snapshot["sources"][key] != receipt(root, source[1]):
            raise ValueError("stale scene source: " + key)
    glyphs = [Glyph(**g) for g in snapshot["glyphs"]]
    if (len(glyphs) != len(SOURCES) or
            {g.content.get("scene_key") for g in glyphs} != set(SOURCES)):
        raise ValueError("unexpected scene glyphs")
    ids = set()
    for glyph in glyphs:
        key = glyph.content["scene_key"]
        kind, path, _ = SOURCES[key]
        if (glyph.glyph_id in ids or glyph.glyph_type != kind or
                glyph.content.get("kind") != "curated_git_scene_reference" or
                glyph.content.get("source_path") != path or
                glyph.content.get("source_sha256") != snapshot["sources"][key]["sha256"]):
            raise ValueError("invalid source glyph")
        ids.add(glyph.glyph_id)
    for raw in snapshot["edges"]:
        edge = GlyphEdge(**raw)
        if edge.source not in ids or edge.target not in ids or edge.relation != "derived_from":
            raise ValueError("invalid public scene relation")


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def export_journal(root: Path, commit: str) -> dict:
    from synergesis_curiosity_observatory import MAX_ENTRY_BYTES, MAX_RECORDS, validate_entry
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("a pinned source commit is required")
    directory = root / "curiosity-journal/entries"
    paths = sorted(directory.glob("*.json"))
    if not 1 <= len(paths) <= MAX_RECORDS:
        raise ValueError("missing or oversized public journal")
    entries, seen, domains = [], set(), Counter()
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("journal path escapes root")
        raw = path.read_bytes()
        if len(raw) > MAX_ENTRY_BYTES:
            raise ValueError("journal entry too large")
        entry = validate_entry(json.loads(raw, object_pairs_hook=unique_object))
        if entry["entry_id"] in seen:
            raise ValueError("duplicate entry ID")
        seen.add(entry["entry_id"])
        domains[entry["domain"]] += 1
        question = entry["question"]
        relative = path.relative_to(root).as_posix()
        entries.append({"entry_id": entry["entry_id"], "observed_at": entry["observed_at"],
                        "domain": entry["domain"], "question_excerpt": question[:180],
                        "question_truncated": len(question) > 180,
                        "outcome_reported": entry["outcome"],
                        **receipt(root, relative)})
    return {"schema": "syn-chatgpt-journal-index-v1",
            "source_repository": "subharmonicseed/Synergesis",
            "source_branch": "feat/syn-curiosity-observatory-v0",
            "source_commit": commit, "count": len(entries),
            "source_url": "https://github.com/subharmonicseed/Synergesis/tree/" + commit
                          + "/curiosity-journal/entries",
            "validation_scope": "entry schema, uniqueness and local source bytes only; cited studies not reverified",
            "domains": dict(sorted(domains.items())), "entries": entries}


def save(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_journal_bundle(root: Path, journal: dict):
    """Keep the entry-point index small; load at most one page when resuming."""
    index = {key: value for key, value in journal.items() if key not in {"entries", "domains"}}
    index["pages"] = []
    for offset in range(0, len(journal["entries"]), 12):
        entries = journal["entries"][offset:offset + 12]
        relative = f"docs/chatgpt/journal-pages/{offset // 12 + 1:02d}.json"
        save(root / relative, {"schema": "syn-chatgpt-journal-page-v1",
                             "source_commit": journal["source_commit"], "entries": entries})
        index["pages"].append({"count": len(entries), "first_entry": entries[0]["entry_id"],
                              "last_entry": entries[-1]["entry_id"],
                              "domains": sorted({entry["domain"] for entry in entries}),
                              **receipt(root, relative)})
    save(root / "docs/chatgpt/journal-index.json", index)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("scene", "journal", "check"))
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--journal-root", type=Path)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    root = args.repo_root.resolve(strict=True)
    if args.mode == "scene":
        result = export_scene(root)
        save(root / "docs/chatgpt/scene.json", result)
        print(f"Exported {len(result['glyphs'])} native glyphs and {len(result['edges'])} relations")
    elif args.mode == "journal":
        if not args.journal_root or not args.source_commit:
            parser.error("journal requires --journal-root and --source-commit")
        result = export_journal(args.journal_root.resolve(strict=True), args.source_commit)
        save_journal_bundle(root, result)
        print(f"Indexed {result['count']} public entries at {args.source_commit}")
    else:
        validate_scene(root, json.loads((root / "docs/chatgpt/scene.json").read_text(encoding="utf-8")))
        print("All scene source receipts match current files")


if __name__ == "__main__":
    main()
