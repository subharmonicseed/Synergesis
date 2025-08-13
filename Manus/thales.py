"""Synergesis – Thales v2
========================
Module de détection d'incohérences logiques dans le blackboard NOUS.

Thales v2 intègre la résonance et le poids des concepts pour une analyse
plus sophistiquée des incohérences et contradictions logiques.
"""

import requests
from typing import List, Dict, Any, Optional, Tuple
from nous import Nous, Concept
from glyph_bus import GlyphBus


class LogicalInconsistency:
    """Représente une incohérence logique détectée."""
    
    def __init__(self, inconsistency_type: str, concept_ids: List[str], 
                 description: str, severity: float = 0.5, 
                 metadata: Optional[Dict[str, Any]] = None):
        self.inconsistency_type = inconsistency_type
        self.concept_ids = concept_ids
        self.description = description
        self.severity = severity  # 0.0 = faible, 1.0 = critique
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'incohérence en dictionnaire."""
        return {
            "type": self.inconsistency_type,
            "concept_ids": self.concept_ids,
            "description": self.description,
            "severity": self.severity,
            "metadata": self.metadata
        }


class Thales:
    """Module de détection d'incohérences logiques avec support de la résonance et du poids."""
    
    def __init__(self, nous_instance: Optional[Nous] = None, nous_api_url: Optional[str] = None):
        self.nous = nous_instance
        self.nous_api_url = nous_api_url
        self.bus = GlyphBus()
        
        # Configuration des seuils
        self.resonance_threshold = 0.1  # Seuil de différence de résonance
        self.weight_threshold = 0.1     # Seuil de différence de poids
    
    def _get_concepts_from_api(self) -> List[Dict[str, Any]]:
        """Récupère les concepts depuis l'API NOUS."""
        if not self.nous_api_url:
            return []
        
        try:
            headers = {"Authorization": "Bearer synergesis_nous_token_2025"}
            response = requests.get(f"{self.nous_api_url}/concepts", headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des concepts depuis NOUS: {e}")
            return []
    
    def _get_concepts(self) -> List[Concept]:
        """Récupère les concepts depuis NOUS (local ou API)."""
        if self.nous_api_url:
            # Utiliser l'API
            concepts_data = self._get_concepts_from_api()
            concepts = []
            for data in concepts_data:
                concept = Concept(
                    id=data.get("id"),
                    concept_id=data["concept_id"],
                    natural_prompt=data["natural_prompt"],
                    concept_type=data["concept_type"],
                    source=data["source"],
                    timestamp=data.get("timestamp", 0.0),
                    resonance=data.get("resonance"),
                    weight=data.get("weight")
                )
                concepts.append(concept)
            return concepts
        elif self.nous:
            # Utiliser l'instance locale
            return self.nous.get_all_concepts()
        else:
            return []
    
    def check_simple_contradictions(self) -> List[LogicalInconsistency]:
        """Détecte les contradictions simples (même concept_id, descriptions différentes)."""
        inconsistencies = []
        concepts = self._get_concepts()
        
        # Grouper les concepts par concept_id
        concept_groups = {}
        for concept in concepts:
            if concept.concept_id not in concept_groups:
                concept_groups[concept.concept_id] = []
            concept_groups[concept.concept_id].append(concept)
        
        # Vérifier les contradictions dans chaque groupe
        for concept_id, group_concepts in concept_groups.items():
            if len(group_concepts) > 1:
                # Vérifier les différences de description
                descriptions = set()
                types = set()
                
                for concept in group_concepts:
                    descriptions.add(concept.natural_prompt)
                    types.add(concept.concept_type)
                
                # Contradiction si descriptions ou types différents
                if len(descriptions) > 1 or len(types) > 1:
                    # Calculer la sévérité basée sur la résonance et le poids
                    severity = self._calculate_contradiction_severity(group_concepts)
                    
                    inconsistency = LogicalInconsistency(
                        inconsistency_type="simple_contradiction",
                        concept_ids=[concept_id],
                        description=f"Le concept '{concept_id}' a des descriptions ou types contradictoires",
                        severity=severity,
                        metadata={
                            "descriptions": list(descriptions),
                            "types": list(types),
                            "concept_count": len(group_concepts),
                            "resonance_analysis": self._analyze_resonance_weight(group_concepts)
                        }
                    )
                    inconsistencies.append(inconsistency)
        
        return inconsistencies
    
    def _calculate_contradiction_severity(self, concepts: List[Concept]) -> float:
        """Calcule la sévérité d'une contradiction basée sur la résonance et le poids."""
        if not concepts:
            return 0.5
        
        # Récupérer les valeurs de résonance et de poids
        resonances = [c.resonance for c in concepts if c.resonance is not None]
        weights = [c.weight for c in concepts if c.weight is not None]
        
        if not resonances and not weights:
            return 0.5  # Sévérité par défaut
        
        severity = 0.5
        
        # Plus la résonance est élevée, plus la contradiction est sévère
        if resonances:
            max_resonance = max(resonances)
            severity += max_resonance * 0.3
        
        # Plus le poids est élevé, plus la contradiction est sévère
        if weights:
            max_weight = max(weights)
            severity += max_weight * 0.2
        
        return min(severity, 1.0)
    
    def _analyze_resonance_weight(self, concepts: List[Concept]) -> Dict[str, Any]:
        """Analyse la résonance et le poids des concepts en contradiction."""
        resonances = [c.resonance for c in concepts if c.resonance is not None]
        weights = [c.weight for c in concepts if c.weight is not None]
        
        analysis = {
            "resonance_values": resonances,
            "weight_values": weights,
            "resonance_variance": 0.0,
            "weight_variance": 0.0
        }
        
        if len(resonances) > 1:
            mean_resonance = sum(resonances) / len(resonances)
            analysis["resonance_variance"] = sum((r - mean_resonance) ** 2 for r in resonances) / len(resonances)
        
        if len(weights) > 1:
            mean_weight = sum(weights) / len(weights)
            analysis["weight_variance"] = sum((w - mean_weight) ** 2 for w in weights) / len(weights)
        
        return analysis
    
    def check_deductive_cycles(self) -> List[LogicalInconsistency]:
        """Détecte les cycles déductifs (placeholder pour implémentation future)."""
        # TODO: Implémenter la détection de cycles déductifs
        # Cette fonctionnalité nécessiterait une représentation des relations logiques
        # entre les concepts, ce qui n'est pas encore disponible dans le modèle actuel.
        return []
    
    def check_resonance_inconsistencies(self) -> List[LogicalInconsistency]:
        """Détecte les incohérences basées sur la résonance."""
        inconsistencies = []
        concepts = self._get_concepts()
        
        # Grouper les concepts par type
        type_groups = {}
        for concept in concepts:
            if concept.concept_type not in type_groups:
                type_groups[concept.concept_type] = []
            type_groups[concept.concept_type].append(concept)
        
        # Vérifier les incohérences de résonance dans chaque type
        for concept_type, group_concepts in type_groups.items():
            if len(group_concepts) > 1:
                resonances = [(c.concept_id, c.resonance) for c in group_concepts if c.resonance is not None]
                
                if len(resonances) > 1:
                    # Détecter les écarts importants de résonance
                    resonance_values = [r[1] for r in resonances]
                    min_resonance = min(resonance_values)
                    max_resonance = max(resonance_values)
                    
                    if max_resonance - min_resonance > self.resonance_threshold:
                        inconsistency = LogicalInconsistency(
                            inconsistency_type="resonance_inconsistency",
                            concept_ids=[r[0] for r in resonances],
                            description=f"Écart important de résonance dans le type '{concept_type}' "
                                       f"(min: {min_resonance:.2f}, max: {max_resonance:.2f})",
                            severity=0.6,
                            metadata={
                                "concept_type": concept_type,
                                "resonance_range": (min_resonance, max_resonance),
                                "resonance_gap": max_resonance - min_resonance
                            }
                        )
                        inconsistencies.append(inconsistency)
        
        return inconsistencies
    
    def check_weight_inconsistencies(self) -> List[LogicalInconsistency]:
        """Détecte les incohérences basées sur le poids."""
        inconsistencies = []
        concepts = self._get_concepts()
        
        # Grouper les concepts par source
        source_groups = {}
        for concept in concepts:
            if concept.source not in source_groups:
                source_groups[concept.source] = []
            source_groups[concept.source].append(concept)
        
        # Vérifier les incohérences de poids dans chaque source
        for source, group_concepts in source_groups.items():
            if len(group_concepts) > 1:
                weights = [(c.concept_id, c.weight) for c in group_concepts if c.weight is not None]
                
                if len(weights) > 1:
                    # Détecter les écarts importants de poids
                    weight_values = [w[1] for w in weights]
                    min_weight = min(weight_values)
                    max_weight = max(weight_values)
                    
                    if max_weight - min_weight > self.weight_threshold:
                        inconsistency = LogicalInconsistency(
                            inconsistency_type="weight_inconsistency",
                            concept_ids=[w[0] for w in weights],
                            description=f"Écart important de poids dans la source '{source}' "
                                       f"(min: {min_weight:.2f}, max: {max_weight:.2f})",
                            severity=0.5,
                            metadata={
                                "source": source,
                                "weight_range": (min_weight, max_weight),
                                "weight_gap": max_weight - min_weight
                            }
                        )
                        inconsistencies.append(inconsistency)
        
        return inconsistencies
    
    def run_all_checks(self) -> List[LogicalInconsistency]:
        """Exécute toutes les vérifications d'incohérences."""
        all_inconsistencies = []
        
        # Exécuter toutes les vérifications
        all_inconsistencies.extend(self.check_simple_contradictions())
        all_inconsistencies.extend(self.check_deductive_cycles())
        all_inconsistencies.extend(self.check_resonance_inconsistencies())
        all_inconsistencies.extend(self.check_weight_inconsistencies())
        
        # Publier les incohérences détectées
        for inconsistency in all_inconsistencies:
            self.bus.publish("logical_inconsistency", inconsistency.to_dict())
        
        return all_inconsistencies
    
    def get_inconsistencies_by_type(self, inconsistency_type: str) -> List[LogicalInconsistency]:
        """Récupère les incohérences d'un type spécifique."""
        all_inconsistencies = self.run_all_checks()
        return [inc for inc in all_inconsistencies if inc.inconsistency_type == inconsistency_type]
    
    def get_inconsistencies_by_severity(self, min_severity: float = 0.0, max_severity: float = 1.0) -> List[LogicalInconsistency]:
        """Récupère les incohérences dans une plage de sévérité."""
        all_inconsistencies = self.run_all_checks()
        return [inc for inc in all_inconsistencies if min_severity <= inc.severity <= max_severity]


if __name__ == "__main__":
    # Exemple d'utilisation
    nous = Nous()
    thales = Thales(nous)
    
    # Ajouter des concepts avec des contradictions intentionnelles
    concept_1a = Concept(
        concept_id="concept_contradiction",
        natural_prompt="Première description",
        concept_type="TYPE1",
        source="Source1",
        resonance=0.8,
        weight=0.7
    )
    
    concept_1b = Concept(
        concept_id="concept_contradiction",
        natural_prompt="Deuxième description différente",
        concept_type="TYPE1",
        source="Source1",
        resonance=0.3,
        weight=0.9
    )
    
    nous.add_concept(concept_1a)
    nous.add_concept(concept_1b)
    
    # Détecter les incohérences
    inconsistencies = thales.run_all_checks()
    
    print(f"Nombre d'incohérences détectées: {len(inconsistencies)}")
    for inconsistency in inconsistencies:
        print(f"- {inconsistency.inconsistency_type}: {inconsistency.description}")
        print(f"  Sévérité: {inconsistency.severity}")
        print(f"  Concepts impliqués: {inconsistency.concept_ids}")
        print()

