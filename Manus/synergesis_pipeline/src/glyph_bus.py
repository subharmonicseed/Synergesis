"""Synergesis – Glyph Bus
========================
Bus d'événements pour la communication inter-modules.

Le Glyph Bus permet aux modules de publier et de s'abonner à des événements
de manière découplée, facilitant l'intégration et la coordination entre
les différents composants du système Synergesis.
"""

from typing import Dict, List, Callable, Any
from datetime import datetime
import json


class GlyphEvent:
    """Représente un événement dans le Glyph Bus."""
    
    def __init__(self, event_type: str, data: Any, timestamp: float = None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.now().timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'événement en dictionnaire."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp
        }
    
    def to_json(self) -> str:
        """Convertit l'événement en JSON."""
        return json.dumps(self.to_dict())


class GlyphBus:
    """Bus d'événements pour la communication inter-modules."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[GlyphEvent] = []
        self._max_history = 1000  # Limite du nombre d'événements en historique
    
    def subscribe(self, event_type: str, callback: Callable[[Any], None]):
        """S'abonne à un type d'événement."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]):
        """Se désabonne d'un type d'événement."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass  # Le callback n'était pas dans la liste
    
    def publish(self, event_type: str, data: Any):
        """Publie un événement."""
        event = GlyphEvent(event_type, data)
        
        # Ajouter à l'historique
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)  # Supprimer le plus ancien
        
        # Notifier les abonnés
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Erreur lors de l'exécution du callback pour {event_type}: {e}")
    
    def get_history(self, event_type: str = None, limit: int = None) -> List[GlyphEvent]:
        """Récupère l'historique des événements."""
        history = self._history
        
        if event_type:
            history = [event for event in history if event.event_type == event_type]
        
        if limit:
            history = history[-limit:]
        
        return history
    
    def get_subscribers_count(self, event_type: str) -> int:
        """Retourne le nombre d'abonnés pour un type d'événement."""
        return len(self._subscribers.get(event_type, []))
    
    def clear_history(self):
        """Vide l'historique des événements."""
        self._history.clear()
    
    def get_event_types(self) -> List[str]:
        """Retourne la liste des types d'événements ayant des abonnés."""
        return list(self._subscribers.keys())


# Instance globale du bus (singleton pattern)
_global_bus = None

def get_global_bus() -> GlyphBus:
    """Retourne l'instance globale du Glyph Bus."""
    global _global_bus
    if _global_bus is None:
        _global_bus = GlyphBus()
    return _global_bus


if __name__ == "__main__":
    # Exemple d'utilisation
    bus = GlyphBus()
    
    # Définir des callbacks
    def on_concept_changed(data):
        print(f"Concept changé: {data}")
    
    def on_knowledge_gap(data):
        print(f"Lacune de connaissance détectée: {data}")
    
    # S'abonner aux événements
    bus.subscribe("concept_changed", on_concept_changed)
    bus.subscribe("knowledge_gap", on_knowledge_gap)
    
    # Publier des événements
    bus.publish("concept_changed", {"concept_id": "test_concept", "action": "updated"})
    bus.publish("knowledge_gap", {"gap_type": "missing_definition", "concept": "entropy"})
    
    # Afficher l'historique
    print("\nHistorique des événements:")
    for event in bus.get_history():
        print(f"- {event.event_type}: {event.data} (timestamp: {event.timestamp})")

