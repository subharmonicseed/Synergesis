#!/usr/bin/env python3
# File: topology_intention_transformer.py
# Description: Module pour transformer les intentions topologiques en glyphes d'action potentielle

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Import des modules personnalisés
from decorators import timing_and_logging, validate_required_properties
from schemas import (
    GlyphData, 
    PotentialActionGlyph, 
    ActionType, 
    DetailsStructuredJson, 
    ActionParameters, 
    SourceMetadata,
    convert_glyph_to_dict
)
from metrics import MetricsManager, measure_execution_time

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('topology_intention_transformer')


class TopologyIntentionTransformer:
    """
    Transforme les intentions topologiques en glyphes d'action potentielle.
    """
    
    def __init__(self, metrics_manager: Optional[MetricsManager] = None):
        """
        Initialise le transformateur d'intentions.
        
        Args:
            metrics_manager: Gestionnaire de métriques Prometheus (optionnel)
        """
        self.metrics_manager = metrics_manager
        logger.info("TopologyIntentionTransformer initialisé")
    
    @timing_and_logging
    @measure_execution_time("transform_intentions")
    def transform_intentions(self, observations: List[Dict[str, Any]], output_dir: str = None) -> List[Dict[str, Any]]:
        """
        Transforme une liste d'observations en glyphes d'action potentielle.
        
        Args:
            observations: Liste d'observations topologiques
            output_dir: Répertoire de sortie pour les fichiers JSON (optionnel)
            
        Returns:
            List[Dict[str, Any]]: Liste de glyphes d'action potentielle
        """
        if not observations:
            logger.warning("Aucune observation à transformer")
            return []
        
        # Créer le répertoire de sortie si nécessaire
        if output_dir:
            os.makedirs(os.path.join(output_dir, "potential_actions"), exist_ok=True)
        
        # Transformer chaque observation
        potential_actions = []
        
        for observation in observations:
            try:
                # Transformer l'observation en glyphe d'action potentielle
                action_glyph = self._transform_observation(observation)
                
                if action_glyph:
                    # Convertir en dictionnaire
                    action_dict = action_glyph.model_dump() # Utiliser model_dump() pour Pydantic V2
                    potential_actions.append(action_dict)
                    
                    # Sauvegarder dans un fichier JSON si un répertoire de sortie est spécifié
                    if output_dir:
                        self._save_action_to_file(action_dict, output_dir)
                
            except Exception as e:
                logger.error(f"Erreur lors de la transformation de l'observation: {e}")
                if self.metrics_manager:
                    self.metrics_manager.record_error("transform_observation", str(type(e).__name__))
        
        # Sauvegarder toutes les actions dans un fichier consolidé
        if output_dir and potential_actions:
            timestamp = int(time.time())
            consolidated_file = os.path.join(output_dir, f"potential_actions_{timestamp}.json")
            
            with open(consolidated_file, 'w') as f:
                json.dump(potential_actions, f, indent=2)
            
            logger.info(f"Fichier consolidé créé: {consolidated_file}")
        
        return potential_actions
    
    @validate_required_properties(["type"], arg_name="observation")
    def _transform_observation(self, observation: Dict[str, Any]) -> Optional[PotentialActionGlyph]:
        """
        Transforme une observation en glyphe d'action potentielle.
        
        Args:
            observation: Observation topologique
            
        Returns:
            Optional[PotentialActionGlyph]: Glyphe d'action potentielle ou None en cas d'erreur
        """
        observation_type = observation.get("type")
        
        # Mapper le type d'observation au type d'action
        if observation_type == "ISOLATED_GLYPHS_DETECTED":
            return self._create_connect_isolated_action(observation)
        elif observation_type == "HIGH_CENTRALITY_GLYPHS_DETECTED":
            return self._create_enrich_hub_action(observation)
        elif observation_type == "HIGH_PAGERANK_GLYPHS_DETECTED":
            return self._create_optimize_pagerank_action(observation)
        elif observation_type == "HIGH_BETWEENNESS_GLYPHS_DETECTED":
            return self._create_strengthen_bridge_action(observation)
        elif observation_type == "LOUVAIN_COMMUNITY_DISTRIBUTION":
            return self._create_explore_community_action(observation)
        elif observation_type == "FRACTAL_CONTEXT_ANALYSIS":
            return self._create_analyze_fractal_context_action(observation)
        # Add other observation types as needed
        else:
            logger.warning(f"Type d'observation non pris en charge: {observation_type}")
            return None
    
    def _create_connect_similar_action(self, intention: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour connecter des glyphes similaires.
        
        Args:
            intention: Intention de type CONNECT_SIMILAR_GLYPHS
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'intention
        target_glyphs = intention.get("target_glyphs", [])
        similarity_score = intention.get("similarity_score", 0.5)
        priority_text = intention.get("priority", "medium")
        
        if len(target_glyphs) < 2:
            raise ValueError("Au moins deux glyphes cibles sont nécessaires pour une action de connexion")
        
        # Créer l'ID unique
        action_id = f"sem-potentialaction-TOPOGEN-CONNECT-{self._generate_timestamp_id()}"
        
        # Convertir la priorité textuelle en valeur numérique
        priority = self._convert_priority_to_numeric(priority_text)
        
        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.CREATE_RELATIONSHIP,
            priority=priority,
            confidence=similarity_score,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    source_glyph_id=target_glyphs[0],
                    target_glyph_id=target_glyphs[1],
                    relationship_type="SIMILAR_TO"
                ),
                source_metadata=SourceMetadata(
                    intention_type=intention.get("intention_type"),
                    observation_ids=intention.get("observation_ids", []),
                    target_prompt=f"Connexion entre glyphes similaires: {target_glyphs[0]} et {target_glyphs[1]}"
                ),
                expected_impact={
                    "graph_connectivity": "improved",
                    "knowledge_coherence": "enhanced",
                    "similarity_cluster_formation": "enabled"
                },
                rollback_procedure={
                    "query": "MATCH (s)-[r:SIMILAR_TO]->(t) WHERE s.id = $source_id AND t.id = $target_id DELETE r",
                    "params": {
                        "source_id": target_glyphs[0],
                        "target_id": target_glyphs[1]
                    }
                }
            ),
            details_text=f"Cette action propose de créer une relation SIMILAR_TO entre les glyphes {target_glyphs[0]} et {target_glyphs[1]} qui ont été identifiés comme similaires avec un score de confiance de {similarity_score}."
        )
    
    def _create_solution_for_cluster_action(self, intention: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour générer une solution pour un cluster de problèmes.
        
        Args:
            intention: Intention de type CREATE_SOLUTION_FOR_PROBLEM_CLUSTER
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'intention
        target_glyphs = intention.get("target_glyphs", [])
        cluster_size = intention.get("cluster_size", len(target_glyphs))
        priority_text = intention.get("priority", "high")
        
        if not target_glyphs:
            raise ValueError("Au moins un glyphe problème est nécessaire pour une action de création de solution")
        
        # Créer l'ID unique
        action_id = f"sem-potentialaction-TOPOGEN-CREATESOL-{self._generate_timestamp_id()}"
        
        # Convertir la priorité textuelle en valeur numérique
        priority = self._convert_priority_to_numeric(priority_text)
        
        # Calculer la confiance en fonction de la taille du cluster
        confidence = min(0.9, 0.5 + (cluster_size / 10))
        
        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.CREATE_SOLUTION_NODE,
            priority=priority,
            confidence=confidence,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    problem_glyphs=target_glyphs,
                    solution_template=f"Solution unifiée pour résoudre les problèmes: {', '.join(target_glyphs)}"
                ),
                source_metadata=SourceMetadata(
                    intention_type=intention.get("intention_type"),
                    observation_ids=intention.get("observation_ids", []),
                    target_prompt=f"Création d'une solution pour un cluster de {len(target_glyphs)} problèmes"
                ),
                expected_impact={
                    "problem_resolution": "unified",
                    "knowledge_completeness": "improved",
                    "graph_structure": "balanced"
                },
                rollback_procedure={
                    "query": "MATCH (s:ProposedSolution)-[r:ADDRESSES_PROBLEM]->() WHERE s.source = 'topology_engine' AND s.timestamp > $timestamp DELETE s, r",
                    "params": {
                        "timestamp": int(time.time()) - 3600  # Dernière heure
                    }
                }
            ),
            details_text=f"Cette action propose de créer une solution unifiée pour résoudre un cluster de {len(target_glyphs)} problèmes similaires qui n'ont actuellement pas de solution associée."
        )
    
    def _create_connect_isolated_action(self, observation: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour connecter un glyphe isolé.
        
        Args:
            observation: Observation de type ISOLATED_GLYPHS_DETECTED
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'observation
        isolated_glyphs = observation.get("glyphs", [])
        
        if not isolated_glyphs:
            raise ValueError("Aucun glyphe isolé spécifié pour l'action de connexion")
        
        # Pour cet exemple, nous prenons le premier glyphe isolé
        target_glyph_id = isolated_glyphs[0].get("glyph_id")
        
        # Créer l'ID unique
        action_id = f"sem-potentialaction-TOPOGEN-CONNECTISO-{self._generate_timestamp_id()}"
        
        # Convertir la priorité textuelle en valeur numérique (ici, on met une priorité par défaut)
        priority = self._convert_priority_to_numeric("high")
        
        # Ajuster la confiance en fonction du niveau d'isolation (ici, on met une confiance par défaut)
        confidence = 0.9
        
        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.FIND_AND_CONNECT_ISOLATED,
            priority=priority,
            confidence=confidence,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    target_glyph_id=target_glyph_id
                ),
                source_metadata=SourceMetadata(
                    intention_type=observation.get("type"),
                    observation_ids=[f"obs_{self._generate_timestamp_id()}"], # Placeholder
                    target_prompt=f"Connexion du glyphe isolé {target_glyph_id}"
                ),
                expected_impact={
                    "graph_connectivity": "improved",
                    "knowledge_accessibility": "enhanced",
                    "isolated_nodes": "reduced"
                },
                rollback_procedure={
                    "query": "MATCH (g)-[r]-() WHERE g.id = $glyph_id AND r.timestamp > $timestamp DELETE r",
                    "params": {
                        "glyph_id": target_glyph_id,
                        "timestamp": int(time.time()) - 3600  # Dernière heure
                    }
                }
            ),
            details_text=f"Cette action propose de trouver et connecter le glyphe isolé {target_glyph_id} à d'autres glyphes similaires pour améliorer la connectivité du graphe."
        )
    
    def _create_enrich_hub_action(self, observation: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour enrichir un glyphe hub.
        
        Args:
            observation: Observation de type HIGH_CENTRALITY_GLYPHS_DETECTED
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'observation
        hub_glyphs = observation.get("glyphs", [])
        
        if not hub_glyphs:
            raise ValueError("Aucun glyphe hub spécifié pour l'action d'enrichissement")
        
        # Pour cet exemple, nous prenons le premier glyphe hub
        target_glyph_id = hub_glyphs[0].get("glyph_id")
        hub_degree = hub_glyphs[0].get("degree_centrality", 0)
        
        # Créer l'ID unique
        action_id = f"sem-potentialaction-TOPOGEN-ENRICHHUB-{self._generate_timestamp_id()}"
        
        # Convertir la priorité textuelle en valeur numérique (ici, on met une priorité par défaut)
        priority = self._convert_priority_to_numeric("high")
        
        # Ajuster la confiance en fonction du degré du hub
        confidence = min(0.95, 0.7 + (hub_degree / 20))
        
        # Déterminer les aspects d'enrichissement
        enrichment_aspects = ["detailed_description"]
        if hub_degree > 5:
            enrichment_aspects.append("connection_quality")
        if hub_degree > 10:
            enrichment_aspects.append("technical_details")
        
        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.ENRICH_HUB_NODE,
            priority=priority,
            confidence=confidence,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    target_glyph_id=target_glyph_id,
                    enrichment_aspects=enrichment_aspects
                ),
                source_metadata=SourceMetadata(
                    intention_type=observation.get("type"),
                    observation_ids=[f"obs_{self._generate_timestamp_id()}"], # Placeholder
                    target_prompt=f"Enrichissement du glyphe hub {target_glyph_id} avec {len(enrichment_aspects)} aspects"
                ),
                expected_impact={
                    "knowledge_quality": "improved",
                    "hub_importance": "highlighted",
                    "graph_navigation": "enhanced"
                },
                rollback_procedure={
                    "query": "MATCH (g:Glyph {id: $glyph_id}) SET g.natural_prompt = $original_prompt",
                    "params": {
                        "glyph_id": target_glyph_id,
                        "original_prompt": "" # This would need to be stored somewhere
                    }
                }
            ),
            details_text=f"Cette action propose d'enrichir le glyphe hub {target_glyph_id} avec des informations supplémentaires pour améliorer la qualité des connaissances."
        )

    def _create_optimize_pagerank_action(self, observation: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour optimiser le PageRank d'un glyphe.
        
        Args:
            observation: Observation de type HIGH_PAGERANK_GLYPHS_DETECTED
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'observation
        pagerank_glyphs = observation.get("glyphs", [])
        
        if not pagerank_glyphs:
            raise ValueError("Aucun glyphe PageRank spécifié pour l'action d'optimisation")
        
        # Pour cet exemple, nous prenons le premier glyphe PageRank
        target_glyph_id = pagerank_glyphs[0].get("glyph_id")
        pagerank_score = pagerank_glyphs[0].get("pagerank_score", 0)
        
        # Créer l'ID unique
        action_id = f"sem-potentialaction-TOPOGEN-PAGERANKOPT-{self._generate_timestamp_id()}"
        
        # Convertir la priorité textuelle en valeur numérique (ici, on met une priorité par défaut)
        priority = self._convert_priority_to_numeric("high")
        
        # Ajuster la confiance en fonction du score PageRank
        confidence = min(0.95, 0.7 + (pagerank_score / 1))
        
        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.OPTIMIZE_PAGERANK_GLYPH,
            priority=priority,
            confidence=confidence,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    target_glyph_id=target_glyph_id,
                    optimization_strategy="increase_in_degree"
                ),
                source_metadata=SourceMetadata(
                    intention_type=observation.get("type"),
                    observation_ids=[f"obs_{self._generate_timestamp_id()}"], # Placeholder
                    target_prompt=f"Optimisation du PageRank pour le glyphe {target_glyph_id}"
                ),
                expected_impact={
                    "glyph_influence": "increased",
                    "information_flow": "improved"
                },
                rollback_procedure={
                    "query": "MATCH (g:Glyph {id: $glyph_id}) SET g.pagerank_score = $original_pagerank_score",
                    "params": {
                        "glyph_id": target_glyph_id,
                        "original_pagerank_score": 0.0 # This would need to be stored somewhere
                    }
                }
            ),
            details_text=f"Cette action propose d'optimiser le PageRank du glyphe {target_glyph_id} pour augmenter son influence dans le graphe."
        )

    def _create_strengthen_bridge_action(self, observation: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour renforcer le rôle de pont d'un glyphe.
        
        Args:
            observation: Observation de type HIGH_BETWEENNESS_GLYPHS_DETECTED
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'observation
        betweenness_glyphs = observation.get("glyphs", [])
        
        if not betweenness_glyphs:
            raise ValueError("Aucun glyphe Betweenness spécifié pour l'action de renforcement")
        
        # Pour cet exemple, nous prenons le premier glyphe Betweenness
        target_glyph_id = betweenness_glyphs[0].get("glyph_id")
        betweenness_score = betweenness_glyphs[0].get("betweenness_centrality", 0)
        
        # Créer l'ID unique
        action_id = f"sem-potentialaction-TOPOGEN-BRIDGEOPT-{self._generate_timestamp_id()}"
        
        # Convertir la priorité textuelle en valeur numérique (ici, on met une priorité par défaut)
        priority = self._convert_priority_to_numeric("high")
        
        # Ajuster la confiance en fonction du score Betweenness
        confidence = min(0.95, 0.7 + (betweenness_score / 0.5))
        
        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.STRENGTHEN_BRIDGE_GLYPH,
            priority=priority,
            confidence=confidence,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    target_glyph_id=target_glyph_id,
                    strengthening_strategy="add_redundant_paths"
                ),
                source_metadata=SourceMetadata(
                    intention_type=observation.get("type"),
                    observation_ids=[f"obs_{self._generate_timestamp_id()}"], # Placeholder
                    target_prompt=f"Renforcement du rôle de pont pour le glyphe {target_glyph_id}"
                ),
                expected_impact={
                    "graph_resilience": "increased",
                    "information_flow_robustness": "improved"
                },
                rollback_procedure={
                    "query": "MATCH (g:Glyph {id: $glyph_id}) SET g.betweenness_centrality = $original_betweenness_centrality",
                    "params": {
                        "glyph_id": target_glyph_id,
                        "original_betweenness_centrality": 0.0 # This would need to be stored somewhere
                    }
                }
            ),
            details_text=f"Cette action propose de renforcer le rôle de pont du glyphe {target_glyph_id} pour améliorer la résilience du graphe."
        )

    def _create_explore_community_action(self, observation: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour explorer une communauté.
        
        Args:
            observation: Observation de type LOUVAIN_COMMUNITY_DISTRIBUTION
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'observation
        community_info = observation.get("communities", [])
        
        if not community_info:
            raise ValueError("Aucune information de communauté spécifiée pour l'action d'exploration")
        
        # Pour cet exemple, nous prenons la première communauté
        community_id = community_info[0].get("community_id")
        glyph_count = community_info[0].get("glyph_count", 0)
        
        # Créer l'ID unique
        action_id = f"sem-potentialaction-TOPOGEN-COMMUNITYEXP-{self._generate_timestamp_id()}"
        
        # Convertir la priorité textuelle en valeur numérique (ici, on met une priorité par défaut)
        priority = self._convert_priority_to_numeric("medium")
        
        # Ajuster la confiance en fonction de la taille de la communauté
        confidence = min(0.9, 0.5 + (glyph_count / 100))
        
        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.EXPLORE_COMMUNITY,
            priority=priority,
            confidence=confidence,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    community_id=community_id,
                    exploration_depth="medium"
                ),
                source_metadata=SourceMetadata(
                    intention_type=observation.get("type"),
                    observation_ids=[f"obs_{self._generate_timestamp_id()}"], # Placeholder
                    target_prompt=f"Exploration de la communauté {community_id}"
                ),
                expected_impact={
                    "knowledge_discovery": "new",
                    "community_understanding": "enhanced"
                },
                rollback_procedure={
                    "query": "", # No direct rollback for exploration
                    "params": {}
                }
            ),
            details_text=f"Cette action propose d'explorer la communauté {community_id} pour découvrir de nouvelles connaissances et comprendre sa structure."
        )

    def _create_analyze_fractal_context_action(self, observation: Dict[str, Any]) -> PotentialActionGlyph:
        """
        Crée une action pour analyser le contexte fractal d'un glyphe.
        
        Args:
            observation: Observation de type FRACTAL_CONTEXT_ANALYSIS
            
        Returns:
            PotentialActionGlyph: Glyphe d'action potentielle
        """
        # Extraire les informations de l'observation
        glyph_id = observation.get("glyph_id")
        context_analysis = observation.get("context_analysis", {})
        ethical_score = context_analysis.get("ethical_score", 0.0)
        energy_impact = context_analysis.get("energy_impact", 0.0)

        if not glyph_id:
            raise ValueError("Aucun ID de glyphe spécifié pour l'action d'analyse de contexte fractal")

        # Créer l'ID unique
        action_id = f"sem-potentialaction-FRACTAL-CONTEXTANALYSIS-{self._generate_timestamp_id()}"

        # Définir la priorité et la confiance en fonction des scores éthiques et énergétiques
        # Exemple: plus l'impact énergétique est élevé ou le score éthique est négatif, plus la priorité est haute
        priority = self._convert_priority_to_numeric("high" if energy_impact > 5 or ethical_score < -0.2 else "medium")
        confidence = min(0.9, 0.5 + (abs(ethical_score) + energy_impact / 10))

        # Créer le glyphe d'action potentielle
        return PotentialActionGlyph(
            id=action_id,
            action_type=ActionType.ANALYZE_FRACTAL_CONTEXT,
            priority=priority,
            confidence=confidence,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    target_glyph_id=glyph_id,
                    context_analysis_data=context_analysis
                ),
                source_metadata=SourceMetadata(
                    intention_type=observation.get("type"),
                    observation_ids=[f"obs_{self._generate_timestamp_id()}"], # Placeholder
                    target_prompt=f"Analyse approfondie du contexte fractal pour le glyphe {glyph_id}"
                ),
                expected_impact={
                    "ethical_alignment": "clarified",
                    "resource_optimization": "identified",
                    "contextual_understanding": "deepened"
                },
                rollback_procedure={
                    "query": "", # No direct rollback for analysis
                    "params": {}
                }
            ),
            details_text=f"Cette action propose d'analyser le contexte fractal du glyphe {glyph_id} pour évaluer son impact éthique et énergétique, et identifier des opportunités d'optimisation."
        )

    def _generate_timestamp_id(self) -> str:
        """
        Génère un ID basé sur le timestamp actuel.
        """
        return datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]

    def _convert_priority_to_numeric(self, priority_text: str) -> int:
        """
        Convertit une priorité textuelle en valeur numérique.
        """
        priority_map = {
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4
        }
        return priority_map.get(priority_text.lower(), 2) # Default to medium

    def _save_action_to_file(self, action_dict: Dict[str, Any], output_dir: str):
        """
        Sauvegarde un glyphe d'action potentielle dans un fichier JSON.
        """
        action_id = action_dict.get("id", f"unknown_action_{self._generate_timestamp_id()}")
        file_path = os.path.join(output_dir, "potential_actions", f"{action_id}.json")
        with open(file_path, 'w') as f:
            json.dump(action_dict, f, indent=2)
        logger.info(f"Action sauvegardée: {file_path}")


