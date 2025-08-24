#!/usr/bin/env python3
# File: schemas.py
# Description: Schémas Pydantic pour la validation des données du pipeline Synergesis

from enum import Enum
from typing import List, Dict, Optional, Any, Union, Literal
from datetime import datetime
import time
import json
import logging
from pydantic import BaseModel, Field, validator, model_validator

# Configuration du logging
logger = logging.getLogger('schemas')


class ConceptType(str, Enum):
    """Types de concepts pour les glyphes."""
    TECHNICALCONCEPT = "TECHNICALCONCEPT"
    PROBLEM = "PROBLEM"
    PROPOSEDSOLUTION = "PROPOSEDSOLUTION"
    POTENTIAL_ACTION = "POTENTIAL_ACTION"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    """Types d'actions pour les glyphes d'action potentielle."""
    CREATE_RELATIONSHIP = "CREATE_RELATIONSHIP"
    CREATE_SOLUTION_NODE = "CREATE_SOLUTION_NODE"
    FIND_AND_CONNECT_ISOLATED = "FIND_AND_CONNECT_ISOLATED"
    ENRICH_HUB_NODE = "ENRICH_HUB_NODE"


class ExecutionStatus(str, Enum):
    """Statuts d'exécution pour les résultats d'action."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    SKIPPED = "skipped"


class GlyphData(BaseModel):
    """
    Modèle de base pour les données de glyphe.
    Définit la structure commune à tous les types de glyphes.
    """
    id: str = Field(..., description="Identifiant unique du glyphe")
    concept_type: ConceptType = Field(..., description="Type de concept du glyphe")
    natural_prompt: Optional[str] = Field("Description non disponible", description="Description textuelle du glyphe")
    timestamp: Optional[int] = Field(default_factory=lambda: int(time.time()), description="Horodatage de création")
    source: Optional[str] = Field("topology_engine", description="Source du glyphe")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags associés au glyphe")
    
    @validator('id')
    def validate_id_format(cls, v):
        """Valide le format de l'identifiant."""
        if not v or not isinstance(v, str):
            raise ValueError("L'identifiant doit être une chaîne non vide")
        return v
    
    class Config:
        """Configuration du modèle Pydantic."""
        extra = "allow"  # Permet des champs supplémentaires
        validate_assignment = True  # Valide les assignations après l'initialisation
        arbitrary_types_allowed = True  # Permet des types arbitraires


class ActionParameters(BaseModel):
    """
    Paramètres pour les actions potentielles.
    Contient les paramètres spécifiques à chaque type d'action.
    """
    # Paramètres pour CREATE_RELATIONSHIP
    source_glyph_id: Optional[str] = Field(None, description="ID du glyphe source pour une relation")
    target_glyph_id: Optional[str] = Field(None, description="ID du glyphe cible pour une relation ou un enrichissement")
    relationship_type: Optional[str] = Field(None, description="Type de relation à créer")
    
    # Paramètres pour CREATE_SOLUTION_NODE
    problem_glyphs: Optional[List[str]] = Field(None, description="Liste des IDs de glyphes problèmes")
    solution_template: Optional[str] = Field(None, description="Template pour la génération de solution")
    
    # Paramètres pour ENRICH_HUB_NODE
    enrichment_aspects: Optional[List[str]] = Field(None, description="Aspects à enrichir")
    
    class Config:
        """Configuration du modèle Pydantic."""
        extra = "allow"  # Permet des champs supplémentaires


class SourceMetadata(BaseModel):
    """
    Métadonnées sur la source de l'action.
    Contient des informations sur l'origine de l'action potentielle.
    """
    intention_type: Optional[str] = Field(None, description="Type d'intention ayant généré l'action")
    observation_ids: Optional[List[str]] = Field(None, description="IDs des observations liées")
    target_prompt: Optional[str] = Field(None, description="Prompt cible pour l'action")
    
    class Config:
        """Configuration du modèle Pydantic."""
        extra = "allow"  # Permet des champs supplémentaires


class DetailsStructuredJson(BaseModel):
    """
    Structure JSON détaillée pour les actions potentielles.
    Contient les paramètres et métadonnées de l'action.
    """
    action_parameters: ActionParameters = Field(..., description="Paramètres de l'action")
    source_metadata: Optional[SourceMetadata] = Field(None, description="Métadonnées sur la source de l'action")
    expected_impact: Optional[Dict[str, Any]] = Field(None, description="Impact attendu de l'action")
    rollback_procedure: Optional[Dict[str, Any]] = Field(None, description="Procédure de rollback en cas d'échec")
    
    class Config:
        """Configuration du modèle Pydantic."""
        extra = "allow"  # Permet des champs supplémentaires


