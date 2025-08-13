"""
Module de détection de lacunes de connaissance dans le blackboard NOUS avec capacités d'évolution.

Selene Evolved analyse les concepts stockés dans NOUS et identifie les lacunes
potentielles qui pourraient nécessiter une attention particulière ou
des enrichissements supplémentaires. Cette version intègre des boucles
d'évolution de type AlphaEvolve/DGM pour l'auto-modification du raisonnement.
"""

import json
import time
import random
import hashlib
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from nous_enhanced import NousEnhanced as Nous, Concept
from glyph_bus import GlyphBus


@dataclass
class ReasoningTrajectory:
    """Représente une trajectoire de raisonnement pour l'archive d'expérience."""
    trajectory_id: str
    gap_type: str
    reasoning_steps: List[str]
    success_score: float
    execution_time: float
    metadata: Dict[str, Any]
    timestamp: float


@dataclass
class EvolutionVariant:
    """Représente une variante évolutive d'un algorithme de détection."""
    variant_id: str
    parent_id: Optional[str]
    algorithm_code: str
    performance_metrics: Dict[str, float]
    validation_results: Dict[str, Any]
    generation: int


class ExperienceArchive:
    """Archive d'expériences auto-améliorante pour Selene."""
    
    def __init__(self, max_trajectories: int = 1000):
        self.trajectories: Dict[str, ReasoningTrajectory] = {}
        self.max_trajectories = max_trajectories
    
    def add_trajectory(self, trajectory: ReasoningTrajectory):
        """Ajoute une trajectoire à l'archive."""
        self.trajectories[trajectory.trajectory_id] = trajectory
        
        # Nettoyage si nécessaire
        if len(self.trajectories) > self.max_trajectories:
            self._cleanup_old_trajectories()
    
    def _cleanup_old_trajectories(self):
        """Supprime les trajectoires les moins performantes."""
        sorted_trajectories = sorted(
            self.trajectories.values(),
            key=lambda t: t.success_score,
            reverse=True
        )
        
        # Garde seulement les 80% meilleures
        keep_count = int(self.max_trajectories * 0.8)
        trajectories_to_keep = sorted_trajectories[:keep_count]
        
        self.trajectories = {
            t.trajectory_id: t for t in trajectories_to_keep
        }
    
    def get_best_trajectories(self, gap_type: str, limit: int = 5) -> List[ReasoningTrajectory]:
        """Récupère les meilleures trajectoires pour un type de lacune donné."""
        relevant_trajectories = [
            t for t in self.trajectories.values()
            if t.gap_type == gap_type
        ]
        
        return sorted(
            relevant_trajectories,
            key=lambda t: t.success_score,
            reverse=True
        )[:limit]


class EvolutionEngine:
    """Moteur d'évolution pour les algorithmes de détection de Selene."""
    
    def __init__(self):
        self.variants: Dict[str, EvolutionVariant] = {}
        self.current_generation = 0
    
    def create_initial_variant(self, algorithm_code: str) -> EvolutionVariant:
        """Crée la variante initiale d'un algorithme."""
        variant_id = self._generate_variant_id()
        variant = EvolutionVariant(
            variant_id=variant_id,
            parent_id=None,
            algorithm_code=algorithm_code,
            performance_metrics={},
            validation_results={},
            generation=0
        )
        self.variants[variant_id] = variant
        return variant
    
    def evolve_variant(self, parent_variant: EvolutionVariant, 
                      mutation_strategy: str = "random") -> EvolutionVariant:
        """Fait évoluer une variante d'algorithme."""
        variant_id = self._generate_variant_id()
        
        # Mutation du code de l'algorithme
        mutated_code = self._mutate_algorithm(
            parent_variant.algorithm_code, 
            mutation_strategy
        )
        
        variant = EvolutionVariant(
            variant_id=variant_id,
            parent_id=parent_variant.variant_id,
            algorithm_code=mutated_code,
            performance_metrics={},
            validation_results={},
            generation=parent_variant.generation + 1
        )
        
        self.variants[variant_id] = variant
        self.current_generation = max(self.current_generation, variant.generation)
        return variant
    
    def _generate_variant_id(self) -> str:
        """Génère un ID unique pour une variante."""
        timestamp = str(time.time())
        random_part = str(random.randint(1000, 9999))
        return hashlib.md5(f"{timestamp}_{random_part}".encode()).hexdigest()[:8]
    
    def _mutate_algorithm(self, algorithm_code: str, strategy: str) -> str:
        """Mute un algorithme selon une stratégie donnée."""
        if strategy == "random":
            # Mutation simple : ajustement des seuils
            mutations = [
                ("self.min_prompt_length = 10", "self.min_prompt_length = 15"),
                ("severity = 0.8", "severity = 0.9"),
                ("severity = 0.6", "severity = 0.7"),
                ("len(prompt) < 20", "len(prompt) < 25"),
            ]
            
            for old, new in mutations:
                if old in algorithm_code:
                    algorithm_code = algorithm_code.replace(old, new, 1)
                    break
        
        return algorithm_code
    
    def benchmark_variant(self, variant: EvolutionVariant, 
                         test_concepts: List[Concept]) -> Dict[str, float]:
        """Évalue les performances d'une variante."""
        start_time = time.time()
        
        try:
            # Exécution de l'algorithme (simulation)
            gaps_detected = len(test_concepts) * random.uniform(0.1, 0.9)
            accuracy = random.uniform(0.7, 0.95)
            precision = random.uniform(0.6, 0.9)
            recall = random.uniform(0.5, 0.85)
            
            execution_time = time.time() - start_time
            
            metrics = {
                "gaps_detected": gaps_detected,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "execution_time": execution_time,
                "f1_score": 2 * (precision * recall) / (precision + recall)
            }
            
            variant.performance_metrics = metrics
            return metrics
            
        except Exception as e:
            return {"error": str(e), "execution_time": time.time() - start_time}


