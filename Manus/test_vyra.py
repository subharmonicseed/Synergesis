import unittest
import os
import shutil
import time
import requests
from unittest.mock import patch

from glyph_bus import get_global_bus, Glyph
from nous import Nous, Concept
from selene import Selene
from vyra import Vyra

# Configuration des chemins pour les tests
TEST_DB_PATH = "./test_nous.db"
TEST_INDEX_DIR = "./test_nous_index"
TEST_API_URL = "http://localhost:8001" # URL mockée pour l'API NOUS
TEST_API_TOKEN = "test_token"

class MockResponse:
    """Classe utilitaire pour mocker les réponses HTTP."""
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
    def json(self): return self._json_data
    def raise_for_status(self): 
        if self.status_code >= 400:
            raise requests.exceptions.RequestException(f"HTTP Error: {self.status_code}")

class TestVyraIntegration(unittest.TestCase):

    def setUp(self):
        """Configure l'environnement de test avant chaque test."""
        # Nettoyage des fichiers de test précédents
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        if os.path.exists(TEST_INDEX_DIR):
            shutil.rmtree(TEST_INDEX_DIR)

        self.bus = get_global_bus()
        self.bus.clear_subscribers() # S'assurer que le bus est propre pour chaque test

        # Initialiser NOUS (pour les tests, nous allons mocker son API)
        self.nous_instance = Nous(db_path=TEST_DB_PATH, index_dir=TEST_INDEX_DIR)

        # Initialiser Selene et Vyra
        self.selene_instance = Selene(TEST_API_URL, self.bus, TEST_API_TOKEN)
        self.vyra_instance = Vyra(self.bus)

        # Liste pour collecter les suggestions générées
        self.generated_suggestions = []
        self.bus.subscribe("creative_suggestion", self._suggestion_handler)

    def tearDown(self):
        """Nettoie l'environnement de test après chaque test."""
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        if os.path.exists(TEST_INDEX_DIR):
            shutil.rmtree(TEST_INDEX_DIR)
        self.bus.clear_subscribers()
        self.generated_suggestions = []

    def _suggestion_handler(self, glyph: Glyph):
        self.generated_suggestions.append(glyph.data)

    @patch("requests.get")
    def test_vyra_generates_suggestions_from_selene_gaps(self, mock_get):
        """
        Teste que Vyra génère correctement des suggestions en réponse aux lacunes
        détectées par Selene.
        """
        # Mock de la réponse de l'API NOUS pour Selene
        mock_get.return_value = MockResponse({
            "id": 1, "concept_id": "concept_with_gaps", 
            "natural_prompt": "Short.",
            "concept_type": "UNKNOWN", "source": "unreliable", 
            "timestamp": time.time(), "resonance": None, "weight": None
        })

        # Simuler un événement concept_changed qui sera traité par Selene
        # Selene va détecter les lacunes et publier un knowledge_gap
        self.bus.publish(Glyph(
            type="concept_changed",
            data={
                "action": "created",
                "concept_id": "concept_with_gaps",
                "concept_type": "UNKNOWN",
                "natural_prompt": "Short.",
                "source": "unreliable",
                "timestamp": time.time()
            },
            source="NOUS"
        ))

        # Attendre que les événements se propagent
        time.sleep(0.5)

        # Vérifier que des suggestions ont été générées par Vyra
        self.assertGreater(len(self.generated_suggestions), 0)
        self.assertEqual(self.generated_suggestions[0]["concept_id"], "concept_with_gaps")

        suggestions = self.generated_suggestions[0]["suggestions"]
        self.assertGreater(len(suggestions), 0)

        # Vérifier les types de suggestions attendus
        suggestion_types = [s["type"] for s in suggestions]
        self.assertIn("ENRICH_CONCEPT_PROMPT", suggestion_types)
        self.assertIn("ENRICH_CONCEPT_PROPERTY", suggestion_types)
        self.assertIn("CLARIFY_CONCEPT_TYPE", suggestion_types)
        self.assertIn("VALIDATE_CONCEPT_SOURCE", suggestion_types)
        # Check for specific missing properties
        missing_props = [s["property"] for s in suggestions if s["type"] == "ENRICH_CONCEPT_PROPERTY"]
        self.assertIn("resonance", missing_props)
        self.assertIn("weight", missing_props)

    @patch("requests.get")
    def test_vyra_no_suggestions_for_no_gaps(self, mock_get):
        """
        Teste que Vyra ne génère pas de suggestions si Selene ne détecte aucune lacune.
        """
        # Mock de la réponse de l'API NOUS pour Selene (concept sans lacunes)
        mock_get.return_value = MockResponse({
            "id": 2, "concept_id": "concept_no_gaps", 
            "natural_prompt": "Un concept très détaillé et bien décrit pour éviter les lacunes et tester la robustesse du système.",
            "concept_type": "TECHNICAL_CONCEPT", "source": "ValidSource", 
            "timestamp": time.time(), "resonance": 0.8, "weight": 0.5
        })

        # Simuler un événement concept_changed
        self.bus.publish(Glyph(
            type="concept_changed",
            data={
                "action": "created",
                "concept_id": "concept_no_gaps",
                "concept_type": "TECHNICAL_CONCEPT",
                "natural_prompt": "Un concept très détaillé et bien décrit pour éviter les lacunes et tester la robustesse du système.",
                "source": "ValidSource",
                "timestamp": time.time()
            },
            source="NOUS"
        ))

        time.sleep(0.5)

        # Aucune suggestion ne devrait avoir été générée
        self.assertEqual(len(self.generated_suggestions), 0)

if __name__ == "__main__":
    unittest.main()


