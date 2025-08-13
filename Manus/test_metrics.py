#!/usr/bin/env python3
# File: test_metrics.py
# Description: Tests unitaires pour l'instrumentation Prometheus

import unittest
import time
from unittest.mock import MagicMock, patch
import logging

from metrics import (
    MetricsManager,
    measure_execution_time,
    track_neo4j_query,
    track_fallback_usage,
    initialize_graph_metrics
)

# Configuration du logging pour les tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test_metrics')


class TestMetricsManager(unittest.TestCase):
    """Tests pour la classe MetricsManager."""

    def setUp(self):
        """Initialisation avant chaque test."""
        self.metrics_manager = MetricsManager(expose_http=False)

    def test_record_pipeline_run(self):
        """Test d'enregistrement d'une exécution du pipeline."""
        # Cette méthode ne retourne rien, on vérifie juste qu'elle s'exécute sans erreur
        self.metrics_manager.record_pipeline_run("success")
        self.metrics_manager.record_pipeline_run("error")

    def test_record_action_execution(self):
        """Test d'enregistrement d'une exécution d'action."""
        self.metrics_manager.record_action_execution("ENRICH_HUB_NODE", "success")
        self.metrics_manager.record_action_execution("CREATE_RELATIONSHIP", "error")

    def test_record_execution_time(self):
        """Test d'enregistrement du temps d'exécution."""
        self.metrics_manager.record_execution_time("test_operation", 1.5)
        self.metrics_manager.record_execution_time("test_operation", 2.5, "error")

    def test_update_graph_metrics(self):
        """Test de mise à jour des métriques du graphe."""
        self.metrics_manager.update_graph_nodes("TECHNICALCONCEPT", 10)
        self.metrics_manager.update_graph_relationships("RELATED_TO_CONCEPT", 20)
        self.metrics_manager.update_topology_metric("avg_degree", 2.5)

    def test_record_fallback_usage(self):
        """Test d'enregistrement de l'utilisation d'un fallback."""
        self.metrics_manager.record_fallback_usage("natural_prompt", "test_module")

    @patch('metrics.push_to_gateway')
    def test_push_metrics(self, mock_push):
        """Test de poussée des métriques vers le Push Gateway."""
        # Configurer le gestionnaire avec une URL de Push Gateway
        metrics_manager = MetricsManager(push_gateway_url="http://localhost:9091")
        
        # Pousser les métriques
        metrics_manager.push_metrics()
        
        # Vérifier que push_to_gateway a été appelé
        mock_push.assert_called_once()

    @patch('metrics.start_http_server')
    def test_http_server_start(self, mock_start):
        """Test de démarrage du serveur HTTP."""
        # Créer un gestionnaire avec exposition HTTP
        metrics_manager = MetricsManager(expose_http=True, http_port=8000)
        
        # Vérifier que start_http_server a été appelé
        mock_start.assert_called_once_with(8000, registry=metrics_manager.registry)


class TestMetricsDecorators(unittest.TestCase):
    """Tests pour les décorateurs de métriques."""

    def setUp(self):
        """Initialisation avant chaque test."""
        self.metrics_manager = MetricsManager(expose_http=False)

    def test_measure_execution_time(self):
        """Test du décorateur measure_execution_time."""
        # Fonction décorée
        @measure_execution_time("test_operation", self.metrics_manager)
        def test_function(sleep_time):
            time.sleep(sleep_time)
            return "success"
        
        # Exécuter la fonction
        result = test_function(0.01)
        
        # Vérifier le résultat
        self.assertEqual(result, "success")

    def test_measure_execution_time_with_error(self):
        """Test du décorateur measure_execution_time avec une erreur."""
        # Fonction décorée qui lève une exception
        @measure_execution_time("test_error", self.metrics_manager)
        def test_function():
            raise ValueError("Test error")
        
        # Vérifier que l'exception est propagée
        with self.assertRaises(ValueError):
            test_function()

    def test_track_neo4j_query(self):
        """Test du décorateur track_neo4j_query."""
        # Fonction décorée
        @track_neo4j_query("test_query", self.metrics_manager)
        def test_function():
            time.sleep(0.01)
            return "query result"
        
        # Exécuter la fonction
        result = test_function()
        
        # Vérifier le résultat
        self.assertEqual(result, "query result")

    def test_track_fallback_usage(self):
        """Test du décorateur track_fallback_usage."""
        # Fonction décorée
        @track_fallback_usage("test_property", "test_module", self.metrics_manager)
        def test_function():
            return {"used_fallback": True}
        
        # Exécuter la fonction
        result = test_function()
        
        # Vérifier le résultat
        self.assertEqual(result["used_fallback"], True)


class TestGraphMetricsInitialization(unittest.TestCase):
    """Tests pour l'initialisation des métriques du graphe."""

    def test_initialize_graph_metrics(self):
        """Test de la fonction initialize_graph_metrics."""
        # Créer un mock pour le connecteur Neo4j
        mock_neo4j = MagicMock()
        
        # Configurer les résultats des requêtes
        mock_neo4j.execute_query.side_effect = [
            # Résultat pour les nœuds
            [
                {"types": ["TECHNICALCONCEPT"], "count": 5},
                {"types": ["PROBLEM"], "count": 3}
            ],
            # Résultat pour les relations
            [
                {"type": "RELATED_TO_CONCEPT", "count": 7},
                {"type": "ADDRESSES_PROBLEM", "count": 2}
            ],
            # Résultat pour les métriques
            [
                {"node_count": 8, "avg_degree": 2.25, "max_degree": 5}
            ]
        ]
        
        # Créer un gestionnaire de métriques
        metrics_manager = MetricsManager(expose_http=False)
        
        # Initialiser les métriques
        initialize_graph_metrics(mock_neo4j, metrics_manager)
        
        # Vérifier que les requêtes ont été exécutées
        self.assertEqual(mock_neo4j.execute_query.call_count, 3)


if __name__ == '__main__':
    unittest.main()
