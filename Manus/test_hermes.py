"""Tests pour l'agent Hermes."""
import unittest
import time
import json
from unittest.mock import Mock, patch, MagicMock
import requests

from src.hermes import (
    Hermes, SuggestionAppliedEvent, SuggestionStatus,
    EnrichConceptPromptHandler, CompleteMissingFieldHandler,
    ClarifyVagueDescriptionHandler, AddContextualRelationsHandler,
    TaskDispatcher, SuggestionQueue
)
from src.vyra import CreativeSuggestion


class TestSuggestionQueue(unittest.TestCase):
    """Tests pour la file d'attente de suggestions."""
    
    def setUp(self):
        self.queue = SuggestionQueue()
    
    def test_put_and_get(self):
        """Test d'ajout et de récupération de suggestions."""
        suggestion = CreativeSuggestion(
            concept_id="test_concept",
            suggestion_type="ENRICH_CONCEPT_PROMPT",
            title="Test suggestion",
            description="Test description"
        )
        
        self.queue.put(suggestion)
        retrieved = self.queue.get(timeout=1.0)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.concept_id, "test_concept")
        self.assertEqual(retrieved.suggestion_type, "ENRICH_CONCEPT_PROMPT")
    
    def test_get_timeout(self):
        """Test du timeout lors de la récupération."""
        result = self.queue.get(timeout=0.1)
        self.assertIsNone(result)
    
    def test_mark_done(self):
        """Test du marquage comme terminé."""
        suggestion = CreativeSuggestion(
            concept_id="test_concept",
            suggestion_type="ENRICH_CONCEPT_PROMPT",
            title="Test suggestion",
            description="Test description"
        )
        
        self.queue.put(suggestion)
        retrieved = self.queue.get()
        
        self.assertIn(retrieved.suggestion_id, self.queue.processing)
        
        self.queue.mark_done(retrieved.suggestion_id)
        self.assertNotIn(retrieved.suggestion_id, self.queue.processing)


class TestActionHandlers(unittest.TestCase):
    """Tests pour les gestionnaires d'actions."""
    
    def setUp(self):
        self.nous_api_url = "http://localhost:8001"
        self.api_token = "test_token"
    
    @patch('requests.get')
    @patch('requests.put')
    def test_enrich_concept_prompt_handler(self, mock_put, mock_get):
        """Test du gestionnaire d'enrichissement de prompt."""
        # Mock de la réponse GET
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "concept_id": "test_concept",
            "natural_prompt": "Prompt original"
        }
        mock_get.return_value.raise_for_status = Mock()
        
        # Mock de la réponse PUT
        mock_put.return_value.status_code = 200
        mock_put.return_value.raise_for_status = Mock()
        
        handler = EnrichConceptPromptHandler(self.nous_api_url, self.api_token)
        
        suggestion = CreativeSuggestion(
            concept_id="test_concept",
            suggestion_type="ENRICH_CONCEPT_PROMPT",
            title="Enrichir le prompt",
            description="Le prompt est trop court",
            metadata={"enriched_prompt": "Prompt enrichi"}
        )
        
        result = handler.execute(suggestion)
        
        self.assertEqual(result.status, SuggestionStatus.SUCCESS)
        self.assertEqual(result.concept_id, "test_concept")
        self.assertIn("succès", result.details)
        
        # Vérifier que les bonnes requêtes ont été faites
        mock_get.assert_called_once()
        mock_put.assert_called_once()
    
    @patch('requests.get')
    @patch('requests.put')
    def test_complete_missing_field_handler(self, mock_put, mock_get):
        """Test du gestionnaire de complétion de champs."""
        # Mock de la réponse GET
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "concept_id": "test_concept",
            "natural_prompt": "Test concept"
        }
        mock_get.return_value.raise_for_status = Mock()
        
        # Mock de la réponse PUT
        mock_put.return_value.status_code = 200
        mock_put.return_value.raise_for_status = Mock()
        
        handler = CompleteMissingFieldHandler(self.nous_api_url, self.api_token)
        
        suggestion = CreativeSuggestion(
            concept_id="test_concept",
            suggestion_type="COMPLETE_MISSING_FIELD",
            title="Compléter le champ resonance",
            description="Le champ resonance est manquant",
            metadata={"field_name": "resonance", "field_value": 0.8}
        )
        
        result = handler.execute(suggestion)
        
        self.assertEqual(result.status, SuggestionStatus.SUCCESS)
        self.assertEqual(result.concept_id, "test_concept")
        self.assertIn("resonance", result.details)
    
    @patch('requests.get')
    def test_handler_concept_not_found(self, mock_get):
        """Test du gestionnaire quand le concept n'est pas trouvé."""
        # Mock d'une erreur 404
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")
        
        handler = EnrichConceptPromptHandler(self.nous_api_url, self.api_token)
        
        suggestion = CreativeSuggestion(
            concept_id="nonexistent_concept",
            suggestion_type="ENRICH_CONCEPT_PROMPT",
            title="Enrichir le prompt",
            description="Le prompt est trop court",
            metadata={"enriched_prompt": "Prompt enrichi"}
        )
        
        result = handler.execute(suggestion)
        
        self.assertEqual(result.status, SuggestionStatus.FAILED)
        self.assertIn("récupérer", result.details)


