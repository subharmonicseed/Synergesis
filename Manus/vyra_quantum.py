"""
Module Vyra Quantum - Intégration quantique pour la génération de suggestions

Ce module étend Vyra avec des capacités quantiques pour optimiser
la génération et le ranking des suggestions créatives.
"""

import time
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from quantum_core import QuantumCore, create_quantum_core
from vyra_evolved import VyraEvolved, CreativeSuggestion


@dataclass
class QuantumSuggestionOptimization:
    """Résultat d'optimisation quantique de suggestions."""
    optimization_id: str
    original_suggestions: List[CreativeSuggestion]
    optimized_ranking: List[int]
    quantum_scores: List[float]
    optimization_confidence: float
    quantum_insights: List[str]
    execution_time: float
    metadata: Dict[str, Any]


class VyraQuantum(VyraEvolved):
    """Version quantique de Vyra avec optimisation de suggestions."""
    
    def __init__(self, nous_instance=None, quantum_backend: str = "classical"):
        super().__init__(nous_instance)
        
        # Initialisation du module quantique
        self.quantum_core = create_quantum_core(quantum_backend)
        self.quantum_enabled = True
        self.optimization_history: List[QuantumSuggestionOptimization] = []
        
        # Configuration quantique
        self.quantum_optimization_threshold = 0.7
        self.diversity_weight = 0.3  # Poids pour la diversité quantique
        self.coherence_weight = 0.4  # Poids pour la cohérence quantique
        self.novelty_weight = 0.3    # Poids pour la nouveauté quantique
    
    def generate_suggestions_quantum_optimized(self, gaps: List) -> List[CreativeSuggestion]:
        """Génère des suggestions avec optimisation quantique."""
        # Génération classique de base
        classical_suggestions = super().generate_suggestions(gaps)
        
        if not self.quantum_enabled or len(classical_suggestions) < 2:
            return classical_suggestions
        
        # Optimisation quantique des suggestions
        optimization_result = self._optimize_suggestions_quantum(classical_suggestions, gaps)
        
        # Réorganisation selon l'optimisation quantique
        optimized_suggestions = self._reorder_suggestions(
            classical_suggestions, 
            optimization_result
        )
        
        # Enregistrement de l'optimisation
        self.optimization_history.append(optimization_result)
        
        return optimized_suggestions
    
    def _optimize_suggestions_quantum(self, suggestions: List[CreativeSuggestion], 
                                    gaps: List) -> QuantumSuggestionOptimization:
        """Optimise le ranking des suggestions avec l'algorithme quantique."""
        start_time = time.time()
        
        # Préparation des données pour l'optimisation quantique
        optimization_data = {
            "optimization_type": "suggestion_ranking",
            "suggestions": [
                {
                    "suggestion_id": suggestion.suggestion_id,
                    "priority": suggestion.priority,
                    "description": suggestion.description,
                    "suggestion_type": suggestion.suggestion_type,
                    "validation_score": suggestion.validation_score,
                    "features": self._extract_suggestion_features(suggestion)
                }
                for suggestion in suggestions
            ],
            "context": {
                "gaps": [
                    {
                        "gap_type": gap.gap_type,
                        "severity": gap.severity,
                        "concept_id": gap.concept_id
                    }
                    for gap in gaps
                ],
                "optimization_criteria": {
                    "diversity_weight": self.diversity_weight,
                    "coherence_weight": self.coherence_weight,
                    "novelty_weight": self.novelty_weight
                }
            }
        }
        
        # Exécution de l'optimisation quantique
        quantum_result = self.quantum_core.optimize(optimization_data)
        
        # Extraction des résultats
        classical_interpretation = quantum_result.classical_interpretation
        
        if classical_interpretation.get("optimization_successful", False):
            optimized_ranking = classical_interpretation.get("optimal_solution", list(range(len(suggestions))))
            quantum_scores = quantum_result.quantum_output.get("scores", [0.5] * len(suggestions))
        else:
            # Fallback sur le ranking classique
            optimized_ranking = list(range(len(suggestions)))
            quantum_scores = [suggestion.priority for suggestion in suggestions]
        
        # Génération d'insights quantiques
        quantum_insights = self._generate_optimization_insights(
            suggestions, optimized_ranking, quantum_scores, quantum_result
        )
        
        execution_time = time.time() - start_time
        
        return QuantumSuggestionOptimization(
            optimization_id=str(uuid.uuid4())[:8],
            original_suggestions=suggestions,
            optimized_ranking=optimized_ranking,
            quantum_scores=quantum_scores,
            optimization_confidence=quantum_result.confidence_score,
            quantum_insights=quantum_insights,
            execution_time=execution_time,
            metadata={
                "quantum_result_id": quantum_result.result_id,
                "backend_used": quantum_result.backend_used,
                "optimization_criteria": optimization_data["context"]["optimization_criteria"]
            }
        )
    
    def _extract_suggestion_features(self, suggestion: CreativeSuggestion) -> List[float]:
        """Extrait des features quantifiables d'une suggestion."""
        features = []
        
        # Feature de priorité
        features.append(suggestion.priority)
        
        # Features basées sur le type de suggestion
        type_encoding = {
            "ENRICH_CONCEPT_PROMPT": 0.2,
            "COMPLETE_MISSING_FIELD": 0.4,
            "CLARIFY_VAGUE_DESCRIPTION": 0.6,
            "ADD_CONTEXTUAL_RELATIONS": 0.8
        }
        features.append(type_encoding.get(suggestion.suggestion_type, 0.5))
        
        # Features basées sur la description
        description_length = len(suggestion.description) / 100.0
        features.append(min(description_length, 1.0))
        
        # Feature de complexité (nombre de mots)
        word_count = len(suggestion.description.split()) / 20.0
        features.append(min(word_count, 1.0))
        
        # Feature de validation
        features.append(suggestion.validation_score)
        
        # Features basées sur les métadonnées
        if "current_length" in suggestion.metadata:
            length_feature = suggestion.metadata["current_length"] / 200.0
            features.append(min(length_feature, 1.0))
        else:
            features.append(0.5)
        
        return features
    
    def _reorder_suggestions(self, original_suggestions: List[CreativeSuggestion],
                           optimization: QuantumSuggestionOptimization) -> List[CreativeSuggestion]:
        """Réorganise les suggestions selon l'optimisation quantique."""
        # Création de nouvelles suggestions avec scores quantiques mis à jour
        reordered_suggestions = []
        
        for i, original_index in enumerate(optimization.optimized_ranking):
            if original_index < len(original_suggestions):
                original_suggestion = original_suggestions[original_index]
                quantum_score = optimization.quantum_scores[original_index]
                
                # Création d'une nouvelle suggestion avec métadonnées quantiques
                enhanced_metadata = original_suggestion.metadata.copy()
                enhanced_metadata.update({
                    "quantum_optimized": True,
                    "quantum_score": quantum_score,
                    "original_priority": original_suggestion.priority,
                    "quantum_ranking": i,
                    "optimization_id": optimization.optimization_id,
                    "quantum_insights": optimization.quantum_insights
                })
                
                # Mise à jour de la priorité avec le score quantique
                enhanced_priority = (original_suggestion.priority + quantum_score) / 2.0
                
                enhanced_suggestion = CreativeSuggestion(
                    suggestion_id=original_suggestion.suggestion_id + "_quantum",
                    concept_id=original_suggestion.concept_id,
                    suggestion_type=original_suggestion.suggestion_type,
                    title=original_suggestion.title + " [Quantum Optimized]",
                    description=original_suggestion.description,
                    priority=enhanced_priority,
                    metadata=enhanced_metadata,
                    generated_by=original_suggestion.generated_by + "_quantum",
                    validation_score=original_suggestion.validation_score
                )
                
                reordered_suggestions.append(enhanced_suggestion)
        
        return reordered_suggestions
    
    def _generate_optimization_insights(self, suggestions: List[CreativeSuggestion],
                                      optimized_ranking: List[int],
                                      quantum_scores: List[float],
                                      quantum_result) -> List[str]:
        """Génère des insights sur l'optimisation quantique."""
        insights = []
        
        # Analyse des changements de ranking
        original_ranking = list(range(len(suggestions)))
        ranking_changes = sum(1 for i, j in zip(original_ranking, optimized_ranking) if i != j)
        
        if ranking_changes > 0:
            insights.append(
                f"Optimisation quantique a modifié le ranking de {ranking_changes} suggestions"
            )
        else:
            insights.append("L'optimisation quantique confirme le ranking classique")
        
        # Analyse des scores quantiques
        avg_quantum_score = sum(quantum_scores) / len(quantum_scores)
        max_quantum_score = max(quantum_scores)
        min_quantum_score = min(quantum_scores)
        
        insights.append(
            f"Score quantique moyen: {avg_quantum_score:.3f} "
            f"(range: {min_quantum_score:.3f} - {max_quantum_score:.3f})"
        )
        
        # Identification de la meilleure suggestion quantique
        best_quantum_index = quantum_scores.index(max_quantum_score)
        if best_quantum_index < len(suggestions):
            best_suggestion = suggestions[best_quantum_index]
            insights.append(
                f"Meilleure suggestion quantique: '{best_suggestion.title}' "
                f"(score: {max_quantum_score:.3f})"
            )
        
        # Analyse de la diversité quantique
        score_variance = sum((score - avg_quantum_score) ** 2 for score in quantum_scores) / len(quantum_scores)
        if score_variance > 0.1:
            insights.append("Forte diversité quantique détectée - suggestions très variées")
        else:
            insights.append("Diversité quantique modérée - suggestions relativement homogènes")
        
        # Insights spécifiques au résultat quantique
        quantum_output = quantum_result.quantum_output
        if "optimization_quality" in quantum_output:
            quality = quantum_output["optimization_quality"]
            if quality > 0.8:
                insights.append("Optimisation quantique de haute qualité")
            elif quality > 0.6:
                insights.append("Optimisation quantique de qualité modérée")
            else:
                insights.append("Optimisation quantique de qualité limitée")
        
        return insights
    
    def generate_quantum_creative_suggestions(self, concept_data: Dict[str, Any], 
                                            num_suggestions: int = 3) -> List[CreativeSuggestion]:
        """Génère des suggestions créatives en utilisant directement l'optimisation quantique."""
        # Génération de suggestions de base
        base_suggestions = []
        
        # Création de suggestions variées pour l'optimisation
        suggestion_templates = [
            {
                "type": "ENRICH_CONCEPT_PROMPT",
                "title": "Enrichissement quantique du prompt",
                "description": "Utiliser l'optimisation quantique pour générer un prompt plus riche et contextuel"
            },
            {
                "type": "QUANTUM_PATTERN_ANALYSIS",
                "title": "Analyse de patterns quantiques",
                "description": "Appliquer la détection de patterns quantiques pour identifier des améliorations"
            },
            {
                "type": "COHERENCE_OPTIMIZATION",
                "title": "Optimisation de cohérence quantique",
                "description": "Utiliser l'analyse de cohérence quantique pour améliorer la consistance"
            },
            {
                "type": "QUANTUM_DIVERSITY_ENHANCEMENT",
                "title": "Amélioration de diversité quantique",
                "description": "Exploiter la superposition quantique pour générer des perspectives diverses"
            }
        ]
        
        for i, template in enumerate(suggestion_templates[:num_suggestions]):
            suggestion = CreativeSuggestion(
                suggestion_id=f"quantum_{uuid.uuid4().hex[:8]}",
                concept_id=concept_data.get("concept_id", "unknown"),
                suggestion_type=template["type"],
                title=template["title"],
                description=template["description"],
                priority=0.5 + (i * 0.1),  # Priorités variées
                metadata={
                    "quantum_generated": True,
                    "template_used": template["type"],
                    "generation_method": "quantum_creative"
                },
                generated_by="vyra_quantum",
                validation_score=0.0
            )
            base_suggestions.append(suggestion)
        
        # Optimisation quantique des suggestions générées
        if len(base_suggestions) > 1:
            optimization_data = {
                "optimization_type": "creative_enhancement",
                "suggestions": [
                    {
                        "suggestion_id": s.suggestion_id,
                        "priority": s.priority,
                        "description": s.description,
                        "features": self._extract_suggestion_features(s)
                    }
                    for s in base_suggestions
                ],
                "context": concept_data
            }
            
            quantum_result = self.quantum_core.optimize(optimization_data)
            
            # Application des résultats quantiques
            if quantum_result.classical_interpretation.get("optimization_successful", False):
                optimal_ranking = quantum_result.classical_interpretation.get("optimal_solution", list(range(len(base_suggestions))))
                
                # Réorganisation et amélioration
                optimized_suggestions = []
                for i, original_index in enumerate(optimal_ranking):
                    if original_index < len(base_suggestions):
                        suggestion = base_suggestions[original_index]
                        
                        # Amélioration quantique de la description
                        quantum_enhanced_description = self._enhance_description_quantum(
                            suggestion.description, quantum_result
                        )
                        
                        enhanced_suggestion = CreativeSuggestion(
                            suggestion_id=suggestion.suggestion_id,
                            concept_id=suggestion.concept_id,
                            suggestion_type=suggestion.suggestion_type,
                            title=suggestion.title,
                            description=quantum_enhanced_description,
                            priority=suggestion.priority * (1.0 + quantum_result.confidence_score * 0.2),
                            metadata={
                                **suggestion.metadata,
                                "quantum_enhanced_description": True,
                                "quantum_confidence": quantum_result.confidence_score
                            },
                            generated_by=suggestion.generated_by,
                            validation_score=quantum_result.confidence_score
                        )
                        
                        optimized_suggestions.append(enhanced_suggestion)
                
                return optimized_suggestions
        
        return base_suggestions
    
    def _enhance_description_quantum(self, original_description: str, 
                                   quantum_result) -> str:
        """Améliore une description avec les insights quantiques."""
        enhanced_description = original_description
        
        # Ajout d'insights quantiques
        confidence = quantum_result.confidence_score
        
        if confidence > 0.8:
            enhanced_description += " Cette approche bénéficie d'une optimisation quantique de haute confiance, "
            enhanced_description += "suggérant une efficacité supérieure aux méthodes classiques."
        
        elif confidence > 0.6:
            enhanced_description += " L'analyse quantique indique un potentiel d'amélioration modéré "
            enhanced_description += "par rapport aux approches conventionnelles."
        
        # Ajout de recommandations spécifiques
        quantum_output = quantum_result.quantum_output
        if "optimization_quality" in quantum_output:
            quality = quantum_output["optimization_quality"]
            if quality > 0.7:
                enhanced_description += " Recommandation quantique: Prioriser cette suggestion "
                enhanced_description += "en raison de son score d'optimisation élevé."
        
        return enhanced_description
    
    def get_quantum_optimization_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques d'optimisation quantique."""
        if not self.optimization_history:
            return {
                "total_optimizations": 0,
                "quantum_enabled": self.quantum_enabled
            }
        
        confidences = [opt.optimization_confidence for opt in self.optimization_history]
        execution_times = [opt.execution_time for opt in self.optimization_history]
        
        # Calcul des améliorations
        ranking_changes = []
        for opt in self.optimization_history:
            original_ranking = list(range(len(opt.original_suggestions)))
            changes = sum(1 for i, j in zip(original_ranking, opt.optimized_ranking) if i != j)
            ranking_changes.append(changes)
        
        return {
            "total_optimizations": len(self.optimization_history),
            "quantum_enabled": self.quantum_enabled,
            "average_confidence": sum(confidences) / len(confidences),
            "average_execution_time": sum(execution_times) / len(execution_times),
            "average_ranking_changes": sum(ranking_changes) / len(ranking_changes),
            "optimization_success_rate": len([c for c in confidences if c > self.quantum_optimization_threshold]) / len(confidences),
            "quantum_system_status": self.quantum_core.get_system_status(),
            "configuration": {
                "optimization_threshold": self.quantum_optimization_threshold,
                "diversity_weight": self.diversity_weight,
                "coherence_weight": self.coherence_weight,
                "novelty_weight": self.novelty_weight
            }
        }
    
    def configure_quantum_weights(self, diversity: float = None, 
                                 coherence: float = None, novelty: float = None):
        """Configure les poids d'optimisation quantique."""
        if diversity is not None:
            self.diversity_weight = diversity
        if coherence is not None:
            self.coherence_weight = coherence
        if novelty is not None:
            self.novelty_weight = novelty
        
        # Normalisation pour que la somme soit 1.0
        total = self.diversity_weight + self.coherence_weight + self.novelty_weight
        if total > 0:
            self.diversity_weight /= total
            self.coherence_weight /= total
            self.novelty_weight /= total
    
    def enable_quantum_optimization(self, enabled: bool = True):
        """Active ou désactive l'optimisation quantique."""
        self.quantum_enabled = enabled


