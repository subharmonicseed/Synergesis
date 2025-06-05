from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Dict, List, Optional

from synergesis.llm_interface.backends import get_llm

try:
    from synergesis.llm_interface.prompts import GLYPH_PROMPT_TECH_V1_1
except Exception:  # pragma: no cover - fallback for missing module
    GLYPH_PROMPT_TECH_V1_1 = (
        "Given the following context, output a JSON list of glyph objects:\n{context}"
    )

GlyphData = Dict[str, Any]


def glyphify_sleep_phase(
    raw_ctx: str,
    parent_doc_id: str,
    source_chunk_index: int,
    approx_timestamp_str: str,
    *,
    llm_name: str = "tiny",
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate glyphs from a context string using an LLM backend."""
    ctx_hash = sha256(raw_ctx.encode()).hexdigest()
    prompt = GLYPH_PROMPT_TECH_V1_1.format(context=raw_ctx)
    llm = get_llm(llm_name, **(llm_config or {}))
    response = llm.generate(prompt, max_tokens=256)
    try:
        data = json.loads(response)
        if not isinstance(data, list):
            raise ValueError("LLM response is not a list")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    glyphs: List[GlyphData] = []
    for idx, glyph in enumerate(data, start=1):
        if not isinstance(glyph, dict):
            continue
        glyph_id = glyph.get("id") or f"auto-{idx}"
        glyph["id"] = glyph_id
        glyph["timestamp"] = approx_timestamp_str
        glyph["sourceIds"] = [parent_doc_id]
        glyph["status"] = "from_llm"
        glyphs.append(glyph)

    return {"glyphs": glyphs, "ctx_hash": ctx_hash}


__all__ = ["glyphify_sleep_phase", "GlyphData"]
