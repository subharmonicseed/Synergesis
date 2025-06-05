"""Utilities to transform topology intentions into potential_action glyphs."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

GlyphData = Dict[str, Any]


class TopologyIntentionTransformer:
    """Transform topology intentions into glyph data structures."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.priority_mapping = self.config.get(
            "priority_mapping",
            {"HIGH": 90, "MEDIUM": 70, "LOW": 50},
        )
        self.timestamp = int(time.time())
        self.date_str = time.strftime("%Y%m%d", time.localtime())
        self.sequence_counters: Dict[str, int] = {}

    def transform_intentions(self, intentions: List[GlyphData]) -> List[GlyphData]:
        """Transform a list of topology intentions into potential_action glyphs."""
        glyphs: List[GlyphData] = []
        for intention in intentions:
            itype = intention.get("type")
            if itype == "CONNECT_SIMILAR_GLYPHS":
                glyphs.append(self._transform_connect_similar_glyphs(intention))
            elif itype == "CREATE_SOLUTION_FOR_PROBLEM_CLUSTER":
                glyphs.append(
                    self._transform_create_solution_for_problem_cluster(intention)
                )
        return glyphs

    # internal helpers ---------------------------------------------------
    def _get_next_sequence(self, intention_type: str) -> str:
        self.sequence_counters[intention_type] = (
            self.sequence_counters.get(intention_type, 0) + 1
        )
        return f"{self.sequence_counters[intention_type]:03d}"

    def _map_priority(self, priority_text: str) -> int:
        return self.priority_mapping.get(priority_text.upper(), 50)

    def _transform_connect_similar_glyphs(self, intention: GlyphData) -> GlyphData:
        seq = self._get_next_sequence("CONNECT")
        gid = f"sem-potentialaction-TOPOGEN-CONNECT-{self.date_str}-{seq}"
        similarity = intention.get("similarity_score", 0.0)
        priority = self._map_priority(intention.get("priority", "LOW"))
        source_glyph = intention.get("source_glyph", {})
        target_glyph = intention.get("target_glyph", {})
        relation = intention.get("suggested_relation", "RELATED_TO_CONCEPT")
        rationale = intention.get("rationale", "")

        return {
            "id": gid,
            "timestamp": self.timestamp,
            "source": "topology_aware_intention_generator",
            "concept_type": "POTENTIAL_ACTION",
            "action_type": "CREATE_RELATIONSHIP",
            "status": "PROPOSED",
            "priority": priority,
            "confidence": similarity,
            "tags": [
                "topology_generated",
                "similarity_based",
                "structural_improvement",
                source_glyph.get("concept_type"),
                relation,
            ],
            "natural_prompt": (
                f"Créer une relation {relation} entre deux glyphes"
                f" {source_glyph.get('concept_type')} similaires (score: {similarity:.2f})"
            ),
            "details_structured_json": {
                "action_parameters": {
                    "source_glyph_id": source_glyph.get("id"),
                    "target_glyph_id": target_glyph.get("id"),
                    "relationship_type": relation,
                    "relationship_properties": {
                        "similarity_score": similarity,
                        "generated_by": "topology_aware_intention_generator",
                        "generation_timestamp": self.timestamp,
                        "rationale": rationale,
                    },
                },
                "source_metadata": {
                    "intention_type": "CONNECT_SIMILAR_GLYPHS",
                    "source_glyph_concept_type": source_glyph.get("concept_type"),
                    "target_glyph_concept_type": target_glyph.get("concept_type"),
                    "similarity_score": similarity,
                    "original_priority": intention.get("priority"),
                },
            },
            "details_text": rationale,
            "metadata": {
                "generation_context": {
                    "generator_version": "1.0.0",
                    "generation_timestamp": self.timestamp,
                }
            },
        }

    def _transform_create_solution_for_problem_cluster(self, intention: GlyphData) -> GlyphData:
        seq = self._get_next_sequence("CREATESOL")
        gid = f"sem-potentialaction-TOPOGEN-CREATESOL-{self.date_str}-{seq}"
        similarity = intention.get("avg_similarity", 0.0)
        priority = self._map_priority(intention.get("priority", "LOW"))
        cluster_id = intention.get("target_cluster_id")
        problems = intention.get("problems", [])
        problem_ids = [p.get("id") for p in problems if p.get("id")]
        rationale = intention.get("rationale", "")
        confidence = min(1.0, similarity + len(problem_ids) / 10.0)

        relationships = [
            {
                "source_template": "{solution_id}",
                "target": pid,
                "type": "ADDRESSES_PROBLEM",
                "properties": {
                    "generated_by": "topology_aware_intention_generator",
                    "generation_timestamp": self.timestamp,
                    "cluster_id": cluster_id,
                },
            }
            for pid in problem_ids
        ]

        return {
            "id": gid,
            "timestamp": self.timestamp,
            "source": "topology_aware_intention_generator",
            "concept_type": "POTENTIAL_ACTION",
            "action_type": "CREATE_SOLUTION_NODE",
            "status": "PROPOSED",
            "priority": priority,
            "confidence": confidence,
            "tags": [
                "topology_generated",
                "cluster_based",
                "gap_filling",
                "PROBLEM",
                "PROPOSEDSOLUTION",
                "ADDRESSES_PROBLEM",
            ],
            "natural_prompt": (
                f"Créer un nouveau glyphe PROPOSEDSOLUTION qui adresse un cluster de"
                f" {len(problem_ids)} problèmes similaires (score moyen: {similarity:.2f})"
            ),
            "details_structured_json": {
                "action_parameters": {
                    "solution_glyph": {
                        "id_template": f"sem-proposedsolution-TOPOGEN-{{timestamp}}",
                        "concept_type": "PROPOSEDSOLUTION",
                        "natural_prompt_template": (
                            "Solution unifiée pour les problèmes liés à {common_themes}"
                            f" identifiés dans le cluster {cluster_id}"
                        ),
                        "tags": [
                            "topology_generated",
                            "cluster_solution",
                            "unified_approach",
                        ],
                    },
                    "problem_glyphs": problem_ids,
                    "relationships_to_create": relationships,
                },
                "source_metadata": {
                    "intention_type": "CREATE_SOLUTION_FOR_PROBLEM_CLUSTER",
                    "target_cluster_id": cluster_id,
                    "cluster_size": len(problem_ids),
                    "avg_similarity": similarity,
                    "original_priority": intention.get("priority"),
                },
            },
            "details_text": rationale,
            "metadata": {
                "generation_context": {
                    "generator_version": "1.0.0",
                    "generation_timestamp": self.timestamp,
                }
            },
        }
