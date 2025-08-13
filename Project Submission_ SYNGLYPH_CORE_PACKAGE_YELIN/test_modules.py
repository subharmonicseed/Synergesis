import unittest
import sys
import os
import time

# Ajouter le répertoire parent au chemin de recherche
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importer les modules à tester
from core.blackboard import Blackboard
from core.nous import NOUS, SymbolicMemory, KnowledgeGraph
from core.syn_echo import SYN_ECHO, PatternDetector
from core.deep_research import DeepResearch, WeakSignalDetector
from core.selene import SELENE, DreamField
from core.quantum_validator import QuantumValidator, EthicsValidator

# Configuration de test
test_config = {
    "system_name": "SYNERGESIS",
    "version": "∮⋔◎⟐.Δ",
    "ethics_threshold": 0.7,
    "energy_threshold": 8.0,
    "alignment_threshold": 0.6,
    "weak_signal_threshold": 0.3,
    "pattern_detection_threshold": 0.7,
    "ethical_principles": {
        "harm_prevention": 0.9,
        "fairness": 0.8,
        "autonomy": 0.7,
        "privacy": 0.8,
        "transparency": 0.7
    },
    "information_sources": [
        "academic_papers",
        "news_articles"
    ],
    "memory_retention_period": 3600  # 1 heure pour les tests
}

class TestBlackboard(unittest.TestCase):
    def setUp(self):
        self.blackboard = Blackboard()
    
    def test_write_and_read(self):
        # Écrire une valeur
        self.blackboard.write("test_key", "test_value", "test_author")
        
        # Lire la valeur
        value = self.blackboard.read("test_key")
        
        # Vérifier que la valeur est correcte
        self.assertEqual(value, "test_value")
    
    def test_history(self):
        # Écrire plusieurs valeurs
        self.blackboard.write("key1", "value1", "author1")
        self.blackboard.write("key2", "value2", "author2")
        self.blackboard.write("key1", "updated_value", "author1")
        
        # Récupérer l'historique
        history = self.blackboard.get_history()
        
        # Vérifier que l'historique contient 3 entrées
        self.assertEqual(len(history), 3)
        
        # Vérifier que la dernière entrée est correcte
        last_entry = history[-1]
        self.assertEqual(last_entry["key"], "key1")
        self.assertEqual(last_entry["new_value"], "updated_value")
        self.assertEqual(last_entry["old_value"], "value1")
        self.assertEqual(last_entry["author"], "author1")
    
    def test_delete(self):
        # Écrire une valeur
        self.blackboard.write("key_to_delete", "value", "author")
        
        # Vérifier que la valeur existe
        self.assertEqual(self.blackboard.read("key_to_delete"), "value")
        
        # Supprimer la valeur
        result = self.blackboard.delete("key_to_delete", "author")
        
        # Vérifier que la suppression a réussi
        self.assertTrue(result)
        
        # Vérifier que la valeur n'existe plus
        self.assertIsNone(self.blackboard.read("key_to_delete"))

class TestNOUS(unittest.TestCase):
    def setUp(self):
        self.nous = NOUS(test_config)
    
    def test_process_symbol(self):
        # Créer un symbole de test
        symbol = {
            "type": "concept",
            "name": "harmony",
            "attributes": {
                "polarity": "+",
                "frequency": 78
            }
        }
        
        # Traiter le symbole
        processed = self.nous.process_symbol(symbol)
        
        # Vérifier que le symbole a été traité correctement
        self.assertIsNotNone(processed)
        self.assertEqual(processed["name"], "harmony")
        self.assertIn("id", processed)
        self.assertIn("context", processed)
    
    def test_create_relation(self):
        # Créer deux symboles
        symbol1 = self.nous.process_symbol({
            "type": "concept",
            "name": "harmony",
            "attributes": {"polarity": "+"}
        })
        
        symbol2 = self.nous.process_symbol({
            "type": "concept",
            "name": "balance",
            "attributes": {"polarity": "+"}
        })
        
        # Créer une relation entre les symboles
        relation = self.nous.create_relation(symbol1["id"], symbol2["id"], "similar", 0.8)
        
        # Vérifier que la relation a été créée correctement
        self.assertIsNotNone(relation)
        self.assertEqual(relation["source"], symbol1["id"])
        self.assertEqual(relation["target"], symbol2["id"])
        self.assertEqual(relation["type"], "similar")
        self.assertEqual(relation["weight"], 0.8)
    
    def test_retrieve_related_symbols(self):
        # Créer deux symboles liés
        symbol1 = self.nous.process_symbol({
            "type": "concept",
            "name": "harmony",
            "attributes": {"polarity": "+"}
        })
        
        symbol2 = self.nous.process_symbol({
            "type": "concept",
            "name": "balance",
            "attributes": {"polarity": "+"}
        })
        
        # Créer une relation entre les symboles
        self.nous.create_relation(symbol1["id"], symbol2["id"], "similar", 0.8)
        
        # Récupérer les symboles liés
        related = self.nous.retrieve_related_symbols(symbol1["id"], 1)
        
        # Vérifier que le symbole lié est récupéré
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["name"], "balance")

