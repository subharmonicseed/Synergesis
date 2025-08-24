#!/usr/bin/env python3
# File: glyph_topology_enricher.py
# Description: Module d'enrichissement topologique pour les glyphes dans Neo4j

from __future__ import annotations
import logging
import sys
import os
import time
import json
from typing import Dict, Any, List, Optional, Tuple, Union

# --- Logging Setup ---
log_topology = logging.getLogger('glyph_topology_enricher')
if not log_topology.handlers:
    h_topology = logging.StreamHandler(sys.stdout)
    h_topology.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log_topology.addHandler(h_topology)
log_topology.setLevel(logging.INFO)

# --- Module Imports & Fallbacks ---
try:
    from neo4j import GraphDatabase, basic_auth, exceptions as neo4j_exceptions
    NEO4J_DRIVER_AVAILABLE = True
except ImportError:
    NEO4J_DRIVER_AVAILABLE = False
    log_topology.error("Neo4j driver not available. Please install with: pip install neo4j")
    # Dummy classes for static analysis
    class GraphDatabase:
        @staticmethod
        def driver(uri, auth):
            log_topology.warning("Neo4j driver dummy.")
            return None

    class basic_auth:
        def __init__(self, *_, **__):
            pass

    class neo4j_exceptions:
        class Neo4jError(Exception):
            pass

        class ClientError(Neo4jError):
            pass

# --- Helper Functions ---
def _get_env_topology(key: str, default: Optional[str] = None) -> str:
    """Get environment variable with fallback."""
    val = os.getenv(key, default)
    if val is None and default is None:
        raise EnvironmentError(f"Topology Enricher Env var {key} required.")
    return val or ""

