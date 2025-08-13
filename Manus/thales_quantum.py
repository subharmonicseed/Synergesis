"""
Module Thales Quantum - Intégration quantique pour la détection d'incohérences

Ce module étend Thales avec des capacités quantiques pour améliorer
la détection d'incohérences complexes et l'analyse de cohérence globale.
"""

import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from quantum_core import QuantumCore, create_quantum_core
from thales import Thales, Inconsistency


@dataclass
class QuantumInconsistencyAnalysis:
    """Résultat d'analyse quantique d'incohérence."""
    analysis_id: str
    inconsistency_type: str
    quantum_coherence_score: float
    classical_confidence: float
    quantum_confidence: float
    entanglement_measure: float
    quantum_insights: List[str]
    affected_concepts: List[str]
    severity_enhancement: float
    metadata: Dict[str, Any]


class ThalesQuantum(Thales):
    """Version quantique de Thales avec analyse de cohérence avancée."""
    
    def __init__(self, nous_instance=None, quantum_backend: str = "classical"):
        super().__init__(nous_instance)
        
        # Initialisation du module quantique
        self.quantum_core = create_quantum_core(quantum_backend)
        self.quantum_enabled = True
        self.quantum_analysis_history: List[QuantumInconsistencyAnalysis] = []
        
        # Configuration quantique
        self.coherence_threshold = 0.4  # Seuil de cohérence quantique
        self.entanglement_threshold = 0.6  # Seuil d'intrication significative
        self.quantum_enhancement_factor = 1.5  # Facteur d'amélioration quantique
    
    def detect_inconsistencies_quantum_enhanced(self) -> List[Inconsistency]:
        """Détection d'incohérences avec amélioration quantique."""
        # Détection classique de base
        classical_inconsistencies = super().detect_inconsistencies()
        
        if not self.quantum_enabled:
            return classical_inconsistencies
        
        # Amélioration quantique des incohérences détectées
        enhanced_inconsistencies = []
        
        for inconsistency in classical_inconsistencies:
            # Analyse quantique de l'incohérence
            quantum_analysis = self._analyze_inconsistency_quantum(inconsistency)
            
            # Amélioration de l'incohérence avec les insights quantiques
            enhanced_inconsistency = self._enhance_inconsistency_with_quantum(
                inconsistency, quantum_analysis
            )
            enhanced_inconsistencies.append(enhanced_inconsistency)
            
            # Enregistrement de l'analyse
            self.quantum_analysis_history.append(quantum_analysis)
        
        # Détection d'incohérences quantiques additionnelles
        additional_inconsistencies = self._detect_quantum_only_inconsistencies()
        enhanced_inconsistencies.extend(additional_inconsistencies)
        
        return enhanced_inconsistencies
    
    def _analyze_inconsistency_quantum(self, inconsistency: Inconsistency) -> QuantumInconsistencyAnalysis:
        """Analyse quantique d'une incohérence spécifique."""
        # Récupération des concepts impliqués
        affected_concepts = self._get_concepts_for_inconsistency(inconsistency)
        
        if len(affected_concepts) < 2:
            # Analyse d'un seul concept
            coherence_data = {
                "analysis_type": "single_concept",
                "concepts": affected_concepts
            }
        else:
            # Analyse pairwise ou globale
            coherence_data = {
                "analysis_type": "pairwise" if len(affected_concepts) == 2 else "global",
                "concepts": [
                    {
                        "concept_id": concept.concept_id,
                        "natural_prompt": concept.natural_prompt,
                        "concept_type": concept.concept_type,
                        "resonance": getattr(concept, 'resonance', 0.5),
                        "weight": getattr(concept, 'weight', 0.5)
                    }
                    for concept in affected_concepts
                ]
            }
        
        # Analyse de cohérence quantique
        coherence_result = self.quantum_core.analyze_coherence(coherence_data)
        
        # Extraction des métriques quantiques
        quantum_output = coherence_result.quantum_output
        classical_interpretation = coherence_result.classical_interpretation
        
        # Calcul de la mesure d'intrication
        entanglement_measure = self._calculate_entanglement_measure(quantum_output)
        
        # Calcul de l'amélioration de sévérité
        classical_confidence = inconsistency.severity
        quantum_confidence = coherence_result.confidence_score
        severity_enhancement = self._calculate_severity_enhancement(
            classical_confidence, quantum_confidence, entanglement_measure
        )
        
        # Génération d'insights quantiques
        quantum_insights = self._generate_inconsistency_insights(
            inconsistency, coherence_result, entanglement_measure
        )
        
        return QuantumInconsistencyAnalysis(
            analysis_id=str(uuid.uuid4())[:8],
            inconsistency_type=inconsistency.inconsistency_type,
            quantum_coherence_score=quantum_output.get("coherence_score", 0.0),
            classical_confidence=classical_confidence,
            quantum_confidence=quantum_confidence,
            entanglement_measure=entanglement_measure,
            quantum_insights=quantum_insights,
            affected_concepts=[concept.concept_id for concept in affected_concepts],
            severity_enhancement=severity_enhancement,
            metadata={
                "quantum_result_id": coherence_result.result_id,
                "execution_time": coherence_result.execution_time,
                "backend_used": coherence_result.backend_used,
                "analysis_type": coherence_data["analysis_type"]
            }
        )
    
    def _get_concepts_for_inconsistency(self, inconsistency: Inconsistency) -> List:
        """Récupère les concepts impliqués dans une incohérence."""
        concepts = []
        
        # Extraction des IDs de concepts depuis la description ou les métadonnées
        if hasattr(inconsistency, 'concept_ids') and inconsistency.concept_ids:
            for concept_id in inconsistency.concept_ids:
                concept = self.nous.get_concept(concept_id)
                if concept:
                    concepts.append(concept)
        
        elif "concept_id" in inconsistency.metadata:
            concept_id = inconsistency.metadata["concept_id"]
            concept = self.nous.get_concept(concept_id)
            if concept:
                concepts.append(concept)
        
        # Si aucun concept spécifique, utiliser tous les concepts pour l'analyse globale
        if not concepts:
            all_concepts = self.nous.get_all_concepts()
            # Limiter à un échantillon pour l'efficacité
            concepts = all_concepts[:5] if len(all_concepts) > 5 else all_concepts
        
        return concepts
    
    def _calculate_entanglement_measure(self, quantum_output: Dict[str, Any]) -> float:
        """Calcule une mesure d'intrication quantique."""
        if "quantum_entanglement" in quantum_output:
            return quantum_output["quantum_entanglement"]
        
        elif "expectation_values" in quantum_output:
            # Calcul basé sur les valeurs d'expectation
            exp_vals = quantum_output["expectation_values"]
            if len(exp_vals) >= 2:
                # Mesure de corrélation comme proxy d'intrication
                correlation = abs(sum(exp_vals[i] * exp_vals[i+1] for i in range(len(exp_vals)-1)))
                return min(correlation / len(exp_vals), 1.0)
        
        elif "coherence_matrix" in quantum_output:
            # Calcul basé sur la matrice de cohérence
            matrix = quantum_output["coherence_matrix"]
            if matrix and len(matrix) > 1:
                # Moyenne des corrélations hors-diagonale
                off_diagonal = []
                for i in range(len(matrix)):
                    for j in range(len(matrix[i])):
                        if i != j:
                            off_diagonal.append(abs(matrix[i][j]))
                
                if off_diagonal:
                    return sum(off_diagonal) / len(off_diagonal)
        
        # Valeur par défaut
        return 0.5
    
    def _calculate_severity_enhancement(self, classical_confidence: float,
                                      quantum_confidence: float,
                                      entanglement_measure: float) -> float:
        """Calcule le facteur d'amélioration de sévérité."""
        # Combinaison des métriques quantiques
        quantum_factor = (quantum_confidence + entanglement_measure) / 2.0
        
        # Calcul de l'amélioration
        if quantum_factor > classical_confidence:
            enhancement = quantum_factor / max(classical_confidence, 0.1)
            return min(enhancement, self.quantum_enhancement_factor)
        else:
            # Pas d'amélioration significative
            return 1.0
    
    def _generate_inconsistency_insights(self, inconsistency: Inconsistency,
                                       coherence_result,
                                       entanglement_measure: float) -> List[str]:
        """Génère des insights quantiques sur l'incohérence."""
        insights = []
        
        classical_interpretation = coherence_result.classical_interpretation
        quantum_output = coherence_result.quantum_output
        
        # Insights sur la cohérence quantique
        if "coherence_level" in quantum_output:
            coherence_level = quantum_output["coherence_level"]
            insights.append(f"Niveau de cohérence quantique: {coherence_level}")
            
            if coherence_level in ["INCOHÉRENT", "PEU_COHÉRENT"]:
                insights.append(
                    "L'analyse quantique confirme une incohérence significative"
                )
            elif coherence_level in ["TRÈS_COHÉRENT", "COHÉRENT"]:
                insights.append(
                    "L'analyse quantique suggère que l'incohérence pourrait être superficielle"
                )
        
        # Insights sur l'intrication
        if entanglement_measure > self.entanglement_threshold:
            insights.append(
                f"Forte intrication quantique détectée (score: {entanglement_measure:.3f}) - "
                "les concepts sont profondément liés"
            )
            insights.append(
                "Recommandation: Traiter cette incohérence en priorité car elle affecte "
                "l'ensemble du système"
            )
        elif entanglement_measure > 0.3:
            insights.append(
                f"Intrication quantique modérée (score: {entanglement_measure:.3f}) - "
                "corrélations non-locales présentes"
            )
        else:
            insights.append(
                "Faible intrication quantique - incohérence probablement localisée"
            )
        
        # Insights spécifiques au type d'incohérence
        if inconsistency.inconsistency_type == "FIELD_VALUE_MISMATCH":
            insights.append(
                "Quantum insight: Utiliser l'optimisation quantique pour déterminer "
                "la valeur de champ la plus cohérente"
            )
        
        elif inconsistency.inconsistency_type == "SEMANTIC_CONTRADICTION":
            insights.append(
                "Quantum insight: L'analyse de cohérence quantique peut révéler "
                "des contradictions sémantiques subtiles"
            )
        
        elif inconsistency.inconsistency_type == "STRUCTURAL_INCONSISTENCY":
            insights.append(
                "Quantum insight: L'intrication quantique indique des dépendances "
                "structurelles complexes à considérer"
            )
        
        # Insights sur les incoherences trouvées
        incoherences_found = classical_interpretation.get("incoherences_found", [])
        if incoherences_found:
            insights.append(
                f"L'analyse quantique a identifié {len(incoherences_found)} "
                "incohérences additionnelles"
            )
        
        return insights
    
    def _enhance_inconsistency_with_quantum(self, inconsistency: Inconsistency,
                                          quantum_analysis: QuantumInconsistencyAnalysis) -> Inconsistency:
        """Améliore une incohérence avec les insights quantiques."""
        # Mise à jour de la sévérité
        enhanced_severity = min(
            inconsistency.severity * quantum_analysis.severity_enhancement,
            1.0
        )
        
        # Enrichissement de la description
        enhanced_description = inconsistency.description
        if quantum_analysis.entanglement_measure > self.entanglement_threshold:
            enhanced_description += f" [Quantum: Forte intrication détectée - score {quantum_analysis.entanglement_measure:.3f}]"
        
        if quantum_analysis.quantum_coherence_score < self.coherence_threshold:
            enhanced_description += f" [Quantum: Incohérence confirmée - score {quantum_analysis.quantum_coherence_score:.3f}]"
        
        # Enrichissement des métadonnées
        enhanced_metadata = inconsistency.metadata.copy()
        enhanced_metadata.update({
            "quantum_enhanced": True,
            "quantum_coherence_score": quantum_analysis.quantum_coherence_score,
            "quantum_confidence": quantum_analysis.quantum_confidence,
            "entanglement_measure": quantum_analysis.entanglement_measure,
            "severity_enhancement": quantum_analysis.severity_enhancement,
            "quantum_insights": quantum_analysis.quantum_insights,
            "analysis_id": quantum_analysis.analysis_id
        })
        
        # Création de l'incohérence améliorée
        enhanced_inconsistency = Inconsistency(
            inconsistency_type=inconsistency.inconsistency_type,
            description=enhanced_description,
            severity=enhanced_severity,
            metadata=enhanced_metadata
        )
        
        return enhanced_inconsistency
    
    def _detect_quantum_only_inconsistencies(self) -> List[Inconsistency]:
        """Détecte des incohérences que seule l'analyse quantique peut révéler."""
        quantum_inconsistencies = []
        
        # Récupération de tous les concepts pour l'analyse globale
        all_concepts = self.nous.get_all_concepts()
        
        if len(all_concepts) < 3:
            return quantum_inconsistencies
        
        # Analyse de cohérence quantique globale
        coherence_data = {
            "analysis_type": "global",
            "concepts": [
                {
                    "concept_id": concept.concept_id,
                    "natural_prompt": concept.natural_prompt,
                    "concept_type": concept.concept_type,
                    "resonance": getattr(concept, 'resonance', 0.5),
                    "weight": getattr(concept, 'weight', 0.5)
                }
                for concept in all_concepts
            ]
        }
        
        coherence_result = self.quantum_core.analyze_coherence(coherence_data)
        
        # Détection d'incohérences quantiques
        incoherences = coherence_result.classical_interpretation.get("incoherences_found", [])
        
        for incoherence in incoherences:
            if incoherence["type"] == "global_incoherence":
                concept_indices = incoherence["concept_indices"]
                coherence_score = incoherence["coherence_score"]
                
                if len(concept_indices) >= 2:
                    concept1 = all_concepts[concept_indices[0]]
                    concept2 = all_concepts[concept_indices[1]]
                    
                    # Calcul de l'intrication pour cette paire
                    entanglement = self._calculate_pairwise_entanglement(concept1, concept2)
                    
                    quantum_inconsistency = Inconsistency(
                        inconsistency_type="QUANTUM_GLOBAL_INCOHERENCE",
                        description=f"Incohérence quantique globale détectée entre '{concept1.concept_id}' "
                                  f"et '{concept2.concept_id}' (cohérence: {coherence_score:.3f}, "
                                  f"intrication: {entanglement:.3f})",
                        severity=1.0 - coherence_score,
                        metadata={
                            "quantum_only": True,
                            "coherence_score": coherence_score,
                            "entanglement_measure": entanglement,
                            "affected_concepts": [concept1.concept_id, concept2.concept_id],
                            "detection_method": "quantum_global_coherence_analysis",
                            "quantum_insights": [
                                "Cette incohérence n'aurait pas été détectée par les méthodes classiques",
                                f"L'intrication quantique de {entanglement:.3f} indique des corrélations non-locales",
                                "Recommandation: Analyser les dépendances cachées entre ces concepts"
                            ]
                        }
                    )
                    
                    quantum_inconsistencies.append(quantum_inconsistency)
        
        # Détection d'incohérences par analyse d'intrication
        entanglement_inconsistencies = self._detect_entanglement_inconsistencies(all_concepts)
        quantum_inconsistencies.extend(entanglement_inconsistencies)
        
        return quantum_inconsistencies
    
    def _calculate_pairwise_entanglement(self, concept1, concept2) -> float:
        """Calcule l'intrication entre deux concepts."""
        # Analyse de cohérence pairwise
        coherence_data = {
            "analysis_type": "pairwise",
            "concepts": [
                {
                    "concept_id": concept1.concept_id,
                    "natural_prompt": concept1.natural_prompt,
                    "concept_type": concept1.concept_type,
                    "resonance": getattr(concept1, 'resonance', 0.5),
                    "weight": getattr(concept1, 'weight', 0.5)
                },
                {
                    "concept_id": concept2.concept_id,
                    "natural_prompt": concept2.natural_prompt,
                    "concept_type": concept2.concept_type,
                    "resonance": getattr(concept2, 'resonance', 0.5),
                    "weight": getattr(concept2, 'weight', 0.5)
                }
            ]
        }
        
        coherence_result = self.quantum_core.analyze_coherence(coherence_data)
        return self._calculate_entanglement_measure(coherence_result.quantum_output)
    
    def _detect_entanglement_inconsistencies(self, concepts: List) -> List[Inconsistency]:
        """Détecte des incohérences basées sur l'intrication quantique."""
        entanglement_inconsistencies = []
        
        # Analyse pairwise de tous les concepts
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                concept1, concept2 = concepts[i], concepts[j]
                
                entanglement = self._calculate_pairwise_entanglement(concept1, concept2)
                
                # Détection d'intrication anormalement élevée ou faible
                if entanglement > 0.9:
                    # Intrication trop élevée - possible redondance
                    inconsistency = Inconsistency(
                        inconsistency_type="QUANTUM_EXCESSIVE_ENTANGLEMENT",
                        description=f"Intrication quantique excessive entre '{concept1.concept_id}' "
                                  f"et '{concept2.concept_id}' (score: {entanglement:.3f}) - "
                                  f"possible redondance conceptuelle",
                        severity=entanglement,
                        metadata={
                            "quantum_only": True,
                            "entanglement_measure": entanglement,
                            "affected_concepts": [concept1.concept_id, concept2.concept_id],
                            "detection_method": "quantum_entanglement_analysis",
                            "quantum_insights": [
                                "Intrication quantique anormalement élevée détectée",
                                "Possible fusion ou différenciation des concepts nécessaire",
                                "Vérifier la redondance informationnelle"
                            ]
                        }
                    )
                    entanglement_inconsistencies.append(inconsistency)
                
                elif entanglement < 0.1 and self._should_be_entangled(concept1, concept2):
                    # Intrication trop faible pour des concepts qui devraient être liés
                    inconsistency = Inconsistency(
                        inconsistency_type="QUANTUM_INSUFFICIENT_ENTANGLEMENT",
                        description=f"Intrication quantique insuffisante entre '{concept1.concept_id}' "
                                  f"et '{concept2.concept_id}' (score: {entanglement:.3f}) - "
                                  f"concepts potentiellement déconnectés",
                        severity=1.0 - entanglement,
                        metadata={
                            "quantum_only": True,
                            "entanglement_measure": entanglement,
                            "affected_concepts": [concept1.concept_id, concept2.concept_id],
                            "detection_method": "quantum_entanglement_analysis",
                            "quantum_insights": [
                                "Intrication quantique insuffisante pour des concepts liés",
                                "Possible manque de relations contextuelles",
                                "Vérifier les liens sémantiques manquants"
                            ]
                        }
                    )
                    entanglement_inconsistencies.append(inconsistency)
        
        return entanglement_inconsistencies
    
    def _should_be_entangled(self, concept1, concept2) -> bool:
        """Détermine si deux concepts devraient être intriqués."""
        # Critères pour déterminer si deux concepts devraient être liés
        
        # Même type de concept
        if hasattr(concept1, 'concept_type') and hasattr(concept2, 'concept_type'):
            if concept1.concept_type == concept2.concept_type:
                return True
        
        # Similarité dans les prompts
        if hasattr(concept1, 'natural_prompt') and hasattr(concept2, 'natural_prompt'):
            prompt1_words = set(concept1.natural_prompt.lower().split())
            prompt2_words = set(concept2.natural_prompt.lower().split())
            
            # Intersection significative
            common_words = prompt1_words.intersection(prompt2_words)
            if len(common_words) > 2:
                return True
        
        # Valeurs de résonance similaires
        if (hasattr(concept1, 'resonance') and hasattr(concept2, 'resonance') and
            concept1.resonance is not None and concept2.resonance is not None):
            if abs(concept1.resonance - concept2.resonance) < 0.1:
                return True
        
        return False
    
    def get_quantum_inconsistency_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques d'analyse quantique des incohérences."""
        if not self.quantum_analysis_history:
            return {
                "total_quantum_analyses": 0,
                "quantum_enabled": self.quantum_enabled
            }
        
        # Calcul des métriques
        coherence_scores = [analysis.quantum_coherence_score for analysis in self.quantum_analysis_history]
        entanglement_measures = [analysis.entanglement_measure for analysis in self.quantum_analysis_history]
        severity_enhancements = [analysis.severity_enhancement for analysis in self.quantum_analysis_history]
        
        significant_enhancements = [
            enhancement for enhancement in severity_enhancements 
            if enhancement > 1.1
        ]
        
        high_entanglement_cases = [
            measure for measure in entanglement_measures 
            if measure > self.entanglement_threshold
        ]
        
        return {
            "total_quantum_analyses": len(self.quantum_analysis_history),
            "quantum_enabled": self.quantum_enabled,
            "average_coherence_score": sum(coherence_scores) / len(coherence_scores),
            "average_entanglement_measure": sum(entanglement_measures) / len(entanglement_measures),
            "average_severity_enhancement": sum(severity_enhancements) / len(severity_enhancements),
            "significant_enhancements": len(significant_enhancements),
            "enhancement_rate": len(significant_enhancements) / len(severity_enhancements),
            "high_entanglement_cases": len(high_entanglement_cases),
            "entanglement_detection_rate": len(high_entanglement_cases) / len(entanglement_measures),
            "quantum_system_status": self.quantum_core.get_system_status(),
            "configuration": {
                "coherence_threshold": self.coherence_threshold,
                "entanglement_threshold": self.entanglement_threshold,
                "quantum_enhancement_factor": self.quantum_enhancement_factor
            }
        }
    
    def configure_quantum_thresholds(self, coherence_threshold: float = None,
                                   entanglement_threshold: float = None,
                                   enhancement_factor: float = None):
        """Configure les seuils quantiques."""
        if coherence_threshold is not None:
            self.coherence_threshold = coherence_threshold
        
        if entanglement_threshold is not None:
            self.entanglement_threshold = entanglement_threshold
        
        if enhancement_factor is not None:
            self.quantum_enhancement_factor = enhancement_factor
    
    def enable_quantum_analysis(self, enabled: bool = True):
        """Active ou désactive l'analyse quantique."""
        self.quantum_enabled = enabled


