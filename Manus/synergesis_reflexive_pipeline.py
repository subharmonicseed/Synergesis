import logging
import os
import sys
import json
from typing import List, Dict, Any

# Ajouter le répertoire parent au PYTHONPATH pour les imports relatifs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from glyph_topology_enricher import GlyphTopologyEnricher
from topology_aware_reflexive_cortex import TopologyAwareReflexiveCortex
from topology_intention_transformer import TopologyIntentionTransformer
from refactored_glyph_action_executor import GlyphActionExecutor
from metrics import MetricsManager

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('synergesis_reflexive_pipeline')

class SynergesisReflexivePipeline:
    def __init__(self, neo4j_connector):
        self.neo4j_connector = neo4j_connector
        self.metrics_manager = MetricsManager()
        self.glyph_enricher = GlyphTopologyEnricher(neo4j_connector, self.metrics_manager)
        self.reflexive_cortex = TopologyAwareReflexiveCortex(neo4j_connector)
        self.intention_transformer = TopologyIntentionTransformer(self.metrics_manager)
        self.action_executor = GlyphActionExecutor(neo4j_connector, self.metrics_manager)

    def run_pipeline(self, output_dir: str = "./reflexive_results"):
        logger.info("Démarrage du pipeline réflexif Synergesis...")

        # 1. Enrichissement topologique du graphe
        logger.info("Étape 1: Enrichissement topologique du graphe...")
        self.glyph_enricher.enrich_graph()
        logger.info("Étape 1 terminée.")

        # 2. Génération des observations par le Cortex Réflexif
        logger.info("Étape 2: Génération des observations par le Cortex Réflexif...")
        observations = self.reflexive_cortex.generate_observations()
        logger.info(f"Étape 2 terminée. {len(observations)} observations générées.")

        # Sauvegarder les observations
        obs_output_path = os.path.join(output_dir, f"topology_observations_{int(time.time())}.json")
        os.makedirs(output_dir, exist_ok=True)
        with open(obs_output_path, 'w') as f:
            json.dump(observations, f, indent=2)
        logger.info(f"Observations sauvegardées dans {obs_output_path}")

        # 3. Transformation des observations en intentions
        logger.info("Étape 3: Transformation des observations en intentions...")
        potential_actions = self.intention_transformer.transform_intentions(observations, output_dir)
        logger.info(f"Étape 3 terminée. {len(potential_actions)} intentions transformées en actions potentielles.")

        # 4. Exécution des actions potentielles
        logger.info("Étape 4: Exécution des actions potentielles...")
        execution_results = []
        for action in potential_actions:
            result = self.action_executor.execute_action(action)
            execution_results.append(result.model_dump())
            logger.info(f"Action {action.get('id', 'N/A')} exécutée avec statut: {result.status}")
        logger.info("Étape 4 terminée.")

        # Sauvegarder les résultats d'exécution
        exec_output_path = os.path.join(output_dir, f"execution_results_{int(time.time())}.json")
        with open(exec_output_path, 'w') as f:
            json.dump(execution_results, f, indent=2)
        logger.info(f"Résultats d'exécution sauvegardés dans {exec_output_path}")

        logger.info("Pipeline réflexif Synergesis terminé.")
        return execution_results

if __name__ == "__main__":
    # Mock du connecteur Neo4j pour les tests
    class MockNeo4jConnector:
        def execute_query(self, query, parameters=None):
            logger.info(f"MockNeo4jConnector: Exécution de la requête: {query}")
            # Simuler des données pour les observations
            if "ISOLATED_GLYPHS_DETECTED" in query:
                return [{
                    "glyph_id": "isolated_glyph_1",
                    "natural_prompt": "Un concept très isolé"
                }]
            elif "HIGH_CENTRALITY_GLYPHS_DETECTED" in query:
                return [{
                    "glyph_id": "hub_glyph_1",
                    "natural_prompt": "Un concept central",
                    "degree_centrality": 10
                }]
            elif "PROBLEM_CLUSTERS_NO_SOLUTIONS_DETECTED" in query:
                return [{
                    "cluster_node_id": "problem_cluster_1"
                }]
            elif "HIGH_PAGERANK_GLYPHS_DETECTED" in query:
                return [{
                    "glyph_id": "pagerank_glyph_1",
                    "natural_prompt": "Un concept influent",
                    "pagerank_score": 0.75
                }]
            elif "HIGH_BETWEENNESS_GLYPHS_DETECTED" in query:
                return [{
                    "glyph_id": "betweenness_glyph_1",
                    "natural_prompt": "Un concept de pont",
                    "betweenness_centrality": 0.3
                }]
            elif "LOUVAIN_COMMUNITY_DISTRIBUTION" in query:
                return [{
                    "community_id": 1,
                    "glyph_count": 50
                }]
            elif "FRACTAL_CONTEXT_ANALYSIS" in query:
                return [{
                    "glyph_id": "fractal_glyph_1",
                    "natural_prompt": "Un concept fractal"
                }]
            elif "gds.graph.exists" in query:
                return [{
                    "exists": True
                }]
            elif "gds.graph.nodeProperties.write" in query:
                return [{
                    "nodePropertiesWritten": 10
                }]
            elif "MATCH (g:Glyph) WHERE g.id = $glyph_id RETURN count(g) > 0 AS exists" in query:
                return [{
                    "exists": True
                }]
            elif "MATCH (g:Glyph) WHERE g.id = $glyph_id RETURN g.id AS glyph_id, g.natural_prompt AS natural_prompt, g.tags AS tags, g.concept_type AS concept_type" in query:
                return [{
                    "glyph_id": parameters["glyph_id"],
                    "natural_prompt": "Mocked prompt",
                    "tags": [],
                    "concept_type": "TECHNICALCONCEPT"
                }]
            elif "MATCH (g:Glyph) WHERE g.id = $glyph_id SET g.tags = $tags RETURN g.id AS glyph_id, g.tags AS tags" in query:
                return [{
                    "glyph_id": parameters["glyph_id"],
                    "tags": parameters["tags"]
                }]
            else:
                return []

    mock_neo4j_connector = MockNeo4jConnector()
    pipeline = SynergesisReflexivePipeline(mock_neo4j_connector)
    pipeline.run_pipeline()


