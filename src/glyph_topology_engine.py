import logging
from typing import List, Dict, Any, Optional

import networkx as nx
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

GlyphData = Dict[str, Any]

logger_topo = logging.getLogger("GlyphTopologyEngine")

WEIGHTS_DISTANCE = {
    'polarity': 0.25,
    'alignment': 0.25,
    'frequency': 0.15,
    'weight': 0.10,
    'entropy': 0.10,
    'tags': 0.15,
}

DEFAULT_ATTRS = {
    'fréquence': 72,
    'poids': 5,
    'entropy_score': 0.5,
    'resonance': 50,
    'emergence': 360,
}

MIN_CLUSTER_SIZE = 3


def _normalize(value: float, min_v: float, max_v: float) -> float:
    if max_v == min_v:
        return 0.0
    return max(0.0, min(1.0, (float(value) - min_v) / (max_v - min_v)))


def _get_dominant_property_for_translate(prop_value, prop_type: str) -> str:
    if isinstance(prop_value, str):
        return prop_value
    if isinstance(prop_value, list) and prop_value:
        return str(prop_value[0])
    if isinstance(prop_value, dict) and prop_value:
        return max(prop_value, key=prop_value.get)
    return 'Error'


def _calculate_polarity_distance(p1_val, p2_val) -> float:
    p1 = _get_dominant_property_for_translate(p1_val, 'polarity')
    p2 = _get_dominant_property_for_translate(p2_val, 'polarity')
    return 0.0 if p1 == p2 else 1.0


def _calculate_alignment_distance(a1_val, a2_val) -> float:
    a1 = _get_dominant_property_for_translate(a1_val, 'alignment')
    a2 = _get_dominant_property_for_translate(a2_val, 'alignment')
    return 0.0 if a1 == a2 else 1.0


def compute_symbolic_distance(
    g1: GlyphData,
    g2: GlyphData,
    tfidf_vectorizer: Optional[TfidfVectorizer] = None,
    tfidf_matrix: Optional[Any] = None,
    glyph_indices: Optional[Dict[str, int]] = None,
) -> float:
    """Computes a weighted symbolic distance between two glyphs."""
    total_distance = 0.0
    total_weight = 0.0

    pol_dist = _calculate_polarity_distance(g1.get('polarité'), g2.get('polarité'))
    total_distance += pol_dist * WEIGHTS_DISTANCE['polarity']
    total_weight += WEIGHTS_DISTANCE['polarity']

    aln_dist = _calculate_alignment_distance(g1.get('alignement'), g2.get('alignement'))
    total_distance += aln_dist * WEIGHTS_DISTANCE['alignment']
    total_weight += WEIGHTS_DISTANCE['alignment']

    for prop, weight, rng in [
        ('fréquence', WEIGHTS_DISTANCE['frequency'], (1, 144)),
        ('poids', WEIGHTS_DISTANCE['weight'], (1, 10)),
        ('entropy_score', WEIGHTS_DISTANCE['entropy'], (0.0, 1.0)),
    ]:
        v1 = g1.get(prop, DEFAULT_ATTRS[prop])
        v2 = g2.get(prop, DEFAULT_ATTRS[prop])
        norm_dist = abs(_normalize(v1, *rng) - _normalize(v2, *rng))
        total_distance += norm_dist * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return total_distance / total_weight


def build_glyph_graph(
    glyphs: List[GlyphData],
    distance_threshold: float = 0.4,
    include_similarity_edges: bool = True,
) -> nx.Graph:
    """Constructs a simple glyph topology graph."""
    G = nx.Graph()
    for glyph in glyphs:
        if 'id' in glyph:
            G.add_node(glyph['id'])

    if include_similarity_edges:
        for i in range(len(glyphs)):
            for j in range(i + 1, len(glyphs)):
                if 'id' not in glyphs[i] or 'id' not in glyphs[j]:
                    continue
                dist = compute_symbolic_distance(glyphs[i], glyphs[j])
                if dist < distance_threshold:
                    G.add_edge(glyphs[i]['id'], glyphs[j]['id'])
    return G


def compute_resonance_band(glyph: GlyphData) -> int:
    """Return an index representing the resonance band of the glyph."""
    try:
        res = float(glyph.get('resonance', DEFAULT_ATTRS['resonance']))
    except (TypeError, ValueError):
        res = DEFAULT_ATTRS['resonance']

    if res < 40:
        return 0
    if res < 75:
        return 1
    return 2


def cluster_glyphs(glyphs: List[GlyphData], strategy: str = 'alignment_polarity') -> Dict[str, List[str]]:
    """Groups glyphs into clusters based on a chosen strategy."""
    clusters: Dict[str, List[str]] = {}
    if not glyphs:
        return clusters

    for glyph in glyphs:
        if 'id' not in glyph:
            continue
        cluster_key = 'Unclustered'
        if strategy == 'alignment':
            cluster_key = f"Align: {_get_dominant_property_for_translate(glyph.get('alignement'), 'alignment')}"
        elif strategy == 'polarity':
            cluster_key = f"Pol: {_get_dominant_property_for_translate(glyph.get('polarité'), 'polarity')}"
        elif strategy == 'alignment_polarity':
            cluster_key = f"{_get_dominant_property_for_translate(glyph.get('alignement'), 'alignment')} / {_get_dominant_property_for_translate(glyph.get('polarité'), 'polarity')}"
        elif strategy == 'resonance_band':
            idx = compute_resonance_band(glyph)
            band = ['Low-Res', 'Mid-Res', 'High-Res'][idx]
            cluster_key = f"Res: {band}"
        elif strategy == 'stability':
            cluster_key = f"Stab: {glyph.get('stability', 'MEDIUM')}"

        clusters.setdefault(cluster_key, []).append(glyph['id'])

    return {k: v for k, v in clusters.items() if len(v) >= MIN_CLUSTER_SIZE}
