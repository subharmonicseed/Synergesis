"""
Glyph Module for Archon MCP Server

This module exposes the local Glyph engine (SynkrisisVis) as MCP tools.
It wraps:
- Text analysis to symbolic properties
- Glyph generation (ASCII or SVG)
- Entropy inversion + glyph generation

Notes:
- The Glyph engine lives outside the Archon package under `Syn/Glyph engine/Glyph translator/tool1.py`.
- We dynamically add that path to sys.path to import without copying code.
- No secrets are used; this runs purely locally.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)

# Cached engine instance
_engine: Any | None = None


def _resolve_glyph_module_path() -> Optional[Path]:
    """Resolve the absolute path to the Glyph translator folder containing tool1.py."""
    try:
        # Prefer explicit environment override (works well in Docker / compose)
        env_dir = os.getenv("GLYPH_ENGINE_DIR")
        if env_dir:
            p = Path(env_dir)
            tool = p / "tool1.py"
            if tool.exists():
                return p
        here = Path(__file__).resolve()
        # modules -> mcp -> src -> python -> Archon-main -> BigSyn
        parents = list(here.parents)
        # Guard against shallow path depth in unexpected environments
        if len(parents) < 5:
            return None
        bigsyn_root = parents[5 - 1]  # parents[4] = Archon-main; parents[5] = BigSyn, but 0-indexed
        # Adjust calculation robustly
        # Find the top-level directory that contains "Archon-main" and go one level up
        archon_idx = None
        for i, p in enumerate(parents):
            if p.name == "Archon-main":
                archon_idx = i
                break
        if archon_idx is not None and archon_idx + 1 < len(parents):
            bigsyn_root = parents[archon_idx + 1]
        # Path to Glyph engine
        glyph_dir = bigsyn_root / "Syn" / "Glyph engine" / "Glyph translator"
        tool_path = glyph_dir / "tool1.py"
        if tool_path.exists():
            return glyph_dir
        return None
    except Exception as e:
        logger.error("Failed to resolve Glyph module path: %s", e)
        return None


def _get_engine() -> tuple[Optional[Any], Optional[str]]:
    """Load and cache the SynkrisisVis engine. Returns (engine, error)"""
    global _engine
    if _engine is not None:
        return _engine, None

    glyph_dir = _resolve_glyph_module_path()
    if not glyph_dir:
        return None, "Glyph engine path not found. Expected Syn/Glyph engine/Glyph translator/tool1.py"

    try:
        sys.path.insert(0, str(glyph_dir))
        from tool1 import SynkrisisVis  # type: ignore

        _engine = SynkrisisVis()
        logger.info("Glyph engine initialized from %s", glyph_dir)
        return _engine, None
    except Exception as e:
        logger.exception("Error importing Glyph engine: %s", e)
        return None, f"Failed to import Glyph engine: {e}"


def _sanitize_props_for_engine(props: dict) -> dict:
    """Return a copy of props containing only hashable primitives for engine caching.
    Removes nested dict/list values (e.g., 'metrics') and normalizes numeric fields.
    """
    def _is_primitive(v: Any) -> bool:
        return isinstance(v, (str, int, float, bool)) or v is None

    safe = {k: v for k, v in props.items() if _is_primitive(v)}

    # Normalize numeric fields if present
    if "frequency" in props:
        try:
            safe["frequency"] = int(props["frequency"])  # type: ignore[arg-type]
        except Exception:
            pass
    if "weight" in props:
        try:
            safe["weight"] = int(props["weight"])  # type: ignore[arg-type]
        except Exception:
            pass

    return safe


def register_glyph_tools(mcp: FastMCP) -> None:
    """Register Glyph-related tools with the MCP server."""

    @mcp.tool()
    async def glyph_analyze(text: str, ctx: Context | None = None) -> str:
        """
        Analyze input text into symbolic glyph properties.

        Args:
            text: Text to analyze
        Returns:
            JSON string with { success, properties | error }
        """
        try:
            engine, err = _get_engine()
            if err or engine is None:
                return json.dumps({"success": False, "error": err or "Engine unavailable"}, indent=2)

            props = engine.analyzeText(text)
            if not props:
                return json.dumps({"success": False, "error": "Analysis returned no properties"}, indent=2)

            return json.dumps({"success": True, "properties": props}, indent=2)
        except Exception as e:
            logger.error("glyph_analyze failed: %s", e)
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def glyph_generate(text: str, format: str = "ascii", ctx: Context | None = None) -> str:
        """
        Analyze the text and generate a glyph in the requested format.

        Args:
            text: Text to analyze
            format: 'ascii' or 'svg'
        Returns:
            JSON string with { success, format, glyph, properties | error }
        """
        try:
            engine, err = _get_engine()
            if err or engine is None:
                return json.dumps({"success": False, "error": err or "Engine unavailable"}, indent=2)

            props = engine.analyzeText(text)
            if not props:
                return json.dumps({"success": False, "error": "Analysis returned no properties"}, indent=2)

            fmt = (format or "ascii").lower()
            if fmt not in ("ascii", "svg"):
                fmt = "ascii"

            safe_props = _sanitize_props_for_engine(props)
            glyph_str = engine.generateGlyph(safe_props, format=fmt)
            return json.dumps({
                "success": True,
                "format": fmt,
                "glyph": glyph_str,
                "properties": props,
                "used_properties": safe_props,
            }, indent=2)
        except Exception as e:
            logger.error("glyph_generate failed: %s", e)
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def glyph_invert(properties_json: str, format: str = "ascii", ctx: Context | None = None) -> str:
        """
        Invert symbolic entropy of provided glyph properties and optionally generate a glyph.

        Args:
            properties_json: JSON-encoded glyph properties as produced by glyph_analyze
            format: 'ascii' or 'svg'
        Returns:
            JSON string with { success, inverted_properties, glyph? | error }
        """
        try:
            engine, err = _get_engine()
            if err or engine is None:
                return json.dumps({"success": False, "error": err or "Engine unavailable"}, indent=2)

            try:
                props = json.loads(properties_json)
                if not isinstance(props, dict):
                    raise ValueError("properties_json must be a JSON object")
            except Exception as e:
                return json.dumps({"success": False, "error": f"Invalid properties_json: {e}"}, indent=2)

            inverted = engine.invertEntropy(props)
            if not inverted:
                return json.dumps({"success": False, "error": "Entropy inversion failed"}, indent=2)

            fmt = (format or "ascii").lower()
            if fmt not in ("ascii", "svg"):
                fmt = "ascii"

            safe_inverted = _sanitize_props_for_engine(inverted)
            glyph_str = engine.generateGlyph(safe_inverted, format=fmt)
            return json.dumps({
                "success": True,
                "format": fmt,
                "inverted_properties": inverted,
                "glyph": glyph_str,
                "used_properties": safe_inverted,
            }, indent=2)
        except Exception as e:
            logger.error("glyph_invert failed: %s", e)
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def glyph_fractal_map(
        properties_list_json: str,
        width: int = 800,
        height: int = 600,
        ctx: Context | None = None,
    ) -> str:
        """
        Generate a fractal map SVG from a list of glyph properties.

        Args:
            properties_list_json: JSON array of glyph properties dicts
            width: SVG width
            height: SVG height
        Returns:
            JSON string with { success, svg | error }
        """
        try:
            engine, err = _get_engine()
            if err or engine is None:
                return json.dumps({"success": False, "error": err or "Engine unavailable"}, indent=2)

            try:
                props_list = json.loads(properties_list_json)
                if not isinstance(props_list, list) or not all(isinstance(p, dict) for p in props_list):
                    raise ValueError("properties_list_json must be a JSON array of objects")
            except Exception as e:
                return json.dumps({"success": False, "error": f"Invalid properties_list_json: {e}"}, indent=2)

            # Use a temporary file to capture the SVG output
            tmp_svg = Path(tempfile.gettempdir()) / "synkrisis_map.svg"
            safe_list = [_sanitize_props_for_engine(p) for p in props_list]
            engine.displayFractalMap(safe_list, filename=str(tmp_svg), width=width, height=height)

            svg_text = None
            try:
                svg_text = tmp_svg.read_text(encoding="utf-8")
            except Exception as re:
                return json.dumps({"success": False, "error": f"Failed to read generated SVG: {re}"}, indent=2)

            return json.dumps({"success": True, "svg": svg_text}, indent=2)
        except Exception as e:
            logger.error("glyph_fractal_map failed: %s", e)
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    logger.info("[SUCCESS] Glyph tools registered")
