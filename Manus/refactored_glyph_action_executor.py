#!/usr/bin/env python3
# File: refactored_glyph_action_executor.py
# Description: Module refactorisé pour l'exécution des actions sur les glyphes

import logging
import time
import json
import os
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime

# Import des modules personnalisés
from decorators import (
    fallback_property,
    validate_required_properties,
    timing_and_logging,
    retry,
    transaction
)
from schemas import (
    GlyphData,
    PotentialActionGlyph,
    ActionType,
    ExecutionResult,
    ExecutionStatus,
    ExecutionResultData,
    convert_dict_to_glyph,
    convert_glyph_to_dict
)
from metrics import MetricsManager, measure_execution_time

# Configuration du logging
logger = logging.getLogger('glyph_action_executor')


class GlyphActionExecutor:
    """
    Classe responsable de l'exécution des actions sur les glyphes.
    Intègre les décorateurs défensifs, les schémas Pydantic et l'instrumentation Prometheus.
    """
    
    def __init__(self, neo4j_connector, metrics_manager: Optional[MetricsManager] = None):
        """
        Initialise l'exécuteur d'actions.
        
        Args:
            neo4j_connector: Connecteur Neo4j pour interagir avec la base de données
            metrics_manager: Gestionnaire de métriques Prometheus (optionnel)
        """
        self.neo4j_connector = neo4j_connector
        self.metrics_manager = metrics_manager
        logger.info("GlyphActionExecutor initialisé")
    
    @timing_and_logging
    def execute_action(self, action_glyph: Union[PotentialActionGlyph, Dict[str, Any]]) -> ExecutionResult:
        """
        Exécute une action sur un glyphe.
        
        Args:
            action_glyph: Glyphe d'action potentielle ou dictionnaire représentant l'action
            
        Returns:
            ExecutionResult: Résultat de l'exécution
        """
        # Convertir en objet PotentialActionGlyph si nécessaire
        if isinstance(action_glyph, dict):
            try:
                action_glyph = convert_dict_to_glyph(action_glyph)
                if not isinstance(action_glyph, PotentialActionGlyph):
                    return ExecutionResult(
                        status=ExecutionStatus.ERROR,
                        message=f"L'objet fourni n'est pas une action potentielle valide: {type(action_glyph)}"
                    )
            except Exception as e:
                logger.error(f"Erreur lors de la conversion de l'action: {e}")
                if self.metrics_manager:
                    self.metrics_manager.record_error("execute_action", str(type(e).__name__))
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    message=f"Erreur lors de la conversion de l'action: {str(e)}"
                )
        
        # Enregistrer la métrique d'exécution d'action
        if self.metrics_manager:
            self.metrics_manager.record_action_execution(str(action_glyph.action_type))
        
        # Exécuter l'action en fonction de son type
        try:
            if action_glyph.action_type == ActionType.CREATE_RELATIONSHIP:
                return self._execute_create_relationship(action_glyph)
            elif action_glyph.action_type == ActionType.CREATE_SOLUTION_NODE:
                return self._execute_create_solution_node(action_glyph)
            elif action_glyph.action_type == ActionType.FIND_AND_CONNECT_ISOLATED:
                return self._execute_find_and_connect_isolated(action_glyph)
            elif action_glyph.action_type == ActionType.ENRICH_HUB_NODE:
                return self._execute_enrich_hub_node(action_glyph)
            else:
                logger.warning(f"Type d'action non pris en charge: {action_glyph.action_type}")
                if self.metrics_manager:
                    self.metrics_manager.record_error("execute_action", "unsupported_action_type")
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    message=f"Type d'action non pris en charge: {action_glyph.action_type}"
                )
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de l'action {action_glyph.id}: {e}")
            if self.metrics_manager:
                self.metrics_manager.record_error("execute_action", str(type(e).__name__))
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message=f"Erreur lors de l'exécution de l'action: {str(e)}"
            )
    
    @transaction
    @validate_required_properties(["source_glyph_id", "target_glyph_id", "relationship_type"], arg_name="action_params")
    @measure_execution_time("create_relationship")
    def _execute_create_relationship(self, action_glyph: PotentialActionGlyph, tx=None) -> ExecutionResult:
        """
        Exécute une action de création de relation entre deux glyphes.
        
        Args:
            action_glyph: Glyphe d'action potentielle
            tx: Transaction Neo4j (injectée par le décorateur transaction)
            
        Returns:
            ExecutionResult: Résultat de l'exécution
        """
        # Extraire les paramètres
        action_params = action_glyph.details_structured_json.action_parameters
        source_id = action_params.source_glyph_id
        target_id = action_params.target_glyph_id
        rel_type = action_params.relationship_type
        
        # Vérifier que les glyphes existent
        source_exists = self._check_glyph_exists(source_id, tx)
        target_exists = self._check_glyph_exists(target_id, tx)
        
        if not source_exists:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message=f"Le glyphe source {source_id} n'existe pas"
            )
        
        if not target_exists:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message=f"Le glyphe cible {target_id} n'existe pas"
            )
        
        # Créer la relation
        query = """
        MATCH (source), (target)
        WHERE source.id = $source_id AND target.id = $target_id
        CREATE (source)-[r:$rel_type]->(target)
        RETURN source.id AS source_id, target.id AS target_id, type(r) AS r_type
        """
        
        params = {
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_type
        }
        
        # Exécuter la requête
        if tx:
            result = tx.run(query, params).single()
        else:
            result = self.neo4j_connector.execute_query(query, params)[0]
        
        # Enregistrer la métrique
        if self.metrics_manager:
            self.metrics_manager.update_graph_relationships(rel_type, 1)
        
        # Retourner le résultat
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Relation {rel_type} créée entre {source_id} et {target_id}",
            data=ExecutionResultData(
                source_id=result["source_id"],
                target_id=result["target_id"],
                r_type=result["r_type"]
            )
        )
    
    @transaction
    @measure_execution_time("create_solution_node")
    def _execute_create_solution_node(self, action_glyph: PotentialActionGlyph, tx=None) -> ExecutionResult:
        """
        Exécute une action de création d'un nœud solution.
        
        Args:
            action_glyph: Glyphe d'action potentielle
            tx: Transaction Neo4j (injectée par le décorateur transaction)
            
        Returns:
            ExecutionResult: Résultat de l'exécution
        """
        # Extraire les paramètres
        action_params = action_glyph.details_structured_json.action_parameters
        problem_glyphs = action_params.problem_glyphs or []
        
        if not problem_glyphs:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message="Aucun glyphe problème spécifié pour la création de solution"
            )
        
        # Générer un ID unique pour la solution
        solution_id = f"sem-proposedsolution-TOPOGEN-{int(time.time())}"
        
        # Créer le nœud solution
        solution_query = """
        CREATE (s:Glyph:ProposedSolution {
            id: $id,
            concept_type: 'PROPOSEDSOLUTION',
            timestamp: $timestamp,
            natural_prompt: $prompt,
            source: 'topology_engine'
        })
        RETURN s.id AS solution_id
        """
        
        solution_params = {
            "id": solution_id,
            "timestamp": int(time.time()),
            "prompt": f"Solution proposée pour résoudre les problèmes: {', '.join(problem_glyphs)}"
        }
        
        # Exécuter la requête de création de solution
        if tx:
            solution_result = tx.run(solution_query, solution_params).single()
        else:
            solution_result = self.neo4j_connector.execute_query(solution_query, solution_params)[0]
        
        # Créer les relations avec les problèmes
        relationships = []
        
        for problem_id in problem_glyphs:
            # Vérifier que le problème existe
            if not self._check_glyph_exists(problem_id, tx):
                logger.warning(f"Le glyphe problème {problem_id} n'existe pas, relation ignorée")
                continue
            
            # Créer la relation
            rel_query = """
            MATCH (s:Glyph), (p:Glyph)
            WHERE s.id = $solution_id AND p.id = $problem_id
            CREATE (s)-[r:ADDRESSES_PROBLEM]->(p)
            RETURN s.id AS source_id, p.id AS target_id, type(r) AS r_type
            """
            
            rel_params = {
                "solution_id": solution_id,
                "problem_id": problem_id
            }
            
            # Exécuter la requête de création de relation
            if tx:
                rel_result = tx.run(rel_query, rel_params).single()
            else:
                rel_result = self.neo4j_connector.execute_query(rel_query, rel_params)[0]
            
            relationships.append({
                "source_id": rel_result["source_id"],
                "target_id": rel_result["target_id"],
                "type": rel_result["r_type"]
            })
        
        # Enregistrer les métriques
        if self.metrics_manager:
            self.metrics_manager.update_graph_nodes("PROPOSEDSOLUTION", 1)
            self.metrics_manager.update_graph_relationships("ADDRESSES_PROBLEM", len(relationships))
        
        # Retourner le résultat
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Solution {solution_id} créée avec {len(relationships)} relations",
            data=ExecutionResultData(
                solution_id=solution_id,
                relationships=relationships
            )
        )
    
    @transaction
    @measure_execution_time("find_and_connect_isolated")
    def _execute_find_and_connect_isolated(self, action_glyph: PotentialActionGlyph, tx=None) -> ExecutionResult:
        """
        Exécute une action pour trouver et connecter un glyphe isolé.
        
        Args:
            action_glyph: Glyphe d'action potentielle
            tx: Transaction Neo4j (injectée par le décorateur transaction)
            
        Returns:
            ExecutionResult: Résultat de l'exécution
        """
        # Extraire les paramètres
        action_params = action_glyph.details_structured_json.action_parameters
        target_glyph_id = action_params.target_glyph_id
        
        if not target_glyph_id:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message="Aucun glyphe cible spécifié pour la connexion"
            )
        
        # Vérifier que le glyphe existe
        if not self._check_glyph_exists(target_glyph_id, tx):
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message=f"Le glyphe cible {target_glyph_id} n'existe pas"
            )
        
        # Trouver des glyphes similaires pour la connexion
        similar_query = """
        MATCH (target:Glyph), (other:Glyph)
        WHERE target.id = $target_id
          AND other.id <> $target_id
          AND other.concept_type = target.concept_type
          AND NOT (target)-[]-()
        RETURN other.id AS similar_id, other.concept_type AS concept_type
        LIMIT 3
        """
        
        similar_params = {
            "target_id": target_glyph_id
        }
        
        # Exécuter la requête de recherche
        if tx:
            similar_results = list(tx.run(similar_query, similar_params))
        else:
            similar_results = self.neo4j_connector.execute_query(similar_query, similar_params)
        
        if not similar_results:
            return ExecutionResult(
                status=ExecutionStatus.WARNING,
                message=f"Aucun glyphe similaire trouvé pour {target_glyph_id}"
            )
        
        # Créer des relations avec les glyphes similaires
        relationships = []
        
        for similar in similar_results:
            similar_id = similar["similar_id"]
            
            # Déterminer le type de relation en fonction du type de concept
            concept_type = similar["concept_type"]
            if concept_type in ["PROBLEM", "PROPOSEDSOLUTION", "TECHNICALCONCEPT"]:
                rel_type = "SIMILAR_TO"
            else:
                rel_type = "RELATED_TO_CONCEPT"
            
            # Créer la relation
            rel_query = """
            MATCH (target:Glyph), (similar:Glyph)
            WHERE target.id = $target_id AND similar.id = $similar_id
            CREATE (target)-[r:$rel_type]->(similar)
            RETURN target.id AS source_id, similar.id AS target_id, type(r) AS r_type
            """
            
            rel_params = {
                "target_id": target_glyph_id,
                "similar_id": similar_id,
                "rel_type": rel_type
            }
            
            # Exécuter la requête de création de relation
            if tx:
                rel_result = tx.run(rel_query, rel_params).single()
            else:
                rel_result = self.neo4j_connector.execute_query(rel_query, rel_params)[0]
            
            relationships.append({
                "source_id": rel_result["source_id"],
                "target_id": rel_result["target_id"],
                "type": rel_result["r_type"]
            })
        
        # Enregistrer les métriques
        if self.metrics_manager:
            self.metrics_manager.update_graph_relationships(rel_type, len(relationships))
        
        # Retourner le résultat
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Glyphe {target_glyph_id} connecté à {len(relationships)} glyphes similaires",
            data=ExecutionResultData(
                glyph_id=target_glyph_id,
                relationships=relationships
            )
        )
    
    @transaction
    @fallback_property("natural_prompt", fallback_source="details_structured_json.source_metadata.target_prompt", fallback_value="Glyphe sans description")
    @measure_execution_time("enrich_hub_node")
    def _execute_enrich_hub_node(self, action_glyph: PotentialActionGlyph, tx=None) -> ExecutionResult:
        """
        Exécute une action d'enrichissement d'un nœud hub.
        
        Args:
            action_glyph: Glyphe d'action potentielle
            tx: Transaction Neo4j (injectée par le décorateur transaction)
            
        Returns:
            ExecutionResult: Résultat de l'exécution
        """
        # Extraire les paramètres
        action_params = action_glyph.details_structured_json.action_parameters
        target_glyph_id = action_params.target_glyph_id
        
        if not target_glyph_id:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message="Aucun glyphe hub spécifié pour l'enrichissement"
            )
        
        # Récupérer les informations actuelles du glyphe
        current_info = self._get_glyph_info(target_glyph_id, tx)
        
        if not current_info:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message=f"Le glyphe hub {target_glyph_id} n'existe pas"
            )
        
        # Récupérer la description actuelle avec gestion de fallback
        original_prompt = current_info.get("natural_prompt", "")
        
        # Si natural_prompt est manquant, utiliser le fallback
        if not original_prompt:
            if self.metrics_manager:
                self.metrics_manager.record_fallback_usage("natural_prompt", "enrich_hub_node")
            
            # Utiliser le target_prompt comme fallback
            if action_glyph.details_structured_json.source_metadata and action_glyph.details_structured_json.source_metadata.target_prompt:
                original_prompt = action_glyph.details_structured_json.source_metadata.target_prompt
            else:
                original_prompt = "Glyphe sans description"
            
            logger.warning(f"natural_prompt manquant pour le glyphe {target_glyph_id}, utilisation du fallback: {original_prompt}")
        
        # Enrichir la description
        enriched_prompt = self._generate_enriched_description(
            original_prompt,
            current_info.get("concept_type", "UNKNOWN"),
            action_params.enrichment_aspects or ["detailed_description"]
        )
        
        # Mettre à jour le glyphe
        update_query = """
        MATCH (g:Glyph)
        WHERE g.id = $glyph_id
        SET g.natural_prompt = $enriched_prompt,
            g.last_enriched = $timestamp,
            g.enrichment_source = 'topology_engine'
        RETURN g.id AS glyph_id, g.natural_prompt AS enriched_prompt
        """
        
        update_params = {
            "glyph_id": target_glyph_id,
            "enriched_prompt": enriched_prompt,
            "timestamp": int(time.time())
        }
        
        # Exécuter la requête de mise à jour
        if tx:
            update_result = tx.run(update_query, update_params).single()
        else:
            update_result = self.neo4j_connector.execute_query(update_query, update_params)[0]
        
        # Retourner le résultat
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Glyphe hub {target_glyph_id} enrichi",
            data=ExecutionResultData(
                glyph_id=update_result["glyph_id"],
                original_prompt=original_prompt,
                enriched_prompt=update_result["enriched_prompt"]
            )
        )
    
    def _check_glyph_exists(self, glyph_id: str, tx=None) -> bool:
        """
        Vérifie si un glyphe existe dans la base de données.
        
        Args:
            glyph_id: ID du glyphe à vérifier
            tx: Transaction Neo4j (optionnelle)
            
        Returns:
            bool: True si le glyphe existe, False sinon
        """
        query = "MATCH (g:Glyph) WHERE g.id = $glyph_id RETURN count(g) AS count"
        params = {"glyph_id": glyph_id}
        
        if tx:
            result = tx.run(query, params).single()
        else:
            result = self.neo4j_connector.execute_query(query, params)[0]
        
        return result["count"] > 0
    
    def _get_glyph_info(self, glyph_id: str, tx=None) -> Dict[str, Any]:
        """
        Récupère les informations d'un glyphe.
        
        Args:
            glyph_id: ID du glyphe
            tx: Transaction Neo4j (optionnelle)
            
        Returns:
            Dict[str, Any]: Informations du glyphe ou dictionnaire vide si le glyphe n'existe pas
        """
        query = """
        MATCH (g:Glyph)
        WHERE g.id = $glyph_id
        RETURN g.id AS id, g.concept_type AS concept_type, g.natural_prompt AS natural_prompt,
               g.timestamp AS timestamp, g.source AS source
        """
        params = {"glyph_id": glyph_id}
        
        if tx:
            result = tx.run(query, params).single()
        else:
            result = self.neo4j_connector.execute_query(query, params)
            if not result:
                return {}
            result = result[0]
        
        if not result:
            return {}
        
        return dict(result)
    
    def _generate_enriched_description(self, original_description: str, concept_type: str, enrichment_aspects: List[str]) -> str:
        """
        Génère une description enrichie pour un glyphe.
        
        Args:
            original_description: Description originale
            concept_type: Type de concept du glyphe
            enrichment_aspects: Aspects à enrichir
            
        Returns:
            str: Description enrichie
        """
        # Dans une implémentation réelle, cette méthode pourrait utiliser un LLM
        # pour générer une description enrichie. Pour cet exemple, nous simulons
        # simplement un enrichissement.
        
        if not original_description or original_description == "Glyphe sans description":
            base_description = f"Concept de type {concept_type}"
        else:
            base_description = original_description
        
        enrichments = []
        
        if "detailed_description" in enrichment_aspects:
            enrichments.append("Ce concept a été identifié comme un hub important dans le graphe de connaissances.")
        
        if "connection_quality" in enrichment_aspects:
            enrichments.append("Il présente des connexions significatives avec d'autres concepts du même domaine.")
        
        if "technical_details" in enrichment_aspects:
            enrichments.append("Des détails techniques supplémentaires pourraient être ajoutés ici.")
        
        if enrichments:
            return f"{base_description}\n\n{' '.join(enrichments)}"
        else:
            return base_description


