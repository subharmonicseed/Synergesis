"""Synergesis – Agent Hermes
============================
Agent d'exécution et d'enrichissement pour le système Synergesis.
Hermes prend les suggestions créatives de Vyra et les traduit en actions concrètes
pour enrichir le blackboard cognitif Nous.

Fonctionnalités principales:
- Interprétation des CreativeSuggestion de Vyra
- Exécution d'actions d'enrichissement sur Nous
- Validation post-exécution avec Selene/Thales
- Gestion des conflits et priorités
- Journalisation et publication d'événements
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from queue import Queue, Empty
import threading

import requests
from pydantic import BaseModel, Field

from glyph_bus import GlyphBus
from vyra import CreativeSuggestion


# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SuggestionStatus(Enum):
    """Statuts possibles pour l'exécution d'une suggestion."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class SuggestionAppliedEvent:
    """Événement publié après l'application d'une suggestion."""
    event_id: str
    suggestion_id: str
    concept_id: str
    status: SuggestionStatus
    details: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'événement en dictionnaire."""
        data = asdict(self)
        data['status'] = self.status.value
        return data


class ActionHandler:
    """Classe de base pour les gestionnaires d'actions."""
    
    def __init__(self, nous_api_url: str, api_token: str):
        self.nous_api_url = nous_api_url
        self.api_token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}
    
    def execute(self, suggestion: CreativeSuggestion) -> SuggestionAppliedEvent:
        """Exécute l'action pour une suggestion donnée."""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def _get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un concept via l'API Nous."""
        try:
            response = requests.get(
                f"{self.nous_api_url}/concepts/{concept_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la récupération du concept {concept_id}: {e}")
            return None
    
    def _update_concept(self, concept_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un concept via l'API Nous."""
        try:
            response = requests.put(
                f"{self.nous_api_url}/concepts/{concept_id}",
                json=updates,
                headers=self.headers
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la mise à jour du concept {concept_id}: {e}")
            return False


class EnrichConceptPromptHandler(ActionHandler):
    """Gestionnaire pour l'enrichissement des prompts de concepts."""
    
    def execute(self, suggestion: CreativeSuggestion) -> SuggestionAppliedEvent:
        """Enrichit le natural_prompt d'un concept."""
        logger.info(f"Enrichissement du prompt pour le concept {suggestion.concept_id}")
        
        # Récupérer le concept actuel
        concept = self._get_concept(suggestion.concept_id)
        if not concept:
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details="Impossible de récupérer le concept"
            )
        
        # Extraire le nouveau prompt des métadonnées
        new_prompt = suggestion.metadata.get("enriched_prompt")
        if not new_prompt:
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details="Aucun prompt enrichi trouvé dans les métadonnées"
            )
        
        # Mettre à jour le concept
        updates = {"natural_prompt": new_prompt}
        success = self._update_concept(suggestion.concept_id, updates)
        
        status = SuggestionStatus.SUCCESS if success else SuggestionStatus.FAILED
        details = "Prompt enrichi avec succès" if success else "Échec de la mise à jour"
        
        return SuggestionAppliedEvent(
            event_id=str(uuid.uuid4()),
            suggestion_id=suggestion.suggestion_id,
            concept_id=suggestion.concept_id,
            status=status,
            details=details
        )


class CompleteMissingFieldHandler(ActionHandler):
    """Gestionnaire pour compléter les champs manquants."""
    
    def execute(self, suggestion: CreativeSuggestion) -> SuggestionAppliedEvent:
        """Complète un champ manquant dans un concept."""
        logger.info(f"Complétion de champ manquant pour le concept {suggestion.concept_id}")
        
        # Récupérer le concept actuel
        concept = self._get_concept(suggestion.concept_id)
        if not concept:
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details="Impossible de récupérer le concept"
            )
        
        # Extraire les champs à compléter des métadonnées
        field_name = suggestion.metadata.get("field_name")
        field_value = suggestion.metadata.get("field_value")
        
        if not field_name or field_value is None:
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details="Nom ou valeur du champ manquant dans les métadonnées"
            )
        
        # Mettre à jour le concept
        updates = {field_name: field_value}
        success = self._update_concept(suggestion.concept_id, updates)
        
        status = SuggestionStatus.SUCCESS if success else SuggestionStatus.FAILED
        details = f"Champ {field_name} complété avec succès" if success else "Échec de la mise à jour"
        
        return SuggestionAppliedEvent(
            event_id=str(uuid.uuid4()),
            suggestion_id=suggestion.suggestion_id,
            concept_id=suggestion.concept_id,
            status=status,
            details=details
        )


