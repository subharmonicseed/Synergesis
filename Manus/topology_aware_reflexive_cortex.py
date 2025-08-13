from neo4j import GraphDatabase
import logging
from typing import List, Dict, Any

# Importation des classes fractales
from SynergesisCore_DeepSeek_Pro_Fractal import AdvancedContextValidator, QuantumEnergyCalculator

logger = logging.getLogger(__name__)

class TopologyAwareReflexiveCortex:
    def __init__(self, neo4j_connector):
        self.neo4j_connector = neo4j_connector
        self.context_validator = AdvancedContextValidator()

    def generate_observations(self) -> List[Dict[str, Any]]:
        observations = []
        
        # Observation 1: Isolated Glyphs (degree_centrality = 0)
        isolated_glyphs = self.neo4j_connector.execute_query("""
            MATCH (g:Glyph)
            WHERE g.degree_centrality = 0
            RETURN g.id AS glyph_id, g.natural_prompt AS natural_prompt
        """)
        if isolated_glyphs:
            observations.append({
                "type": "ISOLATED_GLYPHS_DETECTED",
                "details": f"{len(isolated_glyphs)} isolated glyphs found.",
                "glyphs": isolated_glyphs
            })
            logger.info(f"Detected {len(isolated_glyphs)} isolated glyphs.")

        # Observation 2: High Centrality Glyphs (hubs)
        high_centrality_glyphs = self.neo4j_connector.execute_query("""
            MATCH (g:Glyph)
            WHERE g.degree_centrality > 5 // Example threshold
            RETURN g.id AS glyph_id, g.natural_prompt AS natural_prompt, g.degree_centrality AS degree_centrality
            ORDER BY g.degree_centrality DESC
        """)
        if high_centrality_glyphs:
            observations.append({
                "type": "HIGH_CENTRALITY_GLYPHS_DETECTED",
                "details": f"{len(high_centrality_glyphs)} high centrality glyphs found.",
                "glyphs": high_centrality_glyphs
            })
            logger.info(f"Detected {len(high_centrality_glyphs)} high centrality glyphs.")

        # Observation 3: Problem Clusters without Solutions (requires more complex logic)
        problem_clusters_no_solutions = self.neo4j_connector.execute_query("""
            MATCH (p:Glyph {concept_type: 'PROBLEM'})-[*1..2]-(cluster_node)
            WHERE NOT EXISTS((cluster_node)-[:SOLVES]->(:Glyph {concept_type: 'PROPOSEDSOLUTION'}))
            RETURN DISTINCT cluster_node.id AS cluster_node_id
            LIMIT 5 // Example limit
        """)
        if problem_clusters_no_solutions:
            observations.append({
                "type": "PROBLEM_CLUSTERS_NO_SOLUTIONS_DETECTED",
                "details": f"{len(problem_clusters_no_solutions)} problem clusters without solutions found.",
                "clusters": problem_clusters_no_solutions
            })
            logger.info(f"Detected {len(problem_clusters_no_solutions)} problem clusters without solutions.")

        # Observation 4: Glyphs with very high PageRank
        high_pagerank_glyphs = self.neo4j_connector.execute_query("""
            MATCH (g:Glyph)
            WHERE g.pagerank_score IS NOT NULL AND g.pagerank_score > 0.5 // Example threshold
            RETURN g.id AS glyph_id, g.natural_prompt AS natural_prompt, g.pagerank_score AS pagerank_score
            ORDER BY g.pagerank_score DESC
        """)
        if high_pagerank_glyphs:
            observations.append({
                "type": "HIGH_PAGERANK_GLYPHS_DETECTED",
                "details": f"{len(high_pagerank_glyphs)} glyphs with high PageRank found.",
                "glyphs": high_pagerank_glyphs
            })
            logger.info(f"Detected {len(high_pagerank_glyphs)} glyphs with high PageRank.")

        # Observation 5: Glyphs with high Betweenness Centrality
        high_betweenness_glyphs = self.neo4j_connector.execute_query("""
            MATCH (g:Glyph)
            WHERE g.betweenness_centrality IS NOT NULL AND g.betweenness_centrality > 0.1 // Example threshold
            RETURN g.id AS glyph_id, g.natural_prompt AS natural_prompt, g.betweenness_centrality AS betweenness_centrality
            ORDER BY g.betweenness_centrality DESC
        """)
        if high_betweenness_glyphs:
            observations.append({
                "type": "HIGH_BETWEENNESS_GLYPHS_DETECTED",
                "details": f"{len(high_betweenness_glyphs)} glyphs with high Betweenness Centrality found.",
                "glyphs": high_betweenness_glyphs
            })
            logger.info(f"Detected {len(high_betweenness_glyphs)} glyphs with high Betweenness Centrality.")

        # Observation 6: Community distribution (Louvain)
        community_counts = self.neo4j_connector.execute_query("""
            MATCH (g:Glyph)
            WHERE g.louvain_community_id IS NOT NULL
            RETURN g.louvain_community_id AS community_id, count(g) AS glyph_count
            ORDER BY glyph_count DESC
        """)
        if community_counts:
            observations.append({
                "type": "LOUVAIN_COMMUNITY_DISTRIBUTION",
                "details": f"{len(community_counts)} communities detected.",
                "communities": community_counts
            })
            logger.info(f"Detected {len(community_counts)} Louvain communities.")

        # Observation 7: Fractal Contextual Analysis (new)
        # This would typically involve fetching relevant text from glyphs and analyzing it
        # For demonstration, let's assume we analyze the 'natural_prompt' of some glyphs
        sample_glyphs_for_context = self.neo4j_connector.execute_query("""
            MATCH (g:Glyph)
            RETURN g.id AS glyph_id, g.natural_prompt AS natural_prompt
            LIMIT 3
        """)
        
        for glyph in sample_glyphs_for_context:
            if glyph["natural_prompt"]:
                context_analysis = self.context_validator.analyze_context(glyph["natural_prompt"])
                observations.append({
                    "type": "FRACTAL_CONTEXT_ANALYSIS",
                    "details": f"Contextual analysis for glyph {glyph['glyph_id']}",
                    "glyph_id": glyph["glyph_id"],
                    "context_analysis": {
                        "semantic_embedding_preview": context_analysis["semantic_embedding"].tolist()[:5], # Store a preview
                        "ethical_score": context_analysis["ethical_score"],
                        "energy_impact": context_analysis["energy_impact"]
                    }
                })
                logger.info(f"Performed fractal context analysis for glyph {glyph['glyph_id']}")

        return observations


