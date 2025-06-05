"""Graph analysis helpers built on Neo4jInterface."""
from __future__ import annotations

from typing import Any, Dict, List

from ..glyph_core import GlyphData
from ..storage.neo4j_interface import Neo4jInterface


class TopologyEngine:
    """High level operations on glyph topology stored in Neo4j."""

    def __init__(self, neo4j: Neo4jInterface) -> None:
        self.neo4j = neo4j

    def summarize_glyph(self, glyph_id: str) -> Dict[str, Any]:
        return {}

    def build_glyph_graph(self, glyphs: List[GlyphData]) -> Any:
        return None

    def get_neighbors(self, glyph_id: str) -> List[str]:
        return []

    def find_reflective_links(self, glyph_id: str) -> List[str]:
        return []

    def compute_symbolic_distance_v2(self, g1: GlyphData, g2: GlyphData) -> float:
        return 0.0
