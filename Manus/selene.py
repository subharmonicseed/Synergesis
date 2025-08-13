"""Synergesis – Selene v1
=======================
Module de détection de lacunes de connaissance dans le blackboard NOUS.

Selene analyse les concepts stockés dans NOUS et identifie les lacunes
potentielles qui pourraient nécessiter une attention particulière ou
des enrichissements supplémentaires.
"""

from typing import List, Dict, Any, Optional
from nous_enhanced import NousEnhanced as Nous, Concept
from glyph_bus import GlyphBus


class KnowledgeGap:
    """Représente une lacune de connaissance identifiée."""
    
    def __init__(self, gap_type: str, concept_id: str, description: str, 
                 severity: float = 0.5, metadata: Optional[Dict[str, Any]] = None):
        self.gap_type = gap_type
        self.concept_id = concept_id
        self.description = description
        self.severity = severity  # 0.0 = faible, 1.0 = critique
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la lacune en dictionnaire."""
        return {
            "gap_type": self.gap_type,
            "concept_id": self.concept_id,
            "description": self.description,
            "severity": self.severity,
            "metadata": self.metadata
        }


class Selene:
    """Module de détection de lacunes de connaissance."""
    
    def __init__(self, nous_instance: Optional[Nous] = None):
        self.nous = nous_instance or Nous()
        self.bus = GlyphBus()
        
        # Configuration des seuils de détection
        self.min_prompt_length = 10
        self.max_prompt_length = 1000
        self.required_fields = ["concept_id", "natural_prompt", "concept_type", "source"]
    
    def detect_gaps(self) -> List[KnowledgeGap]:
        """Détecte toutes les lacunes de connaissance."""
        gaps = []
        
        # Récupérer tous les concepts
        concepts = self.nous.get_all_concepts()
        
        for concept in concepts:
            # Vérifier les différents types de lacunes
            gaps.extend(self._check_short_prompts(concept))
            gaps.extend(self._check_missing_fields(concept))
            gaps.extend(self._check_vague_descriptions(concept))
            gaps.extend(self._check_missing_context(concept))
        
        # Publier les lacunes détectées
        for gap in gaps:
            self.bus.publish("knowledge_gap", gap.to_dict())
        
        return gaps
    
    def _check_short_prompts(self, concept: Concept) -> List[KnowledgeGap]:
        """Détecte les prompts trop courts."""
        gaps = []
        
        if len(concept.natural_prompt) < self.min_prompt_length:
            gap = KnowledgeGap(
                gap_type="SHORT_PROMPT",
                concept_id=concept.concept_id,
                description=f"Le prompt naturel est trop court ({len(concept.natural_prompt)} caractères)",
                severity=0.7,
                metadata={"current_length": len(concept.natural_prompt), "min_length": self.min_prompt_length}
            )
            gaps.append(gap)
        
        return gaps
    
    def _check_missing_fields(self, concept: Concept) -> List[KnowledgeGap]:
        """Détecte les champs manquants ou vides."""
        gaps = []
        
        concept_dict = concept.dict()
        for field in self.required_fields:
            if field not in concept_dict or not concept_dict[field] or concept_dict[field].strip() == "":
                gap = KnowledgeGap(
                    gap_type="MISSING_FIELD",
                    concept_id=concept.concept_id,
                    description=f"Le champ '{field}' est manquant ou vide",
                    severity=0.8,
                    metadata={"missing_field": field}
                )
                gaps.append(gap)
        
        return gaps
    
    def _check_vague_descriptions(self, concept: Concept) -> List[KnowledgeGap]:
        """Détecte les descriptions vagues ou génériques."""
        gaps = []
        
        # Mots-clés indiquant une description vague
        vague_keywords = ["chose", "truc", "machin", "quelque chose", "etc", "...", "vague", "général"]
        
        prompt_lower = concept.natural_prompt.lower()
        for keyword in vague_keywords:
            if keyword in prompt_lower:
                gap = KnowledgeGap(
                    gap_type="VAGUE_DESCRIPTION",
                    concept_id=concept.concept_id,
                    description=f"La description contient des termes vagues: '{keyword}'",
                    severity=0.6,
                    metadata={"vague_keyword": keyword}
                )
                gaps.append(gap)
                break  # Une seule détection par concept
        
        return gaps
    
    def _check_missing_context(self, concept: Concept) -> List[KnowledgeGap]:
        """Détecte le manque de contexte ou de relations."""
        gaps = []
        
        # Vérifier si le concept semble isolé (pas de références à d'autres concepts)
        if not self._has_contextual_references(concept):
            gap = KnowledgeGap(
                gap_type="MISSING_CONTEXT",
                concept_id=concept.concept_id,
                description="Le concept semble isolé, sans références contextuelles",
                severity=0.5,
                metadata={"isolation_detected": True}
            )
            gaps.append(gap)
        
        return gaps
    
    def _has_contextual_references(self, concept: Concept) -> bool:
        """Vérifie si un concept a des références contextuelles."""
        # Rechercher des mots-clés indiquant des relations
        context_keywords = ["lié à", "en relation avec", "similaire à", "différent de", "basé sur", "dérivé de"]
        
        prompt_lower = concept.natural_prompt.lower()
        return any(keyword in prompt_lower for keyword in context_keywords)
    
    def get_gaps_by_type(self, gap_type: str) -> List[KnowledgeGap]:
        """Récupère les lacunes d'un type spécifique."""
        all_gaps = self.detect_gaps()
        return [gap for gap in all_gaps if gap.gap_type == gap_type]
    
    def get_gaps_by_severity(self, min_severity: float = 0.0, max_severity: float = 1.0) -> List[KnowledgeGap]:
        """Récupère les lacunes dans une plage de sévérité."""
        all_gaps = self.detect_gaps()
        return [gap for gap in all_gaps if min_severity <= gap.severity <= max_severity]
    
    def get_concept_gaps(self, concept_id: str) -> List[KnowledgeGap]:
        """Récupère toutes les lacunes pour un concept spécifique."""
        all_gaps = self.detect_gaps()
        return [gap for gap in all_gaps if gap.concept_id == concept_id]


if __name__ == "__main__":
    # Exemple d'utilisation
    nous = Nous()
    selene = Selene(nous)
    
    # Ajouter des concepts de test avec des lacunes intentionnelles
    concept_1 = Concept(
        concept_id="concept_test_1",
        natural_prompt="Court",  # Prompt trop court
        concept_type="TEST",
        source="Test"
    )
    
    concept_2 = Concept(
        concept_id="concept_test_2",
        natural_prompt="Ceci est un concept avec une description vague et etc...",  # Description vague
        concept_type="TEST",
        source="Test"
    )
    
    concept_3 = Concept(
        concept_id="concept_test_3",
        natural_prompt="",  # Champ vide
        concept_type="TEST",
        source="Test"
    )
    
    # Ajouter les concepts
    nous.add_concept(concept_1)
    nous.add_concept(concept_2)
    nous.add_concept(concept_3)
    
    # Détecter les lacunes
    gaps = selene.detect_gaps()
    
    print(f"Nombre de lacunes détectées: {len(gaps)}")
    for gap in gaps:
        print(f"- {gap.gap_type}: {gap.description} (sévérité: {gap.severity})")