if __name__ == "__main__":
    # Test de Thales Quantum
    print("=== Test de Thales Quantum ===")
    
    # Création d'une instance de test
    thales_quantum = ThalesQuantum(quantum_backend="classical")
    
    # Test de détection d'incohérences quantiques
    print("\n1. Test de détection d'incohérences quantiques:")
    inconsistencies = thales_quantum.detect_inconsistencies_quantum_enhanced()
    
    print(f"Incohérences détectées: {len(inconsistencies)}")
    for inconsistency in inconsistencies:
        print(f"- {inconsistency.inconsistency_type}: {inconsistency.description[:60]}...")
        if inconsistency.metadata.get("quantum_enhanced"):
            print(f"  Amélioration quantique: {inconsistency.metadata['severity_enhancement']:.2f}x")
            print(f"  Intrication: {inconsistency.metadata['entanglement_measure']:.3f}")
    
    # Statistiques quantiques
    print("\n2. Statistiques d'analyse quantique:")
    stats = thales_quantum.get_quantum_inconsistency_statistics()
    print(f"Analyses quantiques: {stats['total_quantum_analyses']}")
    if stats['total_quantum_analyses'] > 0:
        print(f"Score de cohérence moyen: {stats['average_coherence_score']:.3f}")
        print(f"Mesure d'intrication moyenne: {stats['average_entanglement_measure']:.3f}")
        print(f"Taux de détection d'intrication élevée: {stats['entanglement_detection_rate']:.1%}")
    
    print("\n=== Test terminé ===")

