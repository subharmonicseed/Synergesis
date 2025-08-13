import threading
import time
from typing import Dict, List, Any, Optional

class Blackboard:
    """
    Espace de travail partagé pour tous les modules du système Synergesis.
    Implémente le pattern Blackboard pour permettre une communication asynchrone
    entre les différents modules.
    """
    
    def __init__(self):
        """Initialise un nouveau Blackboard vide."""
        self.data: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.lock = threading.RLock()
        
    def write(self, key: str, value: Any, author: str) -> None:
        """
        Écrit une valeur dans le Blackboard.
        
        Args:
            key: Clé identifiant la donnée
            value: Valeur à stocker
            author: Identifiant du module ou agent qui écrit la donnée
        """
        with self.lock:
            old_value = self.data.get(key)
            self.data[key] = value
            self.history.append({
                "action": "write",
                "key": key,
                "old_value": old_value,
                "new_value": value,
                "author": author,
                "timestamp": time.time()
            })
            
    def read(self, key: str) -> Any:
        """
        Lit une valeur depuis le Blackboard.
        
        Args:
            key: Clé identifiant la donnée à lire
            
        Returns:
            La valeur associée à la clé ou None si la clé n'existe pas
        """
        with self.lock:
            return self.data.get(key)
            
    def get_history(self, key: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des modifications du Blackboard.
        
        Args:
            key: Si spécifié, limite l'historique à cette clé
            limit: Nombre maximum d'entrées à retourner
            
        Returns:
            Liste des dernières modifications
        """
        with self.lock:
            if key:
                filtered = [h for h in self.history if h["key"] == key]
                return filtered[-limit:] if filtered else []
            return self.history[-limit:]
    
    def delete(self, key: str, author: str) -> bool:
        """
        Supprime une entrée du Blackboard.
        
        Args:
            key: Clé à supprimer
            author: Identifiant du module ou agent qui supprime la donnée
            
        Returns:
            True si la clé existait et a été supprimée, False sinon
        """
        with self.lock:
            if key in self.data:
                old_value = self.data.get(key)
                del self.data[key]
                self.history.append({
                    "action": "delete",
                    "key": key,
                    "old_value": old_value,
                    "author": author,
                    "timestamp": time.time()
                })
                return True
            return False
    
    def get_all_keys(self) -> List[str]:
        """
        Récupère toutes les clés actuellement présentes dans le Blackboard.
        
        Returns:
            Liste des clés
        """
        with self.lock:
            return list(self.data.keys())
    
    def clear(self, author: str) -> None:
        """
        Efface toutes les données du Blackboard.
        
        Args:
            author: Identifiant du module ou agent qui efface les données
        """
        with self.lock:
            old_data = self.data.copy()
            self.data.clear()
            self.history.append({
                "action": "clear",
                "old_value": old_data,
                "author": author,
                "timestamp": time.time()
            })