class TestTaskDispatcher(unittest.TestCase):
    """Tests pour le distributeur de tâches."""
    
    def setUp(self):
        self.dispatcher = TaskDispatcher("http://localhost:8001", "test_token")
    
    def test_supported_suggestion_types(self):
        """Test des types de suggestions supportés."""
        expected_types = [
            "ENRICH_CONCEPT_PROMPT",
            "COMPLETE_MISSING_FIELD", 
            "CLARIFY_VAGUE_DESCRIPTION",
            "ADD_CONTEXTUAL_RELATIONS"
        ]
        
        for suggestion_type in expected_types:
            self.assertIn(suggestion_type, self.dispatcher.handlers)
    
    def test_unsupported_suggestion_type(self):
        """Test avec un type de suggestion non supporté."""
        suggestion = CreativeSuggestion(
            concept_id="test_concept",
            suggestion_type="UNSUPPORTED_TYPE",
            title="Test suggestion",
            description="Test description"
        )
        
        result = self.dispatcher.dispatch(suggestion)
        
        self.assertEqual(result.status, SuggestionStatus.FAILED)
        self.assertIn("non supporté", result.details)


class TestHermes(unittest.TestCase):
    """Tests pour l'agent Hermes."""
    
    def setUp(self):
        self.hermes = Hermes()
    
    def tearDown(self):
        if self.hermes.running:
            self.hermes.stop()
    
    def test_initialization(self):
        """Test de l'initialisation de Hermes."""
        self.assertIsNotNone(self.hermes.bus)
        self.assertIsNotNone(self.hermes.suggestion_queue)
        self.assertIsNotNone(self.hermes.task_dispatcher)
        self.assertFalse(self.hermes.running)
    
    def test_start_stop(self):
        """Test du démarrage et de l'arrêt de Hermes."""
        self.assertFalse(self.hermes.running)
        
        self.hermes.start()
        self.assertTrue(self.hermes.running)
        self.assertIsNotNone(self.hermes.worker_thread)
        
        self.hermes.stop()
        self.assertFalse(self.hermes.running)
    
    def test_get_status(self):
        """Test de la récupération du statut."""
        status = self.hermes.get_status()
        
        self.assertIn("running", status)
        self.assertIn("queue_size", status)
        self.assertIn("processing_count", status)
        self.assertIn("supported_suggestion_types", status)
        
        self.assertFalse(status["running"])
        self.assertEqual(status["queue_size"], 0)
        self.assertEqual(status["processing_count"], 0)
        self.assertIsInstance(status["supported_suggestion_types"], list)
    
    @patch('src.hermes.TaskDispatcher.dispatch')
    def test_creative_suggestion_processing(self, mock_dispatch):
        """Test du traitement d'une suggestion créative."""
        # Mock du résultat du dispatcher
        mock_result = SuggestionAppliedEvent(
            event_id="test_event",
            suggestion_id="test_suggestion",
            concept_id="test_concept",
            status=SuggestionStatus.SUCCESS,
            details="Test réussi"
        )
        mock_dispatch.return_value = mock_result
        
        # Démarrer Hermes
        self.hermes.start()
        
        # Simuler une suggestion créative
        suggestion_data = {
            "concept_id": "test_concept",
            "suggestion_type": "ENRICH_CONCEPT_PROMPT",
            "title": "Test suggestion",
            "description": "Test description",
            "metadata": {"enriched_prompt": "Prompt enrichi"}
        }
        
        # Publier la suggestion
        self.hermes._on_creative_suggestion(suggestion_data)
        
        # Attendre un peu pour le traitement
        time.sleep(0.5)
        
        # Vérifier que le dispatcher a été appelé
        mock_dispatch.assert_called_once()
        
        # Arrêter Hermes
        self.hermes.stop()


class TestSuggestionAppliedEvent(unittest.TestCase):
    """Tests pour l'événement SuggestionAppliedEvent."""
    
    def test_event_creation(self):
        """Test de la création d'un événement."""
        event = SuggestionAppliedEvent(
            event_id="test_event",
            suggestion_id="test_suggestion",
            concept_id="test_concept",
            status=SuggestionStatus.SUCCESS,
            details="Test réussi"
        )
        
        self.assertEqual(event.event_id, "test_event")
        self.assertEqual(event.suggestion_id, "test_suggestion")
        self.assertEqual(event.concept_id, "test_concept")
        self.assertEqual(event.status, SuggestionStatus.SUCCESS)
        self.assertEqual(event.details, "Test réussi")
        self.assertIsNotNone(event.timestamp)
    
    def test_to_dict(self):
        """Test de la conversion en dictionnaire."""
        event = SuggestionAppliedEvent(
            event_id="test_event",
            suggestion_id="test_suggestion",
            concept_id="test_concept",
            status=SuggestionStatus.SUCCESS,
            details="Test réussi"
        )
        
        event_dict = event.to_dict()
        
        self.assertEqual(event_dict["event_id"], "test_event")
        self.assertEqual(event_dict["suggestion_id"], "test_suggestion")
        self.assertEqual(event_dict["concept_id"], "test_concept")
        self.assertEqual(event_dict["status"], "success")
        self.assertEqual(event_dict["details"], "Test réussi")
        self.assertIn("timestamp", event_dict)


if __name__ == "__main__":
    unittest.main()

