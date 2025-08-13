import unittest
import requests
import time
import subprocess
import os
import json
import sys

# Assurez-vous que le chemin vers le répertoire src est dans le PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from nous import Nous, Concept
from thales import Thales

class TestThalesE2E(unittest.TestCase):
    NOUS_API_URL = "http://localhost:8001"
    DB_PATH = "/home/ubuntu/synergesis_pipeline/nous.db"
    INDEX_DIR = "/home/ubuntu/synergesis_pipeline/nous_index"
    API_PROCESS = None

    @classmethod
    def setUpClass(cls):
        # Nettoyer les fichiers de la base de données et de l'index Whoosh
        if os.path.exists("/home/ubuntu/synergesis_pipeline/nous.db"):
            os.remove("/home/ubuntu/synergesis_pipeline/nous.db")
        if os.path.exists("/home/ubuntu/synergesis_pipeline/nous_index"):
            import shutil
            shutil.rmtree("/home/ubuntu/synergesis_pipeline/nous_index")

        # Lancer l'API NOUS en arrière-plan
        cls.API_PROCESS = subprocess.Popen(
            ["uvicorn", "nous_api:app", "--host", "0.0.0.0", "--port", "8001"],
            cwd="/home/ubuntu/synergesis_pipeline/src",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(os.environ, NOUS_API_TOKEN=os.getenv('NOUS_API_TOKEN', 'synergesis_nous_token_2025'))
        )
        time.sleep(5)  # Attendre que l'API démarre

        # Vérifier que l'API est bien démarrée
        try:
            response = requests.get(f"{cls.NOUS_API_URL}/health")
            response.raise_for_status()
            print("API NOUS démarrée et fonctionnelle.")
        except requests.exceptions.RequestException as e:
            print(f"Erreur au démarrage de l'API NOUS: {e}")
            cls.API_PROCESS.kill()
            raise

    @classmethod
    def tearDownClass(cls):
        # Arrêter le processus de l'API
        if cls.API_PROCESS:
            cls.API_PROCESS.kill()
            cls.API_PROCESS.wait()
            print("API NOUS arrêtée.")
        
        # Nettoyer les fichiers de la base de données et de l'index Whoosh
        if os.path.exists("/home/ubuntu/synergesis_pipeline/nous.db"):
            os.remove("/home/ubuntu/synergesis_pipeline/nous.db")
        if os.path.exists("/home/ubuntu/synergesis_pipeline/nous_index"):
            import shutil
            shutil.rmtree("/home/ubuntu/synergesis_pipeline/nous_index")

    def setUp(self):
        self.thales = Thales(nous_api_url=self.NOUS_API_URL)
        # S'assurer que la base de données est vide avant chaque test
        self._clear_all_concepts_via_api()

    def _clear_all_concepts_via_api(self):
        response = requests.get(f"{self.NOUS_API_URL}/concepts", headers={"Authorization": f"Bearer {os.getenv('NOUS_API_TOKEN', 'synergesis_nous_token_2025')}"})
        response.raise_for_status()
        concepts_data = response.json()
        for concept_dict in concepts_data:
            # Assuming concept_dict is a dictionary representation of ConceptOut
            requests.delete(f"{self.NOUS_API_URL}/concepts/{concept_dict['concept_id']}", headers={"Authorization": f"Bearer {os.getenv('NOUS_API_TOKEN', 'synergesis_nous_token_2025')}"})

    def _add_concept_via_api(self, concept_id, natural_prompt, concept_type, source, resonance=None, weight=None):
        payload = {
            "concept_id": concept_id,
            "natural_prompt": natural_prompt,
            "concept_type": concept_type,
            "source": source,
            "resonance": resonance,
            "weight": weight
        }
        response = requests.post(f"{self.NOUS_API_URL}/concepts", json=payload, headers={"Authorization": f"Bearer {os.getenv('NOUS_API_TOKEN', 'synergesis_nous_token_2025')}"})
        response.raise_for_status()
        return response.json()

    def test_simple_contradictions(self):
        # Ajouter des concepts qui devraient créer des contradictions via l'API
        self._add_concept_via_api("concept_X", "Description A", "TYPE1", "Test", resonance=0.5, weight=0.5)
        self._add_concept_via_api("concept_X", "Description B", "TYPE1", "Test", resonance=0.6, weight=0.6) # Contradiction
        self._add_concept_via_api("concept_Y", "Description C", "TYPE2", "Test", resonance=0.7, weight=0.7)
        self._add_concept_via_api("concept_Y", "Description C", "TYPE3", "Test", resonance=0.7, weight=0.7) # Contradiction

        inconsistencies = self.thales.check_simple_contradictions()
        
        self.assertEqual(len(inconsistencies), 2)
        self.assertEqual(inconsistencies[0]["concept_id"], "concept_X")
        self.assertEqual(inconsistencies[1]["concept_id"], "concept_Y")
        self.assertEqual(inconsistencies[0]["type"], "simple_contradiction")
        self.assertEqual(inconsistencies[1]["type"], "simple_contradiction")

    def test_no_contradictions(self):
        # Ajouter des concepts sans contradictions via l'API
        self._add_concept_via_api("concept_A", "Description A", "TYPE1", "Test", resonance=0.1, weight=0.2)
        self._add_concept_via_api("concept_B", "Description B", "TYPE2", "Test", resonance=0.3, weight=0.4)

        inconsistencies = self.thales.check_simple_contradictions()
        self.assertEqual(len(inconsistencies), 0)

    def test_deductive_cycles_placeholder(self):
        # Test pour la fonction de détection de cycles (actuellement vide)
        inconsistencies = self.thales.check_deductive_cycles()
        self.assertEqual(len(inconsistencies), 0)

    def test_run_all_checks(self):
        # Test combiné via l'API
        self._add_concept_via_api("concept_Z", "Description Z", "TYPE1", "Test", resonance=0.9, weight=0.8)
        self._add_concept_via_api("concept_Z", "Description Z2", "TYPE1", "Test", resonance=0.9, weight=0.8) # Contradiction

        inconsistencies = self.thales.run_all_checks()
        self.assertEqual(len(inconsistencies), 1)
        self.assertEqual(inconsistencies[0]["concept_id"], "concept_Z")

if __name__ == "__main__":
    unittest.main()


