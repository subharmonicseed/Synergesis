"""
Test d'intégration quantique pour Synergesis

Ce script teste l'intégration complète des modules quantiques
avec les agents Synergesis existants.
"""

import sys
import time
import json
from typing import List, Dict, Any

# Ajout du répertoire src au path
sys.path.append('/home/ubuntu/synergesis_pipeline/src')

# Imports des modules quantiques
from quantum_core import create_quantum_core, QuantumBackend

# Imports conditionnels pour éviter les conflits de table
try:
    from selene_quantum import SeleneQuantum
    SELENE_QUANTUM_AVAILABLE = True
except Exception as e:
    print(f"⚠ Selene Quantum non disponible: {e}")
    SELENE_QUANTUM_AVAILABLE = False

try:
    from vyra_quantum import VyraQuantum
    VYRA_QUANTUM_AVAILABLE = True
except Exception as e:
    print(f"⚠ Vyra Quantum non disponible: {e}")
    VYRA_QUANTUM_AVAILABLE = False

try:
    from thales_quantum import ThalesQuantum
    THALES_QUANTUM_AVAILABLE = True
except Exception as e:
    print(f"⚠ Thales Quantum non disponible: {e}")
    THALES_QUANTUM_AVAILABLE = False

# Imports des modules de base (simulés pour le test)
try:
    from nous_enhanced import NousEnhanced, Concept
    NOUS_ENHANCED_AVAILABLE = True
except Exception as e:
    print(f"⚠ Nous Enhanced non disponible: {e}")
    NOUS_ENHANCED_AVAILABLE = False
    # Création de classes mock
    class Concept:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    class NousEnhanced:
        def __init__(self):
            self.concepts = []
        
        def add_concept(self, concept):
            self.concepts.append(concept)
        
        def get_all_concepts(self):
            return self.concepts
        
        def get_concept(self, concept_id):
            for concept in self.concepts:
                if hasattr(concept, 'concept_id') and concept.concept_id == concept_id:
                    return concept
            return None