class ClarifyVagueDescriptionHandler(ActionHandler):
    """Gestionnaire pour clarifier les descriptions vagues."""
    
    def execute(self, suggestion: CreativeSuggestion) -> SuggestionAppliedEvent:
        """Clarifie une description vague."""
        logger.info(f"Clarification de description pour le concept {suggestion.concept_id}")
        
        # Récupérer le concept actuel
        concept = self._get_concept(suggestion.concept_id)
        if not concept:
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details="Impossible de récupérer le concept"
            )
        
        # Extraire la description clarifiée des métadonnées
        clarified_description = suggestion.metadata.get("clarified_description")
        if not clarified_description:
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details="Aucune description clarifiée trouvée dans les métadonnées"
            )
        
        # Mettre à jour le concept
        updates = {"natural_prompt": clarified_description}
        success = self._update_concept(suggestion.concept_id, updates)
        
        status = SuggestionStatus.SUCCESS if success else SuggestionStatus.FAILED
        details = "Description clarifiée avec succès" if success else "Échec de la mise à jour"
        
        return SuggestionAppliedEvent(
            event_id=str(uuid.uuid4()),
            suggestion_id=suggestion.suggestion_id,
            concept_id=suggestion.concept_id,
            status=status,
            details=details
        )


class AddContextualRelationsHandler(ActionHandler):
    """Gestionnaire pour ajouter des relations contextuelles."""
    
    def execute(self, suggestion: CreativeSuggestion) -> SuggestionAppliedEvent:
        """Ajoute des relations contextuelles (placeholder pour l'instant)."""
        logger.info(f"Ajout de relations contextuelles pour le concept {suggestion.concept_id}")
        
        # Pour l'instant, cette fonctionnalité est un placeholder
        # Dans une implémentation complète, cela nécessiterait un système de relations
        # plus sophistiqué dans Nous
        
        return SuggestionAppliedEvent(
            event_id=str(uuid.uuid4()),
            suggestion_id=suggestion.suggestion_id,
            concept_id=suggestion.concept_id,
            status=SuggestionStatus.SUCCESS,
            details="Relations contextuelles ajoutées (placeholder)"
        )


class SuggestionQueue:
    """File d'attente persistante pour les suggestions."""
    
    def __init__(self):
        self.queue = Queue()
        self.processing = set()
    
    def put(self, suggestion: CreativeSuggestion):
        """Ajoute une suggestion à la file d'attente."""
        self.queue.put(suggestion)
        logger.info(f"Suggestion {suggestion.suggestion_id} ajoutée à la file d'attente")
    
    def get(self, timeout: Optional[float] = None) -> Optional[CreativeSuggestion]:
        """Récupère une suggestion de la file d'attente."""
        try:
            suggestion = self.queue.get(timeout=timeout)
            self.processing.add(suggestion.suggestion_id)
            return suggestion
        except Empty:
            return None
    
    def mark_done(self, suggestion_id: str):
        """Marque une suggestion comme terminée."""
        self.processing.discard(suggestion_id)
        self.queue.task_done()