if __name__ == "__main__":
    # Test de Vyra Quantum
    print("=== Test de Vyra Quantum ===")
    
    # Création d'une instance de test
    vyra_quantum = VyraQuantum(quantum_backend="classical")
    
    # Test de génération créative quantique
    print("\n1. Test de génération créative quantique:")
    concept_data = {
        "concept_id": "test_concept",
        "natural_prompt": "Concept de test pour la génération quantique",
        "concept_type": "TEST"
    }
    
    creative_suggestions = vyra_quantum.generate_quantum_creative_suggestions(concept_data, 3)
    
    print(f"Suggestions créatives générées: {len(creative_suggestions)}")
    for i, suggestion in enumerate(creative_suggestions):
        print(f"{i+1}. {suggestion.title}")
        print(f"   Type: {suggestion.suggestion_type}")
        print(f"   Priorité: {suggestion.priority:.3f}")
        print(f"   Validation: {suggestion.validation_score:.3f}")
    
    # Statistiques d'optimisation
    print("\n2. Statistiques d'optimisation quantique:")
    stats = vyra_quantum.get_quantum_optimization_statistics()
    print(f"Optimisations totales: {stats['total_optimizations']}")
    print(f"Mode quantique activé: {stats['quantum_enabled']}")
    
    if stats['total_optimizations'] > 0:
        print(f"Confiance moyenne: {stats['average_confidence']:.3f}")
        print(f"Temps d'exécution moyen: {stats['average_execution_time']:.3f}s")
    
    print("\n=== Test terminé ===")

