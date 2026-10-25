"""Bounded bridge from curated Git documents to SYN's existing Glyph Audit Graph.

No conversation import, no model writes, no automatic GitHub access. Git is the
versioned documentary source; GlyphLedger stores local typed provenance and
relationships. This module does NOT implement semantic search or consciousness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger

ACTOR = "SYN-SCENE-BRIDGE"
# Explicit, non-personal, source-controlled documents only. Order is dependency order.
SCENE_DOCS = (
    ("glyph-protocol", "concept", "synergesis_glyph_protocol.py",
     "Actual typed glyph ledger and relationship API"),
    ("scope", "decision", "docs/continuity/2026-10-25-002.md",
     "SYN is the whole cooperation; Synergesis is a technical instrument"),
    ("scaphandre", "concept", "docs/SYN_SCAPHANDRE_ONTOLOGIQUE_V1.md",
     "Orient, estrange, test and inherit without equating agreement and truth"),
    ("frontier", "hypothesis", "docs/SYN_FRONTIERE_DU_POSSIBLE_V1.md",
     "Transformation of possible actions is an untested hypothesis"),
    ("continuity", "decision", "docs/SYN_AGENT_CONTINUITY.md",
     "Explicit decisions, objections, open hypotheses and status"),
)

# The edges preserve conceptual provenance, NOT logical proof.
DEPENDS_ON = {
    "scaphandre": ("scope",),
    "frontier": ("scaphandre",),
    "continuity": ("scope", "scaphandre", "frontier", "glyph-protocol"),
}

ALIASES = {
    "syn": "scope",
    "glyph": "glyph-protocol",
    "glyphes": "glyph-protocol",
    "feu": "continuity",
    "possibilite": "frontier",
    "possible": "frontier",
}
DOC_KEYS = frozenset(item[0] for item in SCENE_DOCS)


def _paths(repo_root: str | Path, ledger_path: str | Path) -> tuple[Path, Path]:
    root = Path(repo_root).expanduser().resolve(strict=True)
    ledger = Path(ledger_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("repo root is not a directory")
    if ledger.is_relative_to(root):
        raise ValueError("glyph ledger must stay outside the Git repository")
    if Path(ledger_path).expanduser().is_symlink():
        raise ValueError("symlink ledger is not allowed")
    return root, ledger


def _read_curated(root: Path, relative_path: str) -> tuple[str, str]:
    path = root / relative_path
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("source path escapes repository")
    data = path.read_bytes()
    if len(data) > 200_000:
        raise ValueError("curated document over size limit")
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def _ref(key: str) -> str:
    return "syn-scene:" + key


def _current(graph: GlyphAuditGraph, key: str):
    matches = graph.ledger.find_by_external_ref(_ref(key))
    return matches[-1] if matches else None


def ingest_scene(repo_root: str | Path, ledger_path: str | Path) -> dict[str, Any]:
    """Record a bounded, versioned scene in an existing local GlyphLedger.

    Each document version is idempotent, and revisions supersede old glyphs.
    Documents are not copied into the ledger; only curated descriptions and
    SHA-256 source receipts are recorded.
    """
    root, ledger = _paths(repo_root, ledger_path)
    # Prevalidate all documents before writing any event.
    sources = {
        key: (kind, rel, description, *_read_curated(root, rel))
        for key, kind, rel, description in SCENE_DOCS
    }
    graph = GlyphAuditGraph(GlyphLedger(ledger))
    ids = {}
    new_count = 0
    for key, (kind, rel, description, _text, digest) in sources.items():
        version_ref = f"{_ref(key)}:sha256:{digest}"
        previous = _current(graph, key)
        existed = graph.ledger.find_by_external_ref(version_ref, glyph_type=kind)
        glyph = graph.create(
            kind,
            actor=ACTOR,
            content={
                "kind": "curated_git_scene_reference",
                "scene_key": key,
                "description": description,
                "source_path": rel,
                "source_sha256": digest,
                "epistemic_status": "hypothesis_not_tested" if kind == "hypothesis"
                                    else "curated_document_not_empirical_proof",
            },
            external_refs=(_ref(key), version_ref),
            dedupe_external_ref=version_ref,
        )
        ids[key] = glyph.glyph_id
        if not existed:
            new_count += 1
            if previous is not None and previous.glyph_id != glyph.glyph_id:
                graph.relate(glyph.glyph_id, previous.glyph_id, "supersedes",
                             actor=ACTOR, metadata={"scope": "document_revision"})
    for child, parents in DEPENDS_ON.items():
        for parent in parents:
            graph.relate(ids[child], ids[parent], "derived_from", actor=ACTOR,
                         metadata={"scope": "curated_scene_link_not_proof"})
    # The ledger validates hash-chain integrity when reading; do not assert
    # that integrity certifies the truth or completeness of referenced claims.
    graph.ledger.verify()
    return {"indexed": list(ids), "new_versions": new_count, "ledger": str(ledger)}


def recall_scene(repo_root: str | Path, ledger_path: str | Path, focus: str,
                 max_chars_per_source: int = 1200) -> dict[str, Any]:
    """Retrieve relevant typed glyph ancestors and verified source excerpts.

    No implicit semantic similarity: focus keys and aliases are deliberately
    explicit. Missing/changed sources fail closed, rather than fabricating memory.
    """
    root, ledger = _paths(repo_root, ledger_path)
    key = ALIASES.get(focus.lower(), focus.lower())
    if key not in DOC_KEYS:
        raise ValueError("unknown scene focus (no speculative recall): " + focus)
    if not 1 <= max_chars_per_source <= 5_000:
        raise ValueError("max_chars_per_source must be 1..5000")
    if not ledger.is_file():
        raise FileNotFoundError("no local glyph ledger; run ingest first")
    graph = GlyphAuditGraph(GlyphLedger(ledger))
    focal = _current(graph, key)
    if focal is None:
        raise LookupError("focus not indexed: " + key)
    trace = graph.upstream(focal.glyph_id, max_depth=12)
    nodes = []
    for glyph in trace.glyphs:
        if glyph.content.get("kind") != "curated_git_scene_reference":
            continue
        rel = glyph.content["source_path"]
        body, digest = _read_curated(root, rel)
        if digest != glyph.content["source_sha256"]:
            # Historical glyphs may refer to earlier file versions. Do not
            # silently present newer content as evidence for an older version.
            if glyph.glyph_id == _current(graph, glyph.content["scene_key"]).glyph_id:
                raise ValueError("scene source changed; re-ingest first: " + rel)
            excerpt = None
            status = "historical_source_not_in_current_checkout"
        else:
            excerpt = body[:max_chars_per_source]
            status = "source_digest_verified"
        nodes.append({
            "glyph_id": glyph.glyph_id,
            "scene_key": glyph.content["scene_key"],
            "glyph_type": glyph.glyph_type,
            "path": rel,
            "sha256": glyph.content["source_sha256"],
            "status": status,
            "excerpt": excerpt,
        })
    return {
        "focus": key,
        "focal_glyph_id": focal.glyph_id,
        "nodes": nodes,
        "relations": [
            {"source": e.source, "relation": e.relation, "target": e.target}
            for e in trace.edges
        ],
        "warning": "Git receipts verify file identity, not the truth of claims. "
                   "This is bounded graph retrieval, not general semantic memory.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ingest", "recall"))
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--ledger", required=True, help="private path OUTSIDE the repository")
    parser.add_argument("--focus", default="syn",
                        help="syn, scaphandre, frontier, glyph, feu, continuity")
    args = parser.parse_args()
    if args.command == "ingest":
        result = ingest_scene(args.repo_root, args.ledger)
    else:
        result = recall_scene(args.repo_root, args.ledger, args.focus)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