class TestSYN_ECHO(unittest.TestCase):
    def setUp(self):
        self.syn_echo = SYN_ECHO(test_config)
    
    def test_analyze_interactions(self):
        # Créer des interactions de test
        interactions = [
            {
                "agent": "agent1",
                "action": "query",
                "content": "What is the relationship between harmony and chaos?",
                "timestamp": time.time() - 300
            },
            {
                "agent": "agent2",
                "action": "response",
                "content": "Harmony and chaos are complementary forces.",
                "timestamp": time.time() - 240
            },
            {
                "agent": "agent1",
                "action": "query",
                "content": "How can we apply this to complex systems?",
                "timestamp": time.time() - 180
            }
        ]
        
        # Analyser les interactions
        analysis = self.syn_echo.analyze_interactions(interactions)
        
        # Vérifier que l'analyse est correcte
        self.assertIsNotNone(analysis)
        self.assertIn("patterns", analysis)
        self.assertIn("drifts", analysis)
        self.assertIn("emergences", analysis)
        self.assertEqual(analysis["interaction_count"], 3)

class TestDeepResearch(unittest.TestCase):
    def setUp(self):
        self.deep_research = DeepResearch(test_config)
    
    def test_explore_topic(self):
        # Explorer un sujet
        exploration = self.deep_research.explore_topic("quantum computing", 2)
        
        # Vérifier que l'exploration est correcte
        self.assertIsNotNone(exploration)
        self.assertEqual(exploration["topic"], "quantum computing")
        self.assertEqual(exploration["depth"], 2)
        self.assertIn("information", exploration)
        self.assertIn("signals", exploration)
        self.assertIn("hypotheses", exploration)

class TestSELENE(unittest.TestCase):
    def setUp(self):
        self.selene = SELENE(test_config)
    
    def test_incubate_idea(self):
        # Incuber une idée
        idea = self.selene.incubate_idea(["quantum", "creativity", "emergence"], 3)
        
        # Vérifier que l'idée est correcte
        self.assertIsNotNone(idea)
        self.assertIn("id", idea)
        self.assertEqual(idea["seed_concepts"], ["quantum", "creativity", "emergence"])
        self.assertEqual(idea["duration"], 3)
        self.assertIn("description", idea)
        self.assertIn("components", idea)
        self.assertIn("potential", idea)
    
    def test_generate_creative_prompt(self):
        # Générer un prompt créatif
        context = {
            "themes": ["innovation", "sustainability"],
            "constraints": ["practical application", "low resource usage"],
            "tone": "analytical"
        }
        
        prompt = self.selene.generate_creative_prompt(context)
        
        # Vérifier que le prompt est correct
        self.assertIsNotNone(prompt)
        self.assertIn("id", prompt)
        self.assertEqual(prompt["themes"], ["innovation", "sustainability"])
        self.assertEqual(prompt["constraints"], ["practical application", "low resource usage"])
        self.assertEqual(prompt["tone"], "analytical")
        self.assertIn("content", prompt)
        self.assertIn("variations", prompt)

class TestQuantumValidator(unittest.TestCase):
    def setUp(self):
        self.quantum_validator = QuantumValidator(test_config)
    
    def test_validate_task(self):
        # Créer une tâche à valider
        task = {
            "id": "task1",
            "content": "Analyze the patterns of emergence in complex adaptive systems",
            "action_type": "analyze",
            "target": "complex systems",
            "impact_level": "local",
            "estimated_duration": 2.0
        }
        
        # Contexte de validation
        context = {
            "goal": "Understand emergence in complex systems",
            "constraints": ["ethical analysis", "transparent methodology"]
        }
        
        # Valider la tâche
        validation = self.quantum_validator.validate_task(task, context)
        
        # Vérifier que la validation est correcte
        self.assertIsNotNone(validation)
        self.assertIn("is_valid", validation)
        self.assertIn("ethics_score", validation)
        self.assertIn("energy_impact", validation)
        self.assertIn("alignment_score", validation)
        
        # Vérifier que les scores sont dans les plages attendues
        self.assertGreaterEqual(validation["ethics_score"], 0.0)
        self.assertLessEqual(validation["ethics_score"], 1.0)
        self.assertGreaterEqual(validation["energy_impact"], 0.0)
        self.assertLessEqual(validation["energy_impact"], 10.0)
        self.assertGreaterEqual(validation["alignment_score"], 0.0)
        self.assertLessEqual(validation["alignment_score"], 1.0)

if __name__ == '__main__':
    unittest.main()