# Fonction principale pour les tests
if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Exemple de mock pour Neo4j
    class MockNeo4jConnector:
        def execute_query(self, query, params=None):
            logger.info(f"Exécution de la requête: {query}")
            logger.info(f"Paramètres: {params}")
            
            # Simuler des résultats
            if "CREATE (s:Glyph:ProposedSolution" in query:
                return [{"solution_id": f"sem-proposedsolution-TOPOGEN-{int(time.time())}"}]
            elif "CREATE (source)-[r:$rel_type]->(target)" in query:
                return [{"source_id": params["source_id"], "target_id": params["target_id"], "r_type": params["rel_type"]}]
            elif "SET g.natural_prompt" in query:
                return [{"glyph_id": params["glyph_id"], "enriched_prompt": params["enriched_prompt"]}]
            elif "RETURN count(g)" in query:
                return [{"count": 1}]
            elif "RETURN g.id" in query:
                return [{"id": params["glyph_id"], "concept_type": "TECHNICALCONCEPT", "natural_prompt": "Description test", "timestamp": int(time.time()), "source": "test"}]
            else:
                return []
    
    # Créer un gestionnaire de métriques
    metrics_manager = MetricsManager(expose_http=False)
    
    # Créer un exécuteur d'actions
    executor = GlyphActionExecutor(MockNeo4jConnector(), metrics_manager)
    
    # Exemple d'action d'enrichissement de hub
    from schemas import DetailsStructuredJson, ActionParameters, SourceMetadata
    
    action = PotentialActionGlyph(
        id="sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001",
        action_type=ActionType.ENRICH_HUB_NODE,
        priority=70,
        confidence=0.95,
        details_structured_json=DetailsStructuredJson(
            action_parameters=ActionParameters(
                target_glyph_id="techglyph_202505140900_3",
                enrichment_aspects=["detailed_description", "connection_quality"]
            ),
            source_metadata=SourceMetadata(
                intention_type="ENRICH_HUB_GLYPH",
                target_prompt="Glyphe hub important"
            )
        ),
        details_text="Cette action propose d'enrichir un glyphe hub identifié comme point focal dans le graphe de connaissances."
    )
    
    # Exécuter l'action
    result = executor.execute_action(action)
    
    # Afficher le résultat
    logger.info(f"Résultat de l'exécution: {result.status}")
    logger.info(f"Message: {result.message}")
    if result.data:
        logger.info(f"Données: {result.data.dict()}")