class IntrospectiveLayer:
    """Couche introspective pour la vérification des erreurs et le feedback."""
    
    def __init__(self):
        self.error_patterns: Dict[str, int] = {}
        self.feedback_history: List[Dict[str, Any]] = []
    
    def check_reasoning_step(self, step: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Vérifie un pas de raisonnement et fournit du feedback."""
        feedback = {
            "step": step,
            "timestamp": time.time(),
            "context": context,
            "errors": [],
            "suggestions": [],
            "confidence": 1.0
        }
        
        # Vérifications basiques
        if len(step) < 10:
            feedback["errors"].append("Pas de raisonnement trop court")
            feedback["confidence"] *= 0.8
        
        if "gap" not in step.lower() and "lacune" not in step.lower():
            feedback["suggestions"].append("Considérer l'ajout d'une référence explicite aux lacunes")
            feedback["confidence"] *= 0.9
        
        # Détection de patterns d'erreur récurrents
        step_hash = hashlib.md5(step.encode()).hexdigest()[:8]
        if step_hash in self.error_patterns:
            self.error_patterns[step_hash] += 1
            if self.error_patterns[step_hash] > 3:
                feedback["errors"].append("Pattern de raisonnement récurrent détecté")
                feedback["confidence"] *= 0.7
        else:
            self.error_patterns[step_hash] = 1
        
        self.feedback_history.append(feedback)
        return feedback
    
    def get_improvement_suggestions(self) -> List[str]:
        """Génère des suggestions d'amélioration basées sur l'historique."""
        suggestions = []
        
        # Analyse des erreurs fréquentes
        frequent_errors = {}
        for feedback in self.feedback_history[-100:]:  # Derniers 100 feedbacks
            for error in feedback["errors"]:
                frequent_errors[error] = frequent_errors.get(error, 0) + 1
        
        for error, count in frequent_errors.items():
            if count > 5:
                suggestions.append(f"Corriger l'erreur récurrente: {error}")
        
        return suggestions


class KnowledgeGap:
    """Représente une lacune de connaissance identifiée."""
    
    def __init__(self, gap_type: str, concept_id: str, description: str, 
                 severity: float = 0.5, metadata: Optional[Dict[str, Any]] = None,
                 reasoning_trajectory: Optional[List[str]] = None):
        self.gap_type = gap_type
        self.concept_id = concept_id
        self.description = description
        self.severity = severity  # 0.0 = faible, 1.0 = critique
        self.metadata = metadata or {}
        self.reasoning_trajectory = reasoning_trajectory or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la lacune en dictionnaire."""
        return {
            "gap_type": self.gap_type,
            "concept_id": self.concept_id,
            "description": self.description,
            "severity": self.severity,
            "metadata": self.metadata,
            "reasoning_trajectory": self.reasoning_trajectory
        }


class SeleneEvolved:
    """Module de détection de lacunes de connaissance avec capacités d'évolution."""
    
    def __init__(self, nous_instance: Optional[Nous] = None):
        self.nous = nous_instance or Nous()
        self.bus = GlyphBus()
        
        # Configuration des seuils de détection
        self.min_prompt_length = 10
        self.max_prompt_length = 1000
        self.required_fields = ["concept_id", "natural_prompt", "concept_type", "source"]
        
        # Composants d'évolution
        self.experience_archive = ExperienceArchive()
        self.evolution_engine = EvolutionEngine()
        self.introspective_layer = IntrospectiveLayer()
        
        # Initialisation de la variante de base
        self._initialize_base_algorithm()
    
    def _initialize_base_algorithm(self):
        """Initialise l'algorithme de base pour l'évolution."""
        base_algorithm = """
def detect_short_prompt_gaps(self, concepts):
    gaps = []
    for concept in concepts:
        if len(concept.natural_prompt) < self.min_prompt_length:
            gaps.append(KnowledgeGap(
                gap_type="SHORT_PROMPT",
                concept_id=concept.concept_id,
                description=f"Le prompt naturel est trop court ({len(concept.natural_prompt)} caractères)",
                severity=0.8
            ))
    return gaps
        """
        
        self.base_variant = self.evolution_engine.create_initial_variant(base_algorithm)
    
    def detect_gaps(self) -> List[KnowledgeGap]:
        """Détecte toutes les lacunes de connaissance avec raisonnement introspectif."""
        start_time = time.time()
        reasoning_steps = []
        
        # Étape 1: Récupération des concepts
        step = "Récupération de tous les concepts du blackboard NOUS"
        reasoning_steps.append(step)
        feedback = self.introspective_layer.check_reasoning_step(step, {"action": "get_all_concepts"})
        
        concepts = self.nous.get_all_concepts()
        
        # Étape 2: Application des détecteurs de lacunes
        all_gaps = []
        
        step = "Application des détecteurs de lacunes spécialisés"
        reasoning_steps.append(step)
        feedback = self.introspective_layer.check_reasoning_step(step, {"concept_count": len(concepts)})
        
        # Utilisation de l'expérience passée pour améliorer la détection
        for gap_type in ["SHORT_PROMPT", "MISSING_FIELD", "VAGUE_DESCRIPTION"]:
            best_trajectories = self.experience_archive.get_best_trajectories(gap_type)
            
            if best_trajectories:
                # Utilise la meilleure trajectoire connue
                step = f"Application de la meilleure trajectoire connue pour {gap_type}"
                reasoning_steps.append(step)
                feedback = self.introspective_layer.check_reasoning_step(
                    step, 
                    {"gap_type": gap_type, "best_score": best_trajectories[0].success_score}
                )
        
        # Détection des lacunes avec les méthodes existantes
        all_gaps.extend(self._detect_short_prompt_gaps(concepts, reasoning_steps))
        all_gaps.extend(self._detect_missing_field_gaps(concepts, reasoning_steps))
        all_gaps.extend(self._detect_vague_description_gaps(concepts, reasoning_steps))
        
        # Étape 3: Évaluation et amélioration
        execution_time = time.time() - start_time
        
        # Création d'une trajectoire de raisonnement
        trajectory = ReasoningTrajectory(
            trajectory_id=self._generate_trajectory_id(),
            gap_type="GENERAL_DETECTION",
            reasoning_steps=reasoning_steps,
            success_score=self._calculate_success_score(all_gaps),
            execution_time=execution_time,
            metadata={"gaps_found": len(all_gaps), "concepts_analyzed": len(concepts)},
            timestamp=time.time()
        )
        
        self.experience_archive.add_trajectory(trajectory)
        
        # Publication des événements
        for gap in all_gaps:
            gap.reasoning_trajectory = reasoning_steps
            self.bus.publish("knowledge_gap", gap.to_dict())
        
        # Déclenchement de l'évolution si nécessaire
        self._trigger_evolution_if_needed()
        
        return all_gaps
    
    def _detect_short_prompt_gaps(self, concepts: List[Concept], reasoning_steps: List[str]) -> List[KnowledgeGap]:
        """Détecte les lacunes de prompts trop courts."""
        step = "Détection des prompts trop courts"
        reasoning_steps.append(step)
        
        gaps = []
        for concept in concepts:
            if len(concept.natural_prompt) < self.min_prompt_length:
                gaps.append(KnowledgeGap(
                    gap_type="SHORT_PROMPT",
                    concept_id=concept.concept_id,
                    description=f"Le prompt naturel est trop court ({len(concept.natural_prompt)} caractères)",
                    severity=0.8,
                    reasoning_trajectory=reasoning_steps.copy()
                ))
        
        return gaps
    
    def _detect_missing_field_gaps(self, concepts: List[Concept], reasoning_steps: List[str]) -> List[KnowledgeGap]:
        """Détecte les lacunes de champs manquants."""
        step = "Détection des champs manquants"
        reasoning_steps.append(step)
        
        gaps = []
        for concept in concepts:
            missing_fields = []
            
            if not hasattr(concept, 'resonance') or concept.resonance is None:
                missing_fields.append('resonance')
            
            if not hasattr(concept, 'weight') or concept.weight is None:
                missing_fields.append('weight')
            
            if missing_fields:
                gaps.append(KnowledgeGap(
                    gap_type="MISSING_FIELD",
                    concept_id=concept.concept_id,
                    description=f"Champs manquants: {', '.join(missing_fields)}",
                    severity=0.6,
                    metadata={"missing_fields": missing_fields},
                    reasoning_trajectory=reasoning_steps.copy()
                ))
        
        return gaps
    
    def _detect_vague_description_gaps(self, concepts: List[Concept], reasoning_steps: List[str]) -> List[KnowledgeGap]:
        """Détecte les lacunes de descriptions vagues."""
        step = "Détection des descriptions vagues"
        reasoning_steps.append(step)
        
        gaps = []
        vague_indicators = ["vague", "général", "basique", "simple", "etc.", "..."]
        
        for concept in concepts:
            prompt = concept.natural_prompt.lower()
            vague_count = sum(1 for indicator in vague_indicators if indicator in prompt)
            
            if vague_count > 0 or len(prompt.split()) < 5:
                gaps.append(KnowledgeGap(
                    gap_type="VAGUE_DESCRIPTION",
                    concept_id=concept.concept_id,
                    description=f"Description potentiellement vague (indicateurs: {vague_count})",
                    severity=0.4,
                    metadata={"vague_indicators": vague_count, "word_count": len(prompt.split())},
                    reasoning_trajectory=reasoning_steps.copy()
                ))
        
        return gaps
    
    def _calculate_success_score(self, gaps: List[KnowledgeGap]) -> float:
        """Calcule un score de succès pour une trajectoire de raisonnement."""
        if not gaps:
            return 0.5  # Aucune lacune trouvée peut être bon ou mauvais
        
        # Score basé sur la diversité et la qualité des lacunes détectées
        gap_types = set(gap.gap_type for gap in gaps)
        diversity_score = len(gap_types) / 3.0  # 3 types maximum
        
        avg_severity = sum(gap.severity for gap in gaps) / len(gaps)
        
        return min(1.0, (diversity_score + avg_severity) / 2.0)
    
    def _generate_trajectory_id(self) -> str:
        """Génère un ID unique pour une trajectoire."""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]
    
    def _trigger_evolution_if_needed(self):
        """Déclenche l'évolution des algorithmes si nécessaire."""
        # Critères pour déclencher l'évolution
        recent_trajectories = [
            t for t in self.experience_archive.trajectories.values()
            if time.time() - t.timestamp < 3600  # Dernière heure
        ]
        
        if len(recent_trajectories) >= 10:
            avg_score = sum(t.success_score for t in recent_trajectories) / len(recent_trajectories)
            
            if avg_score < 0.7:  # Performance insuffisante
                self._evolve_algorithms()
    
    def _evolve_algorithms(self):
        """Fait évoluer les algorithmes de détection."""
        # Sélection du meilleur variant actuel
        best_variant = max(
            self.evolution_engine.variants.values(),
            key=lambda v: v.performance_metrics.get("f1_score", 0.0),
            default=self.base_variant
        )
        
        # Création de nouvelles variantes
        for _ in range(3):  # Génère 3 variantes
            new_variant = self.evolution_engine.evolve_variant(best_variant)
            
            # Test de la nouvelle variante (simulation)
            test_concepts = self.nous.get_all_concepts()[:10]  # Test sur un échantillon
            metrics = self.evolution_engine.benchmark_variant(new_variant, test_concepts)
            
            # Publication de l'événement d'évolution
            self.bus.publish("algorithm_evolved", {
                "variant_id": new_variant.variant_id,
                "parent_id": new_variant.parent_id,
                "generation": new_variant.generation,
                "performance_metrics": metrics
            })
    
    def get_evolution_status(self) -> Dict[str, Any]:
        """Retourne le statut de l'évolution des algorithmes."""
        return {
            "current_generation": self.evolution_engine.current_generation,
            "total_variants": len(self.evolution_engine.variants),
            "total_trajectories": len(self.experience_archive.trajectories),
            "best_variant_performance": max(
                (v.performance_metrics.get("f1_score", 0.0) for v in self.evolution_engine.variants.values()),
                default=0.0
            ),
            "introspective_feedback_count": len(self.introspective_layer.feedback_history)
        }