class PotentialActionGlyph(GlyphData):
    """Modèle pour les glyphes d'action potentielle."""
    concept_type: Literal[ConceptType.POTENTIAL_ACTION] = Field(ConceptType.POTENTIAL_ACTION, description="Type de concept (toujours POTENTIAL_ACTION)")
    action_type: ActionType = Field(..., description="Type d'action à exécuter")
    priority: int = Field(50, ge=0, le=100, description="Priorité de l'action (0-100)")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Niveau de confiance (0.0-1.0)")
    details_structured_json: DetailsStructuredJson = Field(..., description="Détails structurés de l'action")
    details_text: Optional[str] = Field(None, description="Description textuelle de l'action")
    
    @validator('action_type')
    def validate_action_type(cls, v):
        """Valide que le type d'action est supporté."""
        if v not in ActionType:
            raise ValueError(f"Type d'action non supporté: {v}")
        return v
    
    @model_validator(mode='after')
    def validate_action_parameters(self):
        """Valide que les paramètres correspondent au type d'action."""
        action_type = self.action_type
        details = self.details_structured_json
        
        if not details or not details.action_parameters:
            raise ValueError("Les paramètres d'action sont requis")
        
        params = details.action_parameters
        
        if action_type == ActionType.CREATE_RELATIONSHIP:
            if not params.source_glyph_id or not params.target_glyph_id or not params.relationship_type:
                logger.warning("Paramètres incomplets pour CREATE_RELATIONSHIP")
        
        elif action_type == ActionType.CREATE_SOLUTION_NODE:
            if not params.problem_glyphs:
                logger.warning("Paramètres incomplets pour CREATE_SOLUTION_NODE")
        
        elif action_type == ActionType.FIND_AND_CONNECT_ISOLATED:
            if not params.target_glyph_id:
                logger.warning("Paramètres incomplets pour FIND_AND_CONNECT_ISOLATED")
        
        elif action_type == ActionType.ENRICH_HUB_NODE:
            if not params.target_glyph_id:
                logger.warning("Paramètres incomplets pour ENRICH_HUB_NODE")
        
        return self


class ExecutionResultData(BaseModel):
    """
    Données de résultat d'exécution d'action.
    Contient les données spécifiques au résultat de chaque type d'action.
    """
    # Champs pour CREATE_RELATIONSHIP
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    r_type: Optional[str] = None
    
    # Champs pour CREATE_SOLUTION_NODE
    solution_id: Optional[str] = None
    relationships: Optional[List[Dict[str, str]]] = None
    
    # Champs pour FIND_AND_CONNECT_ISOLATED et ENRICH_HUB_NODE
    glyph_id: Optional[str] = None
    
    # Champs pour ENRICH_HUB_NODE
    original_prompt: Optional[str] = None
    enriched_prompt: Optional[str] = None
    
    class Config:
        """Configuration du modèle Pydantic."""
        extra = "allow"  # Permet des champs supplémentaires


class ExecutionResult(BaseModel):
    """
    Résultat d'exécution d'une action.
    Contient le statut, le message et les données du résultat.
    """
    status: ExecutionStatus = Field(..., description="Statut de l'exécution")
    message: str = Field(..., description="Message décrivant le résultat")
    data: Optional[ExecutionResultData] = Field(None, description="Données du résultat")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="Horodatage de l'exécution")
    
    class Config:
        """Configuration du modèle Pydantic."""
        extra = "allow"  # Permet des champs supplémentaires


def convert_dict_to_glyph(data: Dict[str, Any]) -> Union[GlyphData, PotentialActionGlyph]:
    """
    Convertit un dictionnaire en objet GlyphData ou PotentialActionGlyph.
    
    Args:
        data: Dictionnaire à convertir
        
    Returns:
        GlyphData ou PotentialActionGlyph: Objet converti
    """
    try:
        # Déterminer le type de glyphe
        concept_type = data.get('concept_type')
        
        if concept_type == ConceptType.POTENTIAL_ACTION:
            # Convertir en PotentialActionGlyph
            return PotentialActionGlyph.model_validate(data)
        else:
            # Convertir en GlyphData
            return GlyphData.model_validate(data)
    except Exception as e:
        logger.error(f"Erreur lors de la conversion du dictionnaire en glyphe: {e}")
        raise


def convert_glyph_to_dict(glyph: Union[GlyphData, PotentialActionGlyph]) -> Dict[str, Any]:
    """
    Convertit un objet GlyphData ou PotentialActionGlyph en dictionnaire.
    
    Args:
        glyph: Objet à convertir
        
    Returns:
        Dict[str, Any]: Dictionnaire converti
    """
    try:
        return json.loads(glyph.model_dump_json())
    except Exception as e:
        logger.error(f"Erreur lors de la conversion du glyphe en dictionnaire: {e}")
        raise


# Fonction principale pour les tests
if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Exemple de création de glyphe
    glyph = GlyphData(
        id="techglyph_202505140900_1",
        concept_type=ConceptType.TECHNICALCONCEPT,
        natural_prompt="Un concept technique important",
        tags=["ai", "machine_learning"]
    )
    
    print(f"Glyphe créé: {glyph.id}, type: {glyph.concept_type}")
    
    # Exemple de création d'action potentielle
    action = PotentialActionGlyph(
        id="sem-potentialaction-TOPOGEN-CONNECT-20250620-001",
        action_type=ActionType.CREATE_RELATIONSHIP,
        priority=80,
        confidence=0.9,
        details_structured_json=DetailsStructuredJson(
            action_parameters=ActionParameters(
                source_glyph_id="techglyph_202505140900_1",
                target_glyph_id="techglyph_202505140900_2",
                relationship_type="SIMILAR_TO"
            ),
            source_metadata=SourceMetadata(
                intention_type="CONNECT_SIMILAR_GLYPHS"
            )
        ),
        details_text="Créer une relation de similarité entre deux glyphes techniques"
    )
    
    print(f"Action créée: {action.id}, type: {action.action_type}")
    
    # Conversion en dictionnaire et retour
    action_dict = convert_glyph_to_dict(action)
    action_restored = convert_dict_to_glyph(action_dict)
    
    print(f"Action restaurée: {action_restored.id}, type: {action_restored.action_type}")