# Exemple d'utilisation (pour les tests ou l'exécution directe)
if __name__ == "__main__":
    # Créer un gestionnaire de métriques mock pour l'exemple
    class MockMetricsManager:
        def record_metric(self, *args, **kwargs): pass
        def record_error(self, *args, **kwargs): pass

    metrics_manager = MockMetricsManager()
    transformer = TopologyIntentionTransformer(metrics_manager=metrics_manager)

    # Exemple d'observations (à remplacer par de vraies observations)
    sample_observations = [
        {
            "type": "ISOLATED_GLYPHS_DETECTED",
            "details": "1 isolated glyph found.",
            "glyphs": [{
                "glyph_id": "glyph_A",
                "natural_prompt": "Concept isolé"
            }]
        },
        {
            "type": "FRACTAL_CONTEXT_ANALYSIS",
            "glyph_id": "glyph_B",
            "context_analysis": {
                "semantic_embedding_preview": [0.1, 0.2, 0.3, 0.4, 0.5],
                "ethical_score": -0.8,
                "energy_impact": 12.5
            }
        }
    ]

    # Transformer les observations en intentions
    output_directory = "./test_output"
    os.makedirs(output_directory, exist_ok=True)
    potential_actions = transformer.transform_intentions(sample_observations, output_dir=output_directory)

    print(f"\nGenerated {len(potential_actions)} potential actions:")
    for action in potential_actions:
        print(json.dumps(action, indent=2))

    # Nettoyage (optionnel)
    # import shutil
    # if os.path.exists(output_directory):
    #     shutil.rmtree(output_directory)