class GlyphTopologyEnricher:
    """
    Module d'enrichissement topologique pour les glyphes dans Neo4j.
    Calcule et stocke des métriques de centralité et d'autres propriétés topologiques.
    """
    def __init__(self, neo4j_connector=None, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        """
        Initialise l'enrichisseur de topologie.
        
        Args:
            neo4j_connector: Connecteur Neo4j existant (optionnel)
            uri: URI de connexion Neo4j (défaut: depuis env NEO4J_URI ou "bolt://localhost:7687")
            user: Nom d'utilisateur Neo4j (défaut: depuis env NEO4J_USER ou "neo4j")
            password: Mot de passe Neo4j (défaut: depuis env NEO4J_PASSWORD)
        """
        self.driver = None
        
        # Si un connecteur Neo4j est fourni, l'utiliser directement
        if neo4j_connector is not None:
            if hasattr(neo4j_connector, 'driver'):
                self.driver = neo4j_connector.driver
                log_topology.info("GlyphTopologyEnricher using provided Neo4j connector")
                return
            else:
                log_topology.warning("Provided Neo4j connector does not have a driver attribute")
        
        if not NEO4J_DRIVER_AVAILABLE:
            log_topology.error("GlyphTopologyEnricher initialized but Neo4j driver is NOT available.")
            return
            
        self.uri = uri or _get_env_topology("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or _get_env_topology("NEO4J_USER", "neo4j")
        pwd = password or _get_env_topology("NEO4J_PASSWORD", "synergesis_password")
        
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=basic_auth(self.user, pwd))
            self.driver.verify_connectivity()
            log_topology.info(f"GlyphTopologyEnricher connected to {self.uri}")
        except Exception as e:
            log_topology.critical(f"GlyphTopologyEnricher connection failed: {e}", exc_info=True)
            self.driver = None

    def close(self):
        """Ferme la connexion Neo4j."""
        if self.driver:
            self.driver.close()
            log_topology.info("GlyphTopologyEnricher connection closed.")

    def test_connection(self) -> bool:
        """Teste la connexion Neo4j."""
        if not self.driver:
            log_topology.error("Cannot test connection: Neo4j driver not available.")
            return False
            
        try:
            with self.driver.session(database="neo4j") as session:
                result = session.run("RETURN 1 as test")
                return result.single()["test"] == 1
        except Exception as e:
            log_topology.error(f"Connection test failed: {e}")
            return False

    def enrich_graph(self, similarity_threshold: float = 0.7, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Enrichit le graphe avec des métriques topologiques et des relations de similarité.
        Cette méthode orchestre l'ensemble du processus d'enrichissement topologique.
        
        Args:
            similarity_threshold: Seuil de similarité pour les relations SIMILAR_TO
            output_dir: Répertoire de sortie pour les rapports (optionnel)
            
        Returns:
            Dict contenant les résultats de l'enrichissement
        """
        log_topology.info("Starting graph topology enrichment process")
        start_time = time.time()
        
        results = {
            "status": "success",
            "timestamp": int(time.time()),
            "execution_time_ms": 0,
            "centrality_results": None,
            "similarity_results": None,
            "topology_report": None,
            "errors": []
        }
        
        # Étape 1: Calcul et stockage du degré de centralité
        try:
            log_topology.info("Computing and storing degree centrality")
            centrality_results = self.compute_and_store_degree_centrality()
            results["centrality_results"] = centrality_results
            
            if centrality_results["status"] == "error":
                results["errors"].append({
                    "step": "compute_degree_centrality",
                    "message": centrality_results.get("message", "Unknown error")
                })
                results["status"] = "partial_success"
        except Exception as e:
            log_topology.error(f"Error in degree centrality computation: {e}", exc_info=True)
            results["errors"].append({
                "step": "compute_degree_centrality",
                "message": str(e)
            })
            results["status"] = "partial_success"
        
        # Étape 2: Calcul et stockage des relations de similarité
        try:
            log_topology.info(f"Computing and storing similarity links (threshold: {similarity_threshold})")
            similarity_results = self.compute_and_store_similarity_links(threshold=similarity_threshold)
            results["similarity_results"] = similarity_results
            
            if similarity_results["status"] == "error":
                results["errors"].append({
                    "step": "compute_similarity_links",
                    "message": similarity_results.get("message", "Unknown error")
                })
                results["status"] = "partial_success"
        except Exception as e:
            log_topology.error(f"Error in similarity links computation: {e}", exc_info=True)
            results["errors"].append({
                "step": "compute_similarity_links",
                "message": str(e)
            })
            results["status"] = "partial_success"
        
        # Étape 3: Génération du rapport de topologie
        try:
            log_topology.info("Generating topology report")
            topology_report = self.generate_topology_report()
            results["topology_report"] = topology_report
            
            if topology_report["status"] == "error":
                results["errors"].append({
                    "step": "generate_topology_report",
                    "message": topology_report.get("message", "Unknown error")
                })
                results["status"] = "partial_success"
        except Exception as e:
            log_topology.error(f"Error in topology report generation: {e}", exc_info=True)
            results["errors"].append({
                "step": "generate_topology_report",
                "message": str(e)
            })
            results["status"] = "partial_success"
        
        # Sauvegarder les résultats si un répertoire de sortie est spécifié
        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
                timestamp = int(time.time())
                output_file = os.path.join(output_dir, f"topology_enrichment_{timestamp}.json")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                
                log_topology.info(f"Enrichment results saved to {output_file}")
                results["output_file"] = output_file
            except Exception as e:
                log_topology.error(f"Error saving enrichment results: {e}", exc_info=True)
                results["errors"].append({
                    "step": "save_results",
                    "message": str(e)
                })
        
        # Calculer le temps d'exécution total
        results["execution_time_ms"] = int((time.time() - start_time) * 1000)
        
        # Résumé des résultats
        if not results["errors"]:
            log_topology.info(f"Graph topology enrichment completed successfully in {results['execution_time_ms']}ms")
        else:
            log_topology.warning(f"Graph topology enrichment completed with {len(results['errors'])} errors in {results['execution_time_ms']}ms")
        
        return results

    def compute_and_store_degree_centrality(self) -> Dict[str, Any]:
        """
        Calcule et stocke le degré de centralité pour tous les glyphes.
        Cette métrique indique le nombre de connexions directes de chaque glyphe.
        
        Returns:
            Dict contenant les statistiques de l'opération
        """
        if not self.driver:
            log_topology.error("Cannot compute degree centrality: Neo4j driver not available.")
            return {"status": "error", "message": "Neo4j driver not available"}
            
        start_time = time.time()
        stats = {
            "status": "success",
            "glyphs_processed": 0,
            "properties_set": 0,
            "errors": 0,
            "execution_time_ms": 0
        }
        
        try:
            with self.driver.session(database="neo4j") as session:
                # Requête Cypher pour calculer et stocker le degré de centralité
                # Cette requête calcule à la fois le degré total, entrant et sortant
                # Utilisation de COUNT {} au lieu de size() pour compatibilité Neo4j 5
                result = session.run("""
                MATCH (g:Glyph)
                WITH g, 
                     COUNT { (g)--() } AS total_degree,
                     COUNT { (g)<--() } AS in_degree,
                     COUNT { (g)-->() } AS out_degree
                SET g.degree_centrality = total_degree,
                    g.in_degree = in_degree,
                    g.out_degree = out_degree
                RETURN count(g) AS glyphs_processed
                """)
                
                record = result.single()
                if record:
                    stats["glyphs_processed"] = record["glyphs_processed"]
                    stats["properties_set"] = record["glyphs_processed"] * 3  # 3 propriétés par glyphe
                
                # Récupérer les statistiques de distribution des degrés
                result = session.run("""
                MATCH (g:Glyph)
                WHERE g.degree_centrality IS NOT NULL
                RETURN min(g.degree_centrality) AS min_degree,
                       max(g.degree_centrality) AS max_degree,
                       avg(g.degree_centrality) AS avg_degree,
                       count(g) AS total_glyphs
                """)
                
                record = result.single()
                if record:
                    stats["min_degree"] = record["min_degree"]
                    stats["max_degree"] = record["max_degree"]
                    stats["avg_degree"] = record["avg_degree"]
                    stats["total_glyphs"] = record["total_glyphs"]
                
                # Récupérer les glyphes avec le plus haut degré de centralité
                result = session.run("""
                MATCH (g:Glyph)
                WHERE g.degree_centrality IS NOT NULL
                RETURN g.id, g.natural_prompt, g.degree_centrality, g.in_degree, g.out_degree
                ORDER BY g.degree_centrality DESC
                LIMIT 5
                """)
                
                top_glyphs = []
                for record in result:
                    top_glyphs.append({
                        "id": record["g.id"],
                        "natural_prompt": record["g.natural_prompt"],
                        "degree_centrality": record["g.degree_centrality"],
                        "in_degree": record["g.in_degree"],
                        "out_degree": record["g.out_degree"]
                    })
                
                stats["top_glyphs"] = top_glyphs
                
        except Exception as e:
            log_topology.error(f"Error computing degree centrality: {e}", exc_info=True)
            stats["status"] = "error"
            stats["message"] = str(e)
            stats["errors"] = 1
        
        stats["execution_time_ms"] = int((time.time() - start_time) * 1000)
        log_topology.info(f"Degree centrality computation completed in {stats['execution_time_ms']}ms. "
                         f"Processed {stats['glyphs_processed']} glyphs.")
        
        return stats

    def compute_and_store_similarity_links(self, threshold: float = 0.7) -> Dict[str, Any]:
        """
        Crée des relations SIMILAR_TO entre glyphes ayant des tags communs.
        Cette implémentation utilise la similarité de Jaccard sur les tags.
        
        Args:
            threshold: Seuil de similarité (0.0-1.0) pour créer une relation
            
        Returns:
            Dict contenant les statistiques de l'opération
        """
        if not self.driver:
            log_topology.error("Cannot compute similarity links: Neo4j driver not available.")
            return {"status": "error", "message": "Neo4j driver not available"}
            
        start_time = time.time()
        stats = {
            "status": "success",
            "relationships_created": 0,
            "glyphs_processed": 0,
            "errors": 0,
            "execution_time_ms": 0
        }
        
        try:
            with self.driver.session(database="neo4j") as session:
                # Requête Cypher pour calculer la similarité de Jaccard sur les tags
                # et créer des relations SIMILAR_TO entre glyphes similaires
                result = session.run("""
                MATCH (g1:Glyph), (g2:Glyph)
                WHERE g1 <> g2 AND g1.id < g2.id
                  AND g1.tags IS NOT NULL AND g2.tags IS NOT NULL
                  AND size(g1.tags) > 0 AND size(g2.tags) > 0
                WITH g1, g2,
                     [tag IN g1.tags WHERE tag IN g2.tags] AS common_tags,
                     g1.tags + [tag IN g2.tags WHERE NOT tag IN g1.tags] AS all_tags
                WITH g1, g2, 
                     CASE WHEN size(all_tags) > 0 
                          THEN toFloat(size(common_tags)) / size(all_tags) 
                          ELSE 0 END AS jaccard_similarity
                WHERE jaccard_similarity >= $threshold
                MERGE (g1)-[r:SIMILAR_TO]-(g2)
                SET r.score = jaccard_similarity,
                    r.calculated_at = timestamp()
                RETURN count(r) AS relationships_created
                """, threshold=threshold)
                
                re
(Content truncated due to size limit. Use line ranges to read in chunks)