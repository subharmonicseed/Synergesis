"""
Module Selene Quantum - Intégration quantique pour la détection de lacunes

Ce module étend Selene avec des capacités quantiques pour améliorer
la détection de patterns complexes dans les lacunes de connaissance.
"""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from quantum_core import QuantumCore, QuantumBackend, create_quantum_core
from selene_evolved import SeleneEvolved, KnowledgeGap


@dataclass
class QuantumGapAnalysis:
    """Résultat d'analyse quantique d'une lacune."""
    gap_id: str
    quantum_pattern_score: float
    quantum_confidence: float
    classical_confidence: float
    enhancement_factor: float
    quantum_recommendations: List[str]
    metadata: Dict[str, Any]


class SeleneQuantum(SeleneEvolved):
    """Version quantique de Selene avec détection de patterns avancée."""
    
    def __init__(self, nous_instance=None, quantum_backend: str = "classical"):
        super().__init__(nous_instance)
        
        # Initialisation du module quantique
        self.quantum_core = create_quantum_core(quantum_backend)
        self.quantum_enabled = True
        self.quantum_analysis_history: List[QuantumGapAnalysis] = []
        
        # Configuration quantique
        self.quantum_threshold = 0.6  # Seuil pour considérer un pattern quantique significatif
        self.enhancement_threshold = 1.2  # Facteur minimum d'amélioration quantique
    
    def detect_gaps_quantum_enhanced(self) -> List[KnowledgeGap]:
        """Détection de lacunes avec amélioration quantique."""
        # Détection classique de base
        classical_gaps = super().detect_gaps()
        
        if not self.quantum_enabled:
            return classical_gaps
        
        # Amélioration quantique des lacunes détectées
        enhanced_gaps = []
        
        for gap in classical_gaps:
            # Analyse quantique de la lacune
            quantum_analysis = self._analyze_gap_quantum(gap)
            
            # Amélioration de la lacune avec les insights quantiques
            enhanced_gap = self._enhance_gap_with_quantum(gap, quantum_analysis)
            enhanced_gaps.append(enhanced_gap)
            
            # Enregistrement de l'analyse
            self.quantum_analysis_history.append(quantum_analysis)
        
        # Détection de patterns quantiques additionnels
        additional_gaps = self._detect_quantum_only_patterns()
        enhanced_gaps.extend(additional_gaps)
        
        return enhanced_gaps
    
    def _analyze_gap_quantum(self, gap: KnowledgeGap) -> QuantumGapAnalysis:
        """Analyse quantique d'une lacune spécifique."""
        # Préparation des données pour l'analyse quantique
        gap_data = {
            "gap_type": gap.gap_type,
            "concept_id": gap.concept_id,
            "description": gap.description,
            "severity": gap.severity,
            "metadata": gap.metadata,
            "features": self._extract_gap_features(gap)
        }
        
        # Détection de patterns quantiques
        pattern_result = self.quantum_core.detect_patterns(gap_data)
        
        # Calcul du facteur d'amélioration
        classical_confidence = gap.severity
        quantum_confidence = pattern_result.confidence_score
        enhancement_factor = quantum_confidence / max(classical_confidence, 0.1)
        
        # Génération de recommandations quantiques
        quantum_recommendations = self._generate_quantum_recommendations(
            gap, pattern_result
        )
        
        return QuantumGapAnalysis(
            gap_id=f"{gap.concept_id}_{gap.gap_type}",
            quantum_pattern_score=pattern_result.classical_interpretation.get("pattern_strength", 0.0),
            quantum_confidence=quantum_confidence,
            classical_confidence=classical_confidence,
            enhancement_factor=enhancement_factor,
            quantum_recommendations=quantum_recommendations,
            metadata={
                "quantum_result_id": pattern_result.result_id,
                "execution_time": pattern_result.execution_time,
                "backend_used": pattern_result.backend_used
            }
        )
    
    def _extract_gap_features(self, gap: KnowledgeGap) -> List[float]:
        """Extrait des features quantifiables d'une lacune."""
        features = []
        
        # Features basées sur le type de lacune
        gap_type_encoding = {
            "SHORT_PROMPT": 0.1,
            "MISSING_FIELD": 0.3,
            "VAGUE_DESCRIPTION": 0.5,
            "MISSING_CONTEXT": 0.7
        }
        features.append(gap_type_encoding.get(gap.gap_type, 0.5))
        
        # Features basées sur la sévérité
        features.append(gap.severity)
        
        # Features basées sur la description
        description_length = len(gap.description) / 100.0
        features.append(min(description_length, 1.0))
        
        # Features basées sur les métadonnées
        if "current_length" in gap.metadata:
            normalized_length = gap.metadata["current_length"] / 200.0
            features.append(min(normalized_length, 1.0))
        else:
            features.append(0.5)
        
        # Features contextuelles
        if "missing_fields" in gap.metadata:
            field_count = len(gap.metadata["missing_fields"]) / 5.0
            features.append(min(field_count, 1.0))
        else:
            features.append(0.0)
        
        # Features temporelles (si disponibles)
        if hasattr(gap, 'timestamp'):
            # Normalisation temporelle (récence)
            current_time = time.time()
            age_hours = (current_time - gap.timestamp) / 3600.0
            recency = 1.0 / (1.0 + age_hours / 24.0)  # Décroissance sur 24h
            features.append(recency)
        else:
            features.append(0.5)
        
        return features
    
    def _enhance_gap_with_quantum(self, gap: KnowledgeGap, 
                                 quantum_analysis: QuantumGapAnalysis) -> KnowledgeGap:
        """Améliore une lacune avec les insights quantiques."""
        # Mise à jour de la sévérité si l'amélioration quantique est significative
        if quantum_analysis.enhancement_factor > self.enhancement_threshold:
            enhanced_severity = min(
                gap.severity * quantum_analysis.enhancement_factor, 
                1.0
            )
        else:
            enhanced_severity = gap.severity
        
        # Enrichissement de la description avec les insights quantiques
        enhanced_description = gap.description
        if quantum_analysis.quantum_pattern_score > self.quantum_threshold:
            enhanced_description += f" [Quantum: Pattern complexe détecté avec score {quantum_analysis.quantum_pattern_score:.3f}]"
        
        # Enrichissement des métadonnées
        enhanced_metadata = gap.metadata.copy()
        enhanced_metadata.update({
            "quantum_enhanced": True,
            "quantum_pattern_score": quantum_analysis.quantum_pattern_score,
            "quantum_confidence": quantum_analysis.quantum_confidence,
            "enhancement_factor": quantum_analysis.enhancement_factor,
            "quantum_recommendations": quantum_analysis.quantum_recommendations
        })
        
        # Création de la lacune améliorée
        enhanced_gap = KnowledgeGap(
            gap_type=gap.gap_type,
            concept_id=gap.concept_id,
            description=enhanced_description,
            severity=enhanced_severity,
            metadata=enhanced_metadata,
            reasoning_trajectory=getattr(gap, 'reasoning_trajectory', []) + [
                f"Analyse quantique appliquée: amélioration {quantum_analysis.enhancement_factor:.2f}x"
            ]
        )
        
        return enhanced_gap
    
    def _generate_quantum_recommendations(self, gap: KnowledgeGap, 
                                        pattern_result) -> List[str]:
        """Génère des recommandations basées sur l'analyse quantique."""
        recommendations = []
        
        pattern_interpretation = pattern_result.classical_interpretation
        
        if pattern_interpretation.get("pattern_detected", False):
            pattern_strength = pattern_interpretation.get("pattern_strength", 0.0)
            
            if pattern_strength > 0.8:
                recommendations.append(
                    "Pattern quantique très fort détecté - cette lacune pourrait révéler "
                    "des problèmes systémiques plus profonds"
                )
                recommendations.append(
                    "Recommandation: Analyser les concepts connexes pour identifier "
                    "des patterns similaires"
                )
            
            elif pattern_strength > 0.6:
                recommendations.append(
                    "Pattern quantique modéré détecté - lacune potentiellement liée "
                    "à d'autres dans le système"
                )
                recommendations.append(
                    "Recommandation: Vérifier la cohérence avec les concepts similaires"
                )
            
            else:
                recommendations.append(
                    "Pattern quantique faible détecté - lacune probablement isolée"
                )
        
        else:
            recommendations.append(
                "Aucun pattern quantique significatif - traitement classique recommandé"
            )
        
        # Recommandations spécifiques au type de lacune
        if gap.gap_type == "SHORT_PROMPT":
            recommendations.append(
                "Quantum insight: Utiliser l'optimisation quantique pour générer "
                "des extensions de prompt optimales"
            )
        
        elif gap.gap_type == "MISSING_FIELD":
            recommendations.append(
                "Quantum insight: Appliquer l'analyse de cohérence quantique pour "
                "déterminer les valeurs de champs les plus cohérentes"
            )
        
        elif gap.gap_type == "VAGUE_DESCRIPTION":
            recommendations.append(
                "Quantum insight: Utiliser la détection de patterns quantiques pour "
                "identifier des clarifications spécifiques"
            )
        
        return recommendations
    
    def _detect_quantum_only_patterns(self) -> List[KnowledgeGap]:
        """Détecte des patterns que seule l'analyse quantique peut révéler."""
        additional_gaps = []
        
        # Récupération de tous les concepts pour l'analyse globale
        all_concepts = self.nous.get_all_concepts()
        
        if len(all_concepts) < 2:
            return additional_gaps
        
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
                
                # Création d'une lacune pour l'incohérence quantique
                if len(concept_indices) >= 2:
                    concept1 = all_concepts[concept_indices[0]]
                    concept2 = all_concepts[concept_indices[1]]
                    
                    quantum_gap = KnowledgeGap(
                        gap_type="QUANTUM_INCOHERENCE",
                        concept_id=f"{concept1.concept_id}+{concept2.concept_id}",
                        description=f"Incohérence quantique détectée entre '{concept1.concept_id}' "
                                  f"et '{concept2.concept_id}' (score: {coherence_score:.3f})",
                        severity=1.0 - coherence_score,
                        metadata={
                            "quantum_only": True,
                            "coherence_score": coherence_score,
                            "affected_concepts": [concept1.concept_id, concept2.concept_id],
                            "detection_method": "quantum_coherence_analysis"
                        },
                        reasoning_trajectory=[
                            "Analyse de cohérence quantique globale appliquée",
                            f"Incohérence détectée avec score {coherence_score:.3f}",
                            "Cette lacune n'aurait pas été détectée par les méthodes classiques"
                        ]
                    )
                    
                    additional_gaps.append(quantum_gap)
        
        return additional_gaps
    
    def get_quantum_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques d'utilisation quantique."""
        if not self.quantum_analysis_history:
            return {
                "total_quantum_analyses": 0,
                "quantum_enabled": self.quantum_enabled
            }
        
        enhancement_factors = [analysis.enhancement_factor for analysis in self.quantum_analysis_history]
        quantum_confidences = [analysis.quantum_confidence for analysis in self.quantum_analysis_history]
        pattern_scores = [analysis.quantum_pattern_score for analysis in self.quantum_analysis_history]
        
        significant_enhancements = [
            factor for factor in enhancement_factors 
            if factor > self.enhancement_threshold
        ]
        
        return {
            "total_quantum_analyses": len(self.quantum_analysis_history),
            "quantum_enabled": self.quantum_enabled,
            "average_enhancement_factor": sum(enhancement_factors) / len(enhancement_factors),
            "significant_enhancements": len(significant_enhancements),
            "enhancement_rate": len(significant_enhancements) / len(enhancement_factors),
            "average_quantum_confidence": sum(quantum_confidences) / len(quantum_confidences),
            "average_pattern_score": sum(pattern_scores) / len(pattern_scores),
            "quantum_system_status": self.quantum_core.get_system_status()
        }
    
    def enable_quantum_mode(self, enabled: bool = True):
        """Active ou désactive le mode quantique."""
        self.quantum_enabled = enabled
    
    def set_quantum_thresholds(self, pattern_threshold: float = None, 
                              enhancement_threshold: float = None):
        """Configure les seuils quantiques."""
        if pattern_threshold is not None:
            self.quantum_threshold = pattern_threshold
        
        if enhancement_threshold is not None:
            self.enhancement_threshold = enhancement_threshold
    
    def export_quantum_analysis(self, filepath: str) -> bool:
        """Exporte l'historique d'analyse quantique."""
        try:
            import json
            
            export_data = {
                "export_timestamp": time.time(),
                "quantum_enabled": self.quantum_enabled,
                "quantum_threshold": self.quantum_threshold,
                "enhancement_threshold": self.enhancement_threshold,
                "total_analyses": len(self.quantum_analysis_history),
                "analyses": [
                    {
                        "gap_id": analysis.gap_id,
                        "quantum_pattern_score": analysis.quantum_pattern_score,
                        "quantum_confidence": analysis.quantum_confidence,
                        "classical_confidence": analysis.classical_confidence,
                        "enhancement_factor": analysis.enhancement_factor,
                        "quantum_recommendations": analysis.quantum_recommendations,
                        "metadata": analysis.metadata
                    }
                    for analysis in self.quantum_analysis_history
                ],
                "statistics": self.get_quantum_statistics()
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"Erreur lors de l'export quantique: {e}")
            return False


if __name__ == "__main__":
    # Test de Selene Quantum
    print("=== Test de Selene Quantum ===")
    
    # Création d'une instance de test
    selene_quantum = SeleneQuantum(quantum_backend="classical")
    
    # Test de détection avec amélioration quantique
    print("\n1. Test de détection quantique:")
    gaps = selene_quantum.detect_gaps_quantum_enhanced()
    
    print(f"Lacunes détectées: {len(gaps)}")
    for gap in gaps:
        print(f"- {gap.gap_type}: {gap.description[:50]}...")
        if gap.metadata.get("quantum_enhanced"):
            print(f"  Amélioration quantique: {gap.metadata['enhancement_factor']:.2f}x")
    
    # Statistiques quantiques
    print("\n2. Statistiques quantiques:")
    stats = selene_quantum.get_quantum_statistics()
    print(f"Analyses quantiques: {stats['total_quantum_analyses']}")
    if stats['total_quantum_analyses'] > 0:
        print(f"Facteur d'amélioration moyen: {stats['average_enhancement_factor']:.2f}")
        print(f"Taux d'amélioration significative: {stats['enhancement_rate']:.1%}")
    
    print("\n=== Test terminé ===")