class QuantumIntegrationTester:
    """Testeur d'intégration quantique pour Synergesis."""
    
    def __init__(self):
        self.test_results = {}
        self.nous_instance = None
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Configure l'environnement de test."""
        print("=== Configuration de l'environnement de test quantique ===")
        
        # Création d'une instance Nous simulée
        try:
            self.nous_instance = NousEnhanced()
            print("✓ Instance Nous Enhanced créée")
        except Exception as e:
            print(f"⚠ Erreur création Nous Enhanced: {e}")
            self.nous_instance = None
        
        # Ajout de concepts de test
        self.add_test_concepts()
    
    def add_test_concepts(self):
        """Ajoute des concepts de test."""
        if not self.nous_instance:
            print("⚠ Pas d'instance Nous - concepts simulés")
            return
        
        test_concepts = [
            {
                "concept_id": "quantum_test_1",
                "natural_prompt": "Concept de test pour l'analyse quantique avec prompt court",
                "concept_type": "TEST_TYPE_A",
                "resonance": 0.8,
                "weight": 0.7
            },
            {
                "concept_id": "quantum_test_2", 
                "natural_prompt": "Deuxième concept de test pour vérifier la cohérence quantique et les patterns complexes",
                "concept_type": "TEST_TYPE_A",
                "resonance": 0.6,
                "weight": 0.8
            },
            {
                "concept_id": "quantum_test_3",
                "natural_prompt": "Troisième concept avec type différent",
                "concept_type": "TEST_TYPE_B",
                "resonance": 0.9,
                "weight": 0.5
            }
        ]
        
        for concept_data in test_concepts:
            try:
                concept = Concept(
                    concept_id=concept_data["concept_id"],
                    natural_prompt=concept_data["natural_prompt"],
                    concept_type=concept_data["concept_type"],
                    resonance=concept_data["resonance"],
                    weight=concept_data["weight"]
                )
                self.nous_instance.add_concept(concept)
                print(f"✓ Concept ajouté: {concept_data['concept_id']}")
            except Exception as e:
                print(f"⚠ Erreur ajout concept {concept_data['concept_id']}: {e}")
    
    def test_quantum_core(self) -> Dict[str, Any]:
        """Test du module quantique de base."""
        print("\n=== Test du Module Quantique de Base ===")
        
        results = {
            "test_name": "quantum_core",
            "success": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Création du core quantique
            quantum_core = create_quantum_core("classical")
            
            # Test de détection de patterns
            pattern_data = {
                "concept_id": "test_pattern",
                "natural_prompt": "Test de détection de patterns quantiques",
                "features": [0.5, 0.7, 0.3, 0.9]
            }
            
            pattern_result = quantum_core.detect_patterns(pattern_data)
            results["details"]["pattern_detection"] = {
                "pattern_detected": pattern_result.classical_interpretation.get("pattern_detected", False),
                "confidence": pattern_result.confidence_score,
                "execution_time": pattern_result.execution_time
            }
            
            # Test d'optimisation
            optimization_data = {
                "optimization_type": "suggestion_ranking",
                "suggestions": [
                    {"priority": 0.8, "description": "Suggestion A"},
                    {"priority": 0.6, "description": "Suggestion B"},
                    {"priority": 0.9, "description": "Suggestion C"}
                ]
            }
            
            optimization_result = quantum_core.optimize(optimization_data)
            results["details"]["optimization"] = {
                "optimization_successful": optimization_result.classical_interpretation.get("optimization_successful", False),
                "optimal_solution": optimization_result.classical_interpretation.get("optimal_solution", []),
                "execution_time": optimization_result.execution_time
            }
            
            # Test d'analyse de cohérence
            coherence_data = {
                "analysis_type": "pairwise",
                "concepts": [
                    {"natural_prompt": "Premier concept", "resonance": 0.8},
                    {"natural_prompt": "Second concept", "resonance": 0.7}
                ]
            }
            
            coherence_result = quantum_core.analyze_coherence(coherence_data)
            results["details"]["coherence_analysis"] = {
                "coherence_detected": coherence_result.classical_interpretation.get("coherence_detected", False),
                "confidence": coherence_result.confidence_score,
                "execution_time": coherence_result.execution_time
            }
            
            # Statut du système
            system_status = quantum_core.get_system_status()
            results["details"]["system_status"] = system_status
            
            results["success"] = True
            print("✓ Test du module quantique de base réussi")
            
        except Exception as e:
            results["errors"].append(str(e))
            print(f"✗ Erreur test module quantique: {e}")
        
        return results
    
    def test_selene_quantum(self) -> Dict[str, Any]:
        """Test de Selene Quantum."""
        print("\n=== Test de Selene Quantum ===")
        
        results = {
            "test_name": "selene_quantum",
            "success": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Création de Selene Quantum
            selene_quantum = SeleneQuantum(self.nous_instance, "classical")
            
            # Test de détection de lacunes avec amélioration quantique
            gaps = selene_quantum.detect_gaps_quantum_enhanced()
            
            results["details"]["gap_detection"] = {
                "total_gaps": len(gaps),
                "quantum_enhanced_gaps": len([gap for gap in gaps if gap.metadata.get("quantum_enhanced", False)]),
                "quantum_only_gaps": len([gap for gap in gaps if gap.metadata.get("quantum_only", False)])
            }
            
            # Statistiques quantiques
            quantum_stats = selene_quantum.get_quantum_statistics()
            results["details"]["quantum_statistics"] = quantum_stats
            
            # Test de configuration
            selene_quantum.set_quantum_thresholds(0.5, 1.3)
            selene_quantum.enable_quantum_mode(True)
            
            results["details"]["configuration_test"] = "success"
            
            results["success"] = True
            print(f"✓ Test Selene Quantum réussi - {len(gaps)} lacunes détectées")
            
        except Exception as e:
            results["errors"].append(str(e))
            print(f"✗ Erreur test Selene Quantum: {e}")
        
        return results
    
    def test_vyra_quantum(self) -> Dict[str, Any]:
        """Test de Vyra Quantum."""
        print("\n=== Test de Vyra Quantum ===")
        
        results = {
            "test_name": "vyra_quantum",
            "success": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Création de Vyra Quantum
            vyra_quantum = VyraQuantum(self.nous_instance, "classical")
            
            # Test de génération créative quantique
            concept_data = {
                "concept_id": "test_creative",
                "natural_prompt": "Concept pour test créatif quantique",
                "concept_type": "CREATIVE_TEST"
            }
            
            creative_suggestions = vyra_quantum.generate_quantum_creative_suggestions(concept_data, 3)
            
            results["details"]["creative_generation"] = {
                "total_suggestions": len(creative_suggestions),
                "quantum_generated": len([s for s in creative_suggestions if s.metadata.get("quantum_generated", False)]),
                "average_priority": sum(s.priority for s in creative_suggestions) / len(creative_suggestions) if creative_suggestions else 0
            }
            
            # Test d'optimisation de suggestions (simulé)
            if creative_suggestions:
                # Simulation de lacunes pour l'optimisation
                mock_gaps = []
                optimized_suggestions = vyra_quantum.generate_suggestions_quantum_optimized(mock_gaps)
                
                results["details"]["optimization_test"] = {
                    "optimization_attempted": True,
                    "suggestions_optimized": len(optimized_suggestions)
                }
            
            # Statistiques d'optimisation
            optimization_stats = vyra_quantum.get_quantum_optimization_statistics()
            results["details"]["optimization_statistics"] = optimization_stats
            
            # Test de configuration
            vyra_quantum.configure_quantum_weights(0.4, 0.3, 0.3)
            vyra_quantum.enable_quantum_optimization(True)
            
            results["details"]["configuration_test"] = "success"
            
            results["success"] = True
            print(f"✓ Test Vyra Quantum réussi - {len(creative_suggestions)} suggestions créatives")
            
        except Exception as e:
            results["errors"].append(str(e))
            print(f"✗ Erreur test Vyra Quantum: {e}")
        
        return results
    
    def test_thales_quantum(self) -> Dict[str, Any]:
        """Test de Thales Quantum."""
        print("\n=== Test de Thales Quantum ===")
        
        results = {
            "test_name": "thales_quantum",
            "success": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Création de Thales Quantum
            thales_quantum = ThalesQuantum(self.nous_instance, "classical")
            
            # Test de détection d'incohérences quantiques
            inconsistencies = thales_quantum.detect_inconsistencies_quantum_enhanced()
            
            results["details"]["inconsistency_detection"] = {
                "total_inconsistencies": len(inconsistencies),
                "quantum_enhanced": len([inc for inc in inconsistencies if inc.metadata.get("quantum_enhanced", False)]),
                "quantum_only": len([inc for inc in inconsistencies if inc.metadata.get("quantum_only", False)])
            }
            
            # Statistiques quantiques
            quantum_stats = thales_quantum.get_quantum_inconsistency_statistics()
            results["details"]["quantum_statistics"] = quantum_stats
            
            # Test de configuration
            thales_quantum.configure_quantum_thresholds(0.4, 0.6, 1.5)
            thales_quantum.enable_quantum_analysis(True)
            
            results["details"]["configuration_test"] = "success"
            
            results["success"] = True
            print(f"✓ Test Thales Quantum réussi - {len(inconsistencies)} incohérences détectées")
            
        except Exception as e:
            results["errors"].append(str(e))
            print(f"✗ Erreur test Thales Quantum: {e}")
        
        return results
    
    def test_integration_workflow(self) -> Dict[str, Any]:
        """Test du workflow d'intégration complet."""
        print("\n=== Test du Workflow d'Intégration Complet ===")
        
        results = {
            "test_name": "integration_workflow",
            "success": False,
            "details": {},
            "errors": []
        }
        
        try:
            # Création des agents quantiques
            selene_quantum = SeleneQuantum(self.nous_instance, "classical")
            vyra_quantum = VyraQuantum(self.nous_instance, "classical")
            thales_quantum = ThalesQuantum(self.nous_instance, "classical")
            
            # Workflow complet
            workflow_start = time.time()
            
            # 1. Détection de lacunes avec Selene Quantum
            gaps = selene_quantum.detect_gaps_quantum_enhanced()
            
            # 2. Génération de suggestions avec Vyra Quantum
            suggestions = vyra_quantum.generate_suggestions_quantum_optimized(gaps)
            
            # 3. Détection d'incohérences avec Thales Quantum
            inconsistencies = thales_quantum.detect_inconsistencies_quantum_enhanced()
            
            workflow_time = time.time() - workflow_start
            
            results["details"]["workflow_execution"] = {
                "total_execution_time": workflow_time,
                "gaps_detected": len(gaps),
                "suggestions_generated": len(suggestions),
                "inconsistencies_found": len(inconsistencies)
            }
            
            # Analyse des améliorations quantiques
            quantum_enhanced_gaps = [gap for gap in gaps if gap.metadata.get("quantum_enhanced", False)]
            quantum_enhanced_inconsistencies = [inc for inc in inconsistencies if inc.metadata.get("quantum_enhanced", False)]
            
            results["details"]["quantum_enhancements"] = {
                "enhanced_gaps_ratio": len(quantum_enhanced_gaps) / len(gaps) if gaps else 0,
                "enhanced_inconsistencies_ratio": len(quantum_enhanced_inconsistencies) / len(inconsistencies) if inconsistencies else 0,
                "average_gap_enhancement": sum(gap.metadata.get("enhancement_factor", 1.0) for gap in quantum_enhanced_gaps) / len(quantum_enhanced_gaps) if quantum_enhanced_gaps else 1.0,
                "average_inconsistency_enhancement": sum(inc.metadata.get("severity_enhancement", 1.0) for inc in quantum_enhanced_inconsistencies) / len(quantum_enhanced_inconsistencies) if quantum_enhanced_inconsistencies else 1.0
            }
            
            # Test de cohérence inter-agents
            coherence_test = self.test_inter_agent_coherence(selene_quantum, vyra_quantum, thales_quantum)
            results["details"]["inter_agent_coherence"] = coherence_test
            
            results["success"] = True
            print(f"✓ Workflow d'intégration réussi en {workflow_time:.3f}s")
            
        except Exception as e:
            results["errors"].append(str(e))
            print(f"✗ Erreur workflow d'intégration: {e}")
        
        return results
    
    def test_inter_agent_coherence(self, selene_quantum, vyra_quantum, thales_quantum) -> Dict[str, Any]:
        """Test de cohérence entre les agents quantiques."""
        coherence_results = {
            "selene_vyra_coherence": 0.0,
            "vyra_thales_coherence": 0.0,
            "selene_thales_coherence": 0.0,
            "overall_coherence": 0.0
        }
        
        try:
            # Récupération des statistiques de chaque agent
            selene_stats = selene_quantum.get_quantum_statistics()
            vyra_stats = vyra_quantum.get_quantum_optimization_statistics()
            thales_stats = thales_quantum.get_quantum_inconsistency_statistics()
            
            # Calcul de cohérence basé sur les métriques communes
            if selene_stats.get("total_quantum_analyses", 0) > 0 and vyra_stats.get("total_optimizations", 0) > 0:
                selene_confidence = selene_stats.get("average_quantum_confidence", 0.5)
                vyra_confidence = vyra_stats.get("average_confidence", 0.5)
                coherence_results["selene_vyra_coherence"] = 1.0 - abs(selene_confidence - vyra_confidence)
            
            if vyra_stats.get("total_optimizations", 0) > 0 and thales_stats.get("total_quantum_analyses", 0) > 0:
                vyra_confidence = vyra_stats.get("average_confidence", 0.5)
                thales_confidence = thales_stats.get("average_coherence_score", 0.5)
                coherence_results["vyra_thales_coherence"] = 1.0 - abs(vyra_confidence - thales_confidence)
            
            if selene_stats.get("total_quantum_analyses", 0) > 0 and thales_stats.get("total_quantum_analyses", 0) > 0:
                selene_confidence = selene_stats.get("average_quantum_confidence", 0.5)
                thales_confidence = thales_stats.get("average_coherence_score", 0.5)
                coherence_results["selene_thales_coherence"] = 1.0 - abs(selene_confidence - thales_confidence)
            
            # Cohérence globale
            coherences = [v for v in coherence_results.values() if v > 0]
            if coherences:
                coherence_results["overall_coherence"] = sum(coherences) / len(coherences)
            
        except Exception as e:
            print(f"⚠ Erreur test cohérence inter-agents: {e}")
        
        return coherence_results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Exécute tous les tests d'intégration quantique."""
        print("🚀 Démarrage des tests d'intégration quantique Synergesis")
        
        all_results = {
            "test_suite": "quantum_integration",
            "timestamp": time.time(),
            "tests": {},
            "summary": {}
        }
        
        # Exécution des tests
        test_methods = [
            self.test_quantum_core,
            self.test_selene_quantum,
            self.test_vyra_quantum,
            self.test_thales_quantum,
            self.test_integration_workflow
        ]
        
        successful_tests = 0
        total_tests = len(test_methods)
        
        for test_method in test_methods:
            try:
                result = test_method()
                all_results["tests"][result["test_name"]] = result
                
                if result["success"]:
                    successful_tests += 1
                    
            except Exception as e:
                print(f"✗ Erreur critique dans {test_method.__name__}: {e}")
                all_results["tests"][test_method.__name__] = {
                    "test_name": test_method.__name__,
                    "success": False,
                    "errors": [str(e)]
                }
        
        # Résumé
        all_results["summary"] = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests / total_tests,
            "overall_success": successful_tests == total_tests
        }
        
        return all_results
    
    def generate_test_report(self, results: Dict[str, Any]) -> str:
        """Génère un rapport de test détaillé."""
        report = []
        report.append("# Rapport de Test d'Intégration Quantique Synergesis")
        report.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(results['timestamp']))}")
        report.append("")
        
        # Résumé
        summary = results["summary"]
        report.append("## Résumé Exécutif")
        report.append(f"- **Tests exécutés:** {summary['total_tests']}")
        report.append(f"- **Tests réussis:** {summary['successful_tests']}")
        report.append(f"- **Taux de réussite:** {summary['success_rate']:.1%}")
        report.append(f"- **Statut global:** {'✅ SUCCÈS' if summary['overall_success'] else '❌ ÉCHEC'}")
        report.append("")
        
        # Détails des tests
        report.append("## Détails des Tests")
        
        for test_name, test_result in results["tests"].items():
            report.append(f"### {test_name.replace('_', ' ').title()}")
            report.append(f"**Statut:** {'✅ Réussi' if test_result['success'] else '❌ Échoué'}")
            
            if test_result.get("errors"):
                report.append("**Erreurs:**")
                for error in test_result["errors"]:
                    report.append(f"- {error}")
            
            if test_result.get("details"):
                report.append("**Détails:**")
                for key, value in test_result["details"].items():
                    if isinstance(value, dict):
                        report.append(f"- **{key}:**")
                        for subkey, subvalue in value.items():
                            report.append(f"  - {subkey}: {subvalue}")
                    else:
                        report.append(f"- {key}: {value}")
            
            report.append("")
        
        return "\n".join(report)


def main():
    """Fonction principale de test."""
    tester = QuantumIntegrationTester()
    
    # Exécution des tests
    results = tester.run_all_tests()
    
    # Génération du rapport
    report = tester.generate_test_report(results)
    
    # Affichage du résumé
    print("\n" + "="*60)
    print("RÉSUMÉ DES TESTS D'INTÉGRATION QUANTIQUE")
    print("="*60)
    
    summary = results["summary"]
    print(f"Tests exécutés: {summary['total_tests']}")
    print(f"Tests réussis: {summary['successful_tests']}")
    print(f"Taux de réussite: {summary['success_rate']:.1%}")
    print(f"Statut global: {'✅ SUCCÈS' if summary['overall_success'] else '❌ ÉCHEC'}")
    
    # Sauvegarde des résultats
    try:
        with open('/home/ubuntu/synergesis_pipeline/quantum_test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print("\n📄 Résultats sauvegardés: quantum_test_results.json")
        
        with open('/home/ubuntu/synergesis_pipeline/quantum_test_report.md', 'w') as f:
            f.write(report)
        print("📄 Rapport sauvegardé: quantum_test_report.md")
        
    except Exception as e:
        print(f"⚠ Erreur sauvegarde: {e}")
    
    return results


if __name__ == "__main__":
    main()

