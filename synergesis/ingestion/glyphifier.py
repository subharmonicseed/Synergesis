"""Convert text into glyphs using an LLM backend."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from ..llm_interface.backends import get_llm
from ..llm_interface.prompts import GLYPH_PROMPT_TECH_V1_1
from ..glyph_core import GlyphData


def validate_glyph_structure(glyph_dict: Dict[str, Any]) -> bool:
    """Placeholder validation for glyph dictionaries."""
    return isinstance(glyph_dict, dict) and "id" in glyph_dict


def glyphify_sleep_phase(
    raw_ctx: str,
    parent_doc_id: str,
    source_chunk_index: int,
    approx_timestamp_str: str,
    llm_name: str = "stub",
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Glyphify a text chunk using the specified LLM backend."""
    ctx_hash = hashlib.sha256(raw_ctx.encode("utf-8")).hexdigest()
    prompt = GLYPH_PROMPT_TECH_V1_1.format(
        text_input=raw_ctx,
        source_doc_id_param=parent_doc_id,
        chunk_index_param=source_chunk_index,
    )
    backend = get_llm(llm_name, llm_config or {})
    response = backend.generate(prompt, max_tokens=512)
    try:
        glyphs = json.loads(response)
    except json.JSONDecodeError:
        glyphs = []
    validated: List[GlyphData] = []
    for g in glyphs:
        if validate_glyph_structure(g):
            g.setdefault("timestamp", time.time())
            g.setdefault("sourceIds", []).append(parent_doc_id)
            g.setdefault("status", "generated_from_llm")
            validated.append(g)
    return {"glyphs": validated, "ctx_hash": ctx_hash}
