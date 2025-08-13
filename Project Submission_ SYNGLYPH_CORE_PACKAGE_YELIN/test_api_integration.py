import unittest
import sys
import os
import time
import json
import requests
from multiprocessing import Process
import uvicorn

# Ajouter le répertoire parent au chemin de recherche
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importer les modules nécessaires
from api.main import app

def run_server():
    """Fonction pour exécuter le serveur API dans un processus séparé"""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Démarrer le serveur API avant les tests"""
        # Initialiser les modules pour l'API
        from main import initialize_system
        system = initialize_system()
        app.state.blackboard = system["blackboard"]
        app.state.modules = system["modules"]
        app.state.initialized = True
        
        # Démarrer le serveur dans un processus séparé
        cls.server_process = Process(target=run_server)
        cls.server_process.start()
        
        # Attendre que le serveur démarre
        time.sleep(2)
        
        # URL de base pour les requêtes API
        cls.base_url = "http://127.0.0.1:8000"
    
    @classmethod
    def tearDownClass(cls):
        """Arrêter le serveur API après les tests"""
        cls.server_process.terminate()
        cls.server_process.join()
    
    def test_status_endpoint(self):
        """Tester l'endpoint de statut"""
        response = requests.get(f"{self.base_url}/status")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["status"], "operational")
        self.assertIn("modules", data)
        self.assertIn("version", data)
        
        # Vérifier que tous les modules sont actifs
        for module_status in data["modules"].values():
            self.assertEqual(module_status, "active")
    
    def test_analyze_symbol_endpoint(self):
        """Tester l'endpoint d'analyse de symbole"""
        payload = {
            "text": "Harmony is the balance of opposing forces."
        }
        
        response = requests.post(
            f"{self.base_url}/symbols/analyze",
            json=payload
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("id", data)
        self.assertIn("type", data)
        self.assertIn("content", data)
        self.assertIn("polarity", data)
        self.assertIn("frequency", data)
        self.assertIn("weight", data)
    
    def test_explore_topic_endpoint(self):
        """Tester l'endpoint d'exploration de sujet"""
        payload = {
            "topic": "quantum computing",
            "depth": 2
        }
        
        response = requests.post(
            f"{self.base_url}/exploration/topic",
            json=payload
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["topic"], "quantum computing")
        self.assertEqual(data["depth"], 2)
        self.assertIn("signals", data)
        self.assertIn("hypotheses", data)
    
    def test_incubate_idea_endpoint(self):
        """Tester l'endpoint d'incubation d'idée"""
        payload = {
            "seed_concepts": ["quantum", "creativity", "emergence"],
            "duration": 3
        }
        
        response = requests.post(
            f"{self.base_url}/ideas/incubate",
            json=payload
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["seed_concepts"], ["quantum", "creativity", "emergence"])
        self.assertEqual(data["duration"], 3)
        self.assertIn("description", data)
        self.assertIn("components", data)
    
    def test_validate_task_endpoint(self):
        """Tester l'endpoint de validation de tâche"""
        payload = {
            "content": "Analyze the patterns of emergence in complex adaptive systems",
            "action_type": "analyze",
            "target": "complex systems",
            "impact_level": "local",
            "estimated_duration": 2.0
        }
        
        response = requests.post(
            f"{self.base_url}/validation/task",
            json=payload
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("is_valid", data)
        self.assertIn("ethics_score", data)
        self.assertIn("energy_impact", data)
        self.assertIn("alignment_score", data)
    
    def test_generate_glyph_endpoint(self):
        """Tester l'endpoint de génération de glyphe"""
        response = requests.get(f"{self.base_url}/glyphs/generate")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("id", data)
        self.assertIn("svg", data)
        self.assertIn("timestamp", data)

if __name__ == '__main__':
    unittest.main()
