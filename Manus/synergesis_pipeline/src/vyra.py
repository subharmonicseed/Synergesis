"""Synergesis – Vyra v1
=====================
Module de génération de suggestions créatives basées sur les lacunes détectées par Selene.

Vyra analyse les lacunes de connaissance identifiées par Selene et propose
des suggestions créatives pour enrichir et améliorer les concepts dans NOUS.
"""

from typing import List, Dict, Any, Optional
from nous import Nous, Concept
from selene import Selene, KnowledgeGap
from glyph_bus import GlyphBus


class CreativeSuggestion:
    """Représente une suggestion créative pour améliorer un concept."""
    
    def __init__(self, suggestion_type: str, concept_id: str, title: str, 
                 description: str, priority: float = 0.5, 
                 metadata: Optional[Dict[str, Any]] = None):
        self.suggestion_type = suggestion_type
        self.concept_id = concept_id
        self.title = title
        self.description = description
        self.priority = priority  # 0.0 = faible, 1.0 = haute
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la suggestion en dictionnaire."""
        return {
            "suggestion_type": self.suggestion_type,
            "concept_id": self.concept_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "metadata": self.metadata
        }


class Vyra:
    """Module de génération de suggestions créatives."""
    
    def __init__(self, nous_instance: Optional[Nous] = None, selene_instance: Optional[Selene] = None):
        self.nous = nous_instance or Nous()
        self.selene = selene_instance or Selene(self.nous)
        self.bus = GlyphBus()
        
        # Mapping des types de lacunes vers les générateurs de suggestions
        self.gap_handlers = {
            "SHORT_PROMPT": self._generate_enrich_prompt_suggestions,
            "MISSING_FIELD": self._generate_complete_field_suggestions,
            "VAGUE_DESCRIPTION": self._generate_clarify_description_suggestions,
            "MISSING_CONTEXT": self._generate_add_context_suggestions
        }
    
    def generate_suggestions(self, gaps: Optional[List[KnowledgeGap]] = None) -> List[CreativeSuggestion]:
        """Génère des suggestions créatives basées sur les lacunes détectées."""
        if gaps is None:
            gaps = self.selene.detect_gaps()
        
        suggestions = []
        
        for gap in gaps:
            if gap.gap_type in self.gap_handlers:
                handler = self.gap_handlers[gap.gap_type]
                gap_suggestions = handler(gap)
                suggestions.extend(gap_suggestions)
        
        # Publier les suggestions générées
        for suggestion in suggestions:
            self.bus.publish("creative_suggestion", suggestion.to_dict())
        
        return suggestions
    
    def _generate_enrich_prompt_suggestions(self, gap: KnowledgeGap) -> List[CreativeSuggestion]:
        """Génère des suggestions pour enrichir un prompt trop court."""
        suggestions = []
        
        concept = self.nous.get_concept_by_id(gap.concept_id)
        if not concept:
            return suggestions
        
        # Suggestion principale: enrichir le concept
        suggestion = CreativeSuggestion(
            suggestion_type="ENRICH_CONCEPT_PROMPT",
            concept_id=gap.concept_id,
            title="Enrichir la description du concept",
            description=f"Le concept '{concept.concept_id}' a une description très courte. "
                       f"Considérez ajouter plus de détails sur sa définition, ses applications, "
                       f"ses relations avec d'autres concepts, ou des exemples concrets.",
            priority=0.8,
            metadata={
                "current_length": len(concept.natural_prompt),
                "suggested_min_length": 50,
                "enhancement_areas": ["définition", "applications", "exemples", "relations"]
            }
        )
        suggestions.append(suggestion)
        
        # Suggestion secondaire: rechercher des sources
        suggestion = CreativeSuggestion(
            suggestion_type="RESEARCH_SOURCES",
            concept_id=gap.concept_id,
            title="Rechercher des sources supplémentaires",
            description=f"Recherchez des sources académiques, articles ou documentation "
                       f"pour enrichir le concept '{concept.concept_id}' avec des informations "
                       f"plus détaillées et des références fiables.",
            priority=0.6,
            metadata={
                "search_keywords": [concept.concept_id, concept.concept_type],
                "source_types": ["académique", "documentation", "articles"]
            }
        )
        suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_complete_field_suggestions(self, gap: KnowledgeGap) -> List[CreativeSuggestion]:
        """Génère des suggestions pour compléter les champs manquants."""
        suggestions = []
        
        missing_field = gap.metadata.get("missing_field", "unknown")
        
        suggestion = CreativeSuggestion(
            suggestion_type="COMPLETE_MISSING_FIELD",
            concept_id=gap.concept_id,
            title=f"Compléter le champ '{missing_field}'",
            description=f"Le champ '{missing_field}' est manquant ou vide pour le concept "
                       f"'{gap.concept_id}'. Ce champ est essentiel pour une description "
                       f"complète du concept.",
            priority=0.9,
            metadata={
                "missing_field": missing_field,
                "field_importance": "high" if missing_field in ["natural_prompt", "concept_type"] else "medium"
            }
        )
        suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_clarify_description_suggestions(self, gap: KnowledgeGap) -> List[CreativeSuggestion]:
        """Génère des suggestions pour clarifier les descriptions vagues."""
        suggestions = []
        
        vague_keyword = gap.metadata.get("vague_keyword", "terme vague")
        
        suggestion = CreativeSuggestion(
            suggestion_type="CLARIFY_VAGUE_DESCRIPTION",
            concept_id=gap.concept_id,
            title="Clarifier la description vague",
            description=f"La description du concept '{gap.concept_id}' contient des termes "
                       f"vagues comme '{vague_keyword}'. Remplacez ces termes par des "
                       f"descriptions plus précises et spécifiques.",
            priority=0.7,
            metadata={
                "vague_keyword": vague_keyword,
                "clarification_suggestions": [
                    "Utilisez des termes techniques précis",
                    "Ajoutez des exemples concrets",
                    "Définissez les concepts ambigus"
                ]
            }
        )
        suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_add_context_suggestions(self, gap: KnowledgeGap) -> List[CreativeSuggestion]:
        """Génère des suggestions pour ajouter du contexte."""
        suggestions = []
        
        suggestion = CreativeSuggestion(
            suggestion_type="ADD_CONTEXTUAL_RELATIONS",
            concept_id=gap.concept_id,
            title="Ajouter des relations contextuelles",
            description=f"Le concept '{gap.concept_id}' semble isolé. Ajoutez des références "
                       f"à d'autres concepts, des relations hiérarchiques, ou des liens "
                       f"avec des domaines connexes pour enrichir le contexte.",
            priority=0.6,
            metadata={
                "relation_types": ["hiérarchique", "associative", "causale", "temporelle"],
                "context_areas": ["domaine d'application", "concepts liés", "historique"]
            }
        )
        suggestions.append(suggestion)
        
        return suggestions
    
    def get_suggestions_by_type(self, suggestion_type: str) -> List[CreativeSuggestion]:
        """Récupère les suggestions d'un type spécifique."""
        all_suggestions = self.generate_suggestions()
        return [suggestion for suggestion in all_suggestions if suggestion.suggestion_type == suggestion_type]
    
    def get_suggestions_by_priority(self, min_priority: float = 0.0, max_priority: float = 1.0) -> List[CreativeSuggestion]:
        """Récupère les suggestions dans une plage de priorité."""
        all_suggestions = self.generate_suggestions()
        return [suggestion for suggestion in all_suggestions if min_priority <= suggestion.priority <= max_priority]
    
    def get_concept_suggestions(self, concept_id: str) -> List[CreativeSuggestion]:
        """Récupère toutes les suggestions pour un concept spécifique."""
        all_suggestions = self.generate_suggestions()
        return [suggestion for suggestion in all_suggestions if suggestion.concept_id == concept_id]
    
    def apply_suggestion(self, suggestion: CreativeSuggestion, new_content: str) -> bool:
        """Applique une suggestion en mettant à jour le concept."""
        try:
            concept = self.nous.get_concept_by_id(suggestion.concept_id)
            if not concept:
                return False
            
            # Mettre à jour le concept selon le type de suggestion
            if suggestion.suggestion_type == "ENRICH_CONCEPT_PROMPT":
                concept.natural_prompt = new_content
            elif suggestion.suggestion_type == "COMPLETE_MISSING_FIELD":
                # Logique spécifique selon le champ manquant
                missing_field = suggestion.metadata.get("missing_field")
                if missing_field == "natural_prompt":
                    concept.natural_prompt = new_content
                elif missing_field == "concept_type":
                    concept.concept_type = new_content
                elif missing_field == "source":
                    concept.source = new_content
            elif suggestion.suggestion_type == "CLARIFY_VAGUE_DESCRIPTION":
                concept.natural_prompt = new_content
            
            # Sauvegarder les modifications
            self.nous.update_concept(concept)
            
            # Publier l'application de la suggestion
            self.bus.publish("suggestion_applied", {
                "suggestion": suggestion.to_dict(),
                "concept_id": concept.concept_id,
                "new_content": new_content
            })
            
            return True
        
        except Exception as e:
            print(f"Erreur lors de l'application de la suggestion: {e}")
            return False


if __name__ == "__main__":
    # Exemple d'utilisation
    nous = Nous()
    selene = Selene(nous)
    vyra = Vyra(nous, selene)
    
    # Ajouter un concept avec des lacunes
    concept_test = Concept(
        concept_id="concept_test_vyra",
        natural_prompt="Court",  # Prompt trop court
        concept_type="TEST",
        source="Test"
    )
    nous.add_concept(concept_test)
    
    # Générer des suggestions
    suggestions = vyra.generate_suggestions()
    
    print(f"Nombre de suggestions générées: {len(suggestions)}")
    for suggestion in suggestions:
        print(f"- {suggestion.suggestion_type}: {suggestion.title}")
        print(f"  Description: {suggestion.description}")
        print(f"  Priorité: {suggestion.priority}")
        print()
    
    # Appliquer une suggestion
    if suggestions:
        first_suggestion = suggestions[0]
        success = vyra.apply_suggestion(
            first_suggestion, 
            "Ceci est une description enrichie du concept de test avec plus de détails et d'exemples."
        )
        print(f"Application de la suggestion: {'Réussie' if success else 'Échouée'}")