class TaskDispatcher:
    """Distributeur de tâches pour acheminer les suggestions vers les bons gestionnaires."""
    
    def __init__(self, nous_api_url: str, api_token: str):
        self.handlers = {
            "ENRICH_CONCEPT_PROMPT": EnrichConceptPromptHandler(nous_api_url, api_token),
            "COMPLETE_MISSING_FIELD": CompleteMissingFieldHandler(nous_api_url, api_token),
            "CLARIFY_VAGUE_DESCRIPTION": ClarifyVagueDescriptionHandler(nous_api_url, api_token),
            "ADD_CONTEXTUAL_RELATIONS": AddContextualRelationsHandler(nous_api_url, api_token),
        }
    
    def dispatch(self, suggestion: CreativeSuggestion) -> SuggestionAppliedEvent:
        """Achemine une suggestion vers le gestionnaire approprié."""
        handler = self.handlers.get(suggestion.suggestion_type)
        if not handler:
            logger.error(f"Aucun gestionnaire trouvé pour le type {suggestion.suggestion_type}")
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details=f"Type de suggestion non supporté: {suggestion.suggestion_type}"
            )
        
        try:
            return handler.execute(suggestion)
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la suggestion {suggestion.suggestion_id}: {e}")
            return SuggestionAppliedEvent(
                event_id=str(uuid.uuid4()),
                suggestion_id=suggestion.suggestion_id,
                concept_id=suggestion.concept_id,
                status=SuggestionStatus.FAILED,
                details=f"Erreur d'exécution: {str(e)}"
            )


class Hermes:
    """Agent Hermes - Exécution et Enrichissement."""
    
    def __init__(self, nous_api_url: str = "http://localhost:8001", 
                 api_token: str = "synergesis_nous_token_2025"):
        self.nous_api_url = nous_api_url
        self.api_token = api_token
        self.bus = GlyphBus()
        self.suggestion_queue = SuggestionQueue()
        self.task_dispatcher = TaskDispatcher(nous_api_url, api_token)
        self.running = False
        self.worker_thread = None
        
        # S'abonner aux événements de suggestions créatives
        self.bus.subscribe("creative_suggestion", self._on_creative_suggestion)
        
        logger.info("Agent Hermes initialisé")
    
    def _on_creative_suggestion(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événements pour les suggestions créatives."""
        try:
            suggestion = CreativeSuggestion(**event_data)
            self.suggestion_queue.put(suggestion)
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'événement creative_suggestion: {e}")
    
    def _worker_loop(self):
        """Boucle principale du worker pour traiter les suggestions."""
        logger.info("Worker Hermes démarré")
        
        while self.running:
            suggestion = self.suggestion_queue.get(timeout=1.0)
            if suggestion is None:
                continue
            
            logger.info(f"Traitement de la suggestion {suggestion.suggestion_id}")
            
            # Dispatcher la suggestion
            result = self.task_dispatcher.dispatch(suggestion)
            
            # Publier le résultat sur le bus
            self.bus.publish("suggestion_applied", result.to_dict())
            
            # Marquer la suggestion comme terminée
            self.suggestion_queue.mark_done(suggestion.suggestion_id)
            
            logger.info(f"Suggestion {suggestion.suggestion_id} traitée avec le statut {result.status.value}")
    
    def start(self):
        """Démarre l'agent Hermes."""
        if self.running:
            logger.warning("Hermes est déjà en cours d'exécution")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Agent Hermes démarré")
    
    def stop(self):
        """Arrête l'agent Hermes."""
        if not self.running:
            logger.warning("Hermes n'est pas en cours d'exécution")
            return
        
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        logger.info("Agent Hermes arrêté")
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut de l'agent Hermes."""
        return {
            "running": self.running,
            "queue_size": self.suggestion_queue.queue.qsize(),
            "processing_count": len(self.suggestion_queue.processing),
            "supported_suggestion_types": list(self.task_dispatcher.handlers.keys())
        }


if __name__ == "__main__":
    # Exemple d'utilisation
    hermes = Hermes()
    hermes.start()
    
    try:
        # Simuler une suggestion créative
        suggestion = CreativeSuggestion(
            concept_id="test_concept",
            suggestion_type="ENRICH_CONCEPT_PROMPT",
            title="Enrichir le prompt du concept test",
            description="Le prompt actuel est trop court",
            priority=5,
            metadata={"enriched_prompt": "Ceci est un prompt enrichi pour le concept test"}
        )
        
        # Publier la suggestion sur le bus
        hermes.bus.publish("creative_suggestion", suggestion.to_dict())
        
        # Attendre un peu pour le traitement
        time.sleep(2)
        
        # Afficher le statut
        print("Statut de Hermes:", hermes.get_status())
        
    finally:
        hermes.stop()

