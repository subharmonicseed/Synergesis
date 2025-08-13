"""Minimal stub that converts an LLM response into a GlyphData-compatible dict.
Replace the dummy implementation once real prompt engineering is defined.
"""

from typing import Any, Dict
import uuid
import time

# If the full GlyphData model is available, import; else use dict.
try:
    from models.glyph import Glyph as GlyphData  # fallback to existing model
except Exception:  # pragma: no cover
    GlyphData = Dict[str, Any]  # type: ignore


def response_to_glyph(llm_response: str) -> GlyphData:  # type: ignore[override]
    """Convert a plain LLM string response into a minimal GlyphData.
    Currently returns placeholder values so that downstream code can run.
    """
    dummy_payload = {
        "id": f"glyph_{uuid.uuid4()}",
        "timestamp": int(time.time()),
        "source": "ai_to_glyph",
        "concept_type": "text_chunk",
        "status": "generated",
        "polarité": "?",
        "alignement": "void",
        "content": llm_response[:256],
        "metadata": {"original_response_length": len(llm_response)}
    }
    try:
        return GlyphData(**dummy_payload)  # type: ignore[arg-type]
    except Exception:
        # If GlyphData import failed, return raw dict
        return dummy_payload
