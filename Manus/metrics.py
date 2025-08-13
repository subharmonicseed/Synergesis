#!/usr/bin/env python3
# File: metrics.py
# Description: Instrumentation Prometheus pour le monitoring du pipeline Synergesis

import time
import logging
import threading
from typing import Dict, Optional, Any, List, Union
from prometheus_client import Counter, Gauge, Histogram, Summary
from prometheus_client import start_http_server, push_to_gateway
from prometheus_client import CollectorRegistry, REGISTRY

# Configuration du logging
logger = logging.getLogger('metrics')


class MetricsManager:
    """
    Gestionnaire de métriques Prometheus pour le pipeline Synergesis.
    Centralise la définition et l'exposition des métriques.
    """
    
    def __init__(self, expose_http: bool = False, http_port: int = 8000,
                 push_gateway_url: str = "", push_job_name: str = "synergesis_pipeline",
                 registry: Optional[CollectorRegistry] = None):
        """
        Initialise le gestionnaire de métriques.
        
        Args:
            expose_http: Si True, expose les métriques via HTTP
            http_port: Port pour l'exposition HTTP
            push_gateway_url: URL du Push Gateway Prometheus (vide pour désactiver)
            push_job_name: Nom du job pour le Push Gateway
            registry: Registre Prometheus personnalisé (None pour utiliser le registre par défaut)
        """
        # Utiliser un registre local pour éviter les conflits dans les tests
        self.registry = registry or CollectorRegistry()
        self.push_gateway_url = push_gateway_url
        self.push_job_name = push_job_name
        
        # Métriques pour le pipeline
        self.pipeline_runs = Counter(
            'synergesis_pipeline_runs_total',
            'Nombre total d\'exécutions du pipeline',
            ['status'],
            registry=self.registry
        )
        
        self.action_executions = Counter(
            'synergesis_action_executions_total',
            'Nombre d\'exécutions d\'actions',
            ['action_type', 'status'],
            registry=self.registry
        )
        
        self.execution_time = Histogram(
            'synergesis_execution_time_seconds',
            'Temps d\'exécution des opérations',
            ['operation', 'status'],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
            registry=self.registry
        )
        
        self.fallback_usage = Counter(
            'synergesis_fallback_usage_total',
            'Utilisation des mécanismes de fallback',
            ['property', 'module'],
            registry=self.registry
        )
        
        self.errors = Counter(
            'synergesis_errors_total',
            'Nombre d\'erreurs',
            ['operation', 'error_type'],
            registry=self.registry
        )
        
        # Métriques pour le graphe
        self.graph_nodes = Gauge(
            'synergesis_graph_nodes_total',
            'Nombre de nœuds dans le graphe',
            ['type'],
            registry=self.registry
        )
        
        self.graph_relationships = Gauge(
            'synergesis_graph_relationships_total',
            'Nombre de relations dans le graphe',
            ['type'],
            registry=self.registry
        )
        
        self.topology_metrics = Gauge(
            'synergesis_graph_topology_metrics',
            'Métriques topologiques du graphe',
            ['metric'],
            registry=self.registry
        )
        
        # Démarrer le serveur HTTP si demandé
        if expose_http:
            try:
                start_http_server(http_port, registry=self.registry)
                logger.info(f"Serveur HTTP pour les métriques démarré sur le port {http_port}")
            except Exception as e:
                logger.error(f"Erreur lors du démarrage du serveur HTTP pour les métriques: {e}")
    
    def record_pipeline_run(self, status: str = "success") -> None:
        """
        Enregistre une exécution du pipeline.
        
        Args:
            status: Statut de l'exécution (success, error, etc.)
        """
        self.pipeline_runs.labels(status=status).inc()
    
    def record_action_execution(self, action_type: str, status: str = "success") -> None:
        """
        Enregistre une exécution d'action.
        
        Args:
            action_type: Type d'action exécutée
            status: Statut de l'exécution (success, error, etc.)
        """
        self.action_executions.labels(action_type=action_type, status=status).inc()
    
    def record_execution_time(self, operation: str, execution_time: float, status: str = "success") -> None:
        """
        Enregistre le temps d'exécution d'une opération.
        
        Args:
            operation: Nom de l'opération
            execution_time: Temps d'exécution en secondes
            status: Statut de l'exécution (success, error, etc.)
        """
        self.execution_time.labels(operation=operation, status=status).observe(execution_time)
    
    def record_error(self, operation: str, error_type: str) -> None:
        """
        Enregistre une erreur.
        
        Args:
            operation: Nom de l'opération
            error_type: Type d'erreur
        """
        self.errors.labels(operation=operation, error_type=error_type).inc()
    
    def record_fallback_usage(self, property_name: str, module: str) -> None:
        """
        Enregistre l'utilisation d'un mécanisme de fallback.
        
        Args:
            property_name: Nom de la propriété manquante
            module: Module utilisant le fallback
        """
        self.fallback_usage.labels(property=property_name, module=module).inc()
    
    def update_graph_nodes(self, node_type: str, count: int) -> None:
        """
        Met à jour le nombre de nœuds dans le graphe.
        
        Args:
            node_type: Type de nœud
            count: Nombre de nœuds à ajouter (ou soustraire si négatif)
        """
        self.graph_nodes.labels(type=node_type).inc(count)
    
    def update_graph_relationships(self, relationship_type: str, count: int) -> None:
        """
        Met à jour le nombre de relations dans le graphe.
        
        Args:
            relationship_type: Type de relation
            count: Nombre de relations à ajouter (ou soustraire si négatif)
        """
        self.graph_relationships.labels(type=relationship_type).inc(count)
    
    def update_topology_metric(self, metric_name: str, value: float) -> None:
        """
        Met à jour une métrique topologique du graphe.
        
        Args:
            metric_name: Nom de la métrique
            value: Valeur de la métrique
        """
        self.topology_metrics.labels(metric=metric_name).set(value)
    
    def push_metrics(self) -> None:
        """
        Pousse les métriques vers le Push Gateway Prometheus.
        Ne fait rien si push_gateway_url est vide.
        """
        if not self.push_gateway_url:
            return
        
        try:
            push_to_gateway(
                self.push_gateway_url,
                job=self.push_job_name,
                registry=self.registry
            )
            logger.info(f"Métriques poussées vers {self.push_gateway_url}")
        except Exception as e:
            logger.error(f"Erreur lors de la poussée des métriques: {e}")


def measure_execution_time(operation_name: str, metrics_manager: Optional[MetricsManager] = None):
    """
    Décorateur qui mesure le temps d'exécution d'une fonction et l'enregistre dans Prometheus.
    
    Args:
        operation_name: Nom de l'opération pour l'étiquette Prometheus
        metrics_manager: Gestionnaire de métriques Prometheus
        
    Returns:
        Fonction décorée avec mesure du temps d'exécution
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                if metrics_manager:
                    metrics_manager.record_execution_time(operation_name, execution_time)
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                if metrics_manager:
                    metrics_manager.record_execution_time(operation_name, execution_time, "error")
                    metrics_manager.record_error(operation_name, str(type(e).__name__))
                
                raise
        
        return wrapper
    
    return decorator


def track_neo4j_query(query_type: str, metrics_manager: Optional[MetricsManager] = None):
    """
    Décorateur qui mesure le temps d'exécution d'une requête Neo4j et l'enregistre dans Prometheus.
    
    Args:
        query_type: Type de requête pour l'étiquette Prometheus
        metrics_manager: Gestionnaire de métriques Prometheus
        
    Returns:
        Fonction décorée avec mesure du temps d'exécution
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                if metrics_manager:
                    metrics_manager.record_execution_time(f"neo4j_query_{query_type}", execution_time)
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                if metrics_manager:
                    metrics_manager.record_execution_time(f"neo4j_query_{query_type}", execution_time, "error")
                    metrics_manager.record_error(f"neo4j_query_{query_type}", str(type(e).__name__))
                
                raise
        
        return wrapper
    
    return decorator


def track_fallback_usage(property_name: str, module_name: str, metrics_manager: Optional[MetricsManager] = None):
    """
    Décorateur qui enregistre l'utilisation d'un mécanisme de fallback dans Prometheus.
    
    Args:
        property_name: Nom de la propriété manquante
        module_name: Nom du module utilisant le fallback
        metrics_manager: Gestionnaire de métriques Prometheus
        
    Returns:
        Fonction décorée avec enregistrement de l'utilisation du fallback
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            if isinstance(result, dict) and result.get('used_fallback'):
                if metrics_manager:
                    metrics_manager.record_fallback_usage(property_name, module_name)
            
            return result
        
        return wrapper
    
    return decorator


def initialize_graph_metrics(neo4j_connector, metrics_manager: MetricsManager) -> None:
    """
    Initialise les métriques du graphe à partir de Neo4j.
    
    Args:
        neo4j_connector: Connecteur Neo4j
        metrics_manager: Gestionnaire de métriques Prometheus
    """
    try:
        # Récupérer le nombre de nœuds par type
        nodes_query = """
        MATCH (n)
        WITH labels(n) AS types, count(n) AS count
        RETURN types, count
        """
        
        nodes_result = neo4j_connector.execute_query(nodes_query)
        
        for record in nodes_result:
            node_type = record["types"][0] if record["types"] else "UNKNOWN"
            count = record["count"]
            metrics_manager.update_graph_nodes(node_type, count)
        
        # Récupérer le nombre de relations par type
        relationships_query = """
        MATCH ()-[r]-()
        WITH type(r) AS type, count(r) AS count
        RETURN type, count
        """
        
        relationships_result = neo4j_connector.execute_query(relationships_query)
        
        for record in relationships_result:
            relationship_type = record["type"]
            count = record["count"]
            metrics_manager.update_graph_relationships(relationship_type, count)
        
        # Récupérer les métriques topologiques
        topology_query = """
        MATCH (n)
        WITH count(n) AS node_count, avg(apoc.node.degree(n)) AS avg_degree, max(apoc.node.degree(n)) AS max_degree
        RETURN node_count, avg_degree, max_degree
        """
        
        topology_result = neo4j_connector.execute_query(topology_query)
        
        if topology_result:
            record = topology_result[0]
            metrics_manager.update_topology_metric("node_count", record["node_count"])
            metrics_manager.update_topology_metric("avg_degree", record["avg_degree"])
            metrics_manager.update_topology_metric("max_degree", record["max_degree"])
        
        logger.info("Métriques du graphe initialisées avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation des métriques du graphe: {e}")


# Fonction principale pour les tests
if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Créer un gestionnaire de métriques avec exposition HTTP
    metrics_manager = MetricsManager(expose_http=True, http_port=8000)
    
    # Enregistrer quelques métriques
    metrics_manager.record_pipeline_run("success")
    metrics_manager.record_action_execution("CREATE_RELATIONSHIP", "success")
    metrics_manager.record_execution_time("test_operation", 1.5)
    metrics_manager.record_fallback_usage("natural_prompt", "test_module")
    
    # Exemple d'utilisation du décorateur
    @measure_execution_time("decorated_operation", metrics_manager)
    def test_function():
        time.sleep(0.5)
        return "success"
    
    # Exécuter la fonction décorée
    result = test_function()
    
    logger.info(f"Résultat: {result}")
    logger.info("Métriques exposées sur http://localhost:8000")
    
    # Garder le serveur HTTP en vie pour les tests
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Arrêt du serveur HTTP")
