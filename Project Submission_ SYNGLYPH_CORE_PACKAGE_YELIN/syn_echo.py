from typing import Dict, List, Any, Optional
import time
import uuid

class PatternDetector:
    """
    Détecteur de motifs récurrents dans les interactions entre agents.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le détecteur de motifs.
        
        Args:
            config: Configuration du système
        """
        self.config = config
        self.patterns = {}
        self.threshold = config.get("pattern_detection_threshold", 0.7)
    
    def detect(self, interactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Détecte des motifs dans une liste d'interactions.
        
        Args:
            interactions: Liste d'interactions entre agents
            
        Returns:
            Liste des motifs détectés
        """
        if not interactions:
            return []
        
        detected_patterns = []
        
        # Analyse des séquences d'interactions
        sequences = self._extract_sequences(interactions)
        
        # Recherche de motifs récurrents
        for seq_id, sequence in sequences.items():
            pattern_strength = self._calculate_pattern_strength(sequence)
            
            if pattern_strength >= self.threshold:
                pattern = {
                    "id": str(uuid.uuid4()),
                    "sequence_id": seq_id,
                    "strength": pattern_strength,
                    "elements": sequence,
                    "timestamp": time.time()
                }
                
                detected_patterns.append(pattern)
                self.patterns[pattern["id"]] = pattern
        
        return detected_patterns
    
    def _extract_sequences(self, interactions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extrait des séquences d'interactions.
        
        Args:
            interactions: Liste d'interactions
            
        Returns:
            Dictionnaire de séquences
        """
        sequences = {}
        
        # Regrouper les interactions par conversation ou contexte
        for interaction in interactions:
            context_id = interaction.get("context_id", "default")
            
            if context_id not in sequences:
                sequences[context_id] = []
            
            sequences[context_id].append(interaction)
        
        return sequences
    
    def _calculate_pattern_strength(self, sequence: List[Dict[str, Any]]) -> float:
        """
        Calcule la force d'un motif dans une séquence.
        
        Args:
            sequence: Séquence d'interactions
            
        Returns:
            Force du motif (entre 0 et 1)
        """
        if not sequence:
            return 0.0
        
        # Cette implémentation est simplifiée
        # Une version plus avancée utiliserait des algorithmes de détection de motifs
        
        # Compter les répétitions d'actions similaires
        action_counts = {}
        for interaction in sequence:
            action = interaction.get("action", "unknown")
            if action not in action_counts:
                action_counts[action] = 0
            action_counts[action] += 1
        
        # Calculer la concentration des actions les plus fréquentes
        total_actions = len(sequence)
        most_common_count = max(action_counts.values()) if action_counts else 0
        
        return most_common_count / total_actions if total_actions > 0 else 0.0


class ConceptualDriftMonitor:
    """
    Moniteur de dérive conceptuelle dans les échanges entre agents.
    """
    
    def __init__(self):
        """Initialise le moniteur de dérive conceptuelle."""
        self.baseline = {}
        self.drift_history = []
    
    def set_baseline(self, concepts: Dict[str, Any]) -> None:
        """
        Définit une ligne de base pour les concepts.
        
        Args:
            concepts: Dictionnaire de concepts de référence
        """
        self.baseline = concepts.copy()
    
    def check(self, interactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Vérifie les dérives conceptuelles dans les interactions.
        
        Args:
            interactions: Liste d'interactions entre agents
            
        Returns:
            Liste des dérives détectées
        """
        if not self.baseline:
            # Si pas de ligne de base, extraire les concepts des premières interactions
            concepts = self._extract_concepts(interactions[:min(10, len(interactions))])
            self.set_baseline(concepts)
            return []
        
        # Extraire les concepts des interactions actuelles
        current_concepts = self._extract_concepts(interactions)
        
        # Détecter les dérives
        drifts = []
        
        for concept, current_value in current_concepts.items():
            if concept in self.baseline:
                baseline_value = self.baseline[concept]
                drift_magnitude = self._calculate_drift(baseline_value, current_value)
                
                if drift_magnitude > 0.2:  # Seuil de détection
                    drift = {
                        "id": str(uuid.uuid4()),
                        "concept": concept,
                        "baseline_value": baseline_value,
                        "current_value": current_value,
                        "magnitude": drift_magnitude,
                        "timestamp": time.time()
                    }
                    
                    drifts.append(drift)
                    self.drift_history.append(drift)
        
        return drifts
    
    def _extract_concepts(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extrait les concepts des interactions.
        
        Args:
            interactions: Liste d'interactions
            
        Returns:
            Dictionnaire de concepts extraits
        """
        concepts = {}
        
        for interaction in interactions:
            if "concepts" in interaction:
                for concept, value in interaction["concepts"].items():
                    if concept not in concepts:
                        concepts[concept] = []
                    concepts[concept].append(value)
        
        # Agréger les valeurs pour chaque concept
        aggregated = {}
        for concept, values in concepts.items():
            if isinstance(values[0], (int, float)):
                aggregated[concept] = sum(values) / len(values)
            else:
                # Pour les valeurs non numériques, utiliser la plus fréquente
                value_counts = {}
                for value in values:
                    value_str = str(value)
                    if value_str not in value_counts:
                        value_counts[value_str] = 0
                    value_counts[value_str] += 1
                
                most_common = max(value_counts.items(), key=lambda x: x[1])[0]
                aggregated[concept] = most_common
        
        return aggregated
    
    def _calculate_drift(self, baseline_value: Any, current_value: Any) -> float:
        """
        Calcule la magnitude de la dérive entre deux valeurs.
        
        Args:
            baseline_value: Valeur de référence
            current_value: Valeur actuelle
            
        Returns:
            Magnitude de la dérive (entre 0 et 1)
        """
        if isinstance(baseline_value, (int, float)) and isinstance(current_value, (int, float)):
            # Pour les valeurs numériques, calculer la différence relative
            max_val = max(abs(baseline_value), abs(current_value))
            if max_val == 0:
                return 0.0
            return abs(baseline_value - current_value) / max_val
        else:
            # Pour les valeurs non numériques, 1 si différent, 0 si identique
            return 0.0 if str(baseline_value) == str(current_value) else 1.0


class EmergenceAnalyzer:
    """
    Analyseur d'émergences symboliques dans les interactions.
    """
    
    def __init__(self):
        """Initialise l'analyseur d'émergences."""
        self.known_symbols = set()
        self.emergences = []
    
    def identify(self, interactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifie les émergences symboliques dans les interactions.
        
        Args:
            interactions: Liste d'interactions entre agents
            
        Returns:
            Liste des émergences identifiées
        """
        # Extraire tous les symboles des interactions
        all_symbols = set()
        for interaction in interactions:
            if "symbols" in interaction:
                for symbol in interaction["symbols"]:
                    symbol_id = symbol.get("id", str(symbol))
                    all_symbols.add(symbol_id)
        
        # Identifier les nouveaux symboles
        new_symbols = all_symbols - self.known_symbols
        
        # Mettre à jour la liste des symboles connus
        self.known_symbols.update(new_symbols)
        
        # Créer des objets d'émergence pour les nouveaux symboles
        new_emergences = []
        for symbol_id in new_symbols:
            # Trouver le symbole complet dans les interactions
            symbol_data = None
            for interaction in interactions:
                if "symbols" in interaction:
                    for symbol in interaction["symbols"]:
                        if symbol.get("id", str(symbol)) == symbol_id:
                            symbol_data = symbol
                            break
                if symbol_data:
                    break
            
            emergence = {
                "id": str(uuid.uuid4()),
                "symbol_id": symbol_id,
                "symbol_data": symbol_data,
                "first_seen": time.time(),
                "context": self._extract_context(interactions, symbol_id)
            }
            
            new_emergences.append(emergence)
            self.emergences.append(emergence)
        
        return new_emergences
    
    def _extract_context(self, interactions: List[Dict[str, Any]], symbol_id: str) -> Dict[str, Any]:
        """
        Extrait le contexte d'un symbole dans les interactions.
        
        Args:
            interactions: Liste d'interactions
            symbol_id: Identifiant du symbole
            
        Returns:
            Contexte du symbole
        """
        # Trouver les interactions contenant le symbole
        relevant_interactions = []
        for interaction in interactions:
            if "symbols" in interaction:
                for symbol in interaction["symbols"]:
                    if symbol.get("id", str(symbol)) == symbol_id:
                        relevant_interactions.append(interaction)
                        break
        
        # Extraire des informations contextuelles
        agents = set()
        topics = set()
        
        for interaction in relevant_interactions:
            if "agent" in interaction:
                agents.add(interaction["agent"])
            if "topic" in interaction:
                topics.add(interaction["topic"])
        
        return {
            "agents": list(agents),
            "topics": list(topics),
            "interaction_count": len(relevant_interactions)
        }


class SYN_ECHO:
    """
    Module SYN-ECHO du système Synergesis.
    Détecte les motifs récurrents, les émergences symboliques et
    les dérives conceptuelles dans les échanges inter-agents.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le module SYN-ECHO.
        
        Args:
            config: Configuration du système
        """
        self.config = config
        self.pattern_detector = PatternDetector(config)
        self.drift_monitor = ConceptualDriftMonitor()
        self.emergence_analyzer = EmergenceAnalyzer()
        self.analysis_history = []
    
    def analyze_interactions(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyse les interactions entre agents.
        
        Args:
            interactions: Liste d'interactions entre agents
            
        Returns:
            Résultats de l'analyse
        """
        if not interactions:
            return {
                "patterns": [],
                "drifts": [],
                "emergences": [],
                "timestamp": time.time()
            }
        
        # Détecter les motifs
        patterns = self.pattern_detector.detect(interactions)
        
        # Vérifier les dérives conceptuelles
        drifts = self.drift_monitor.check(interactions)
        
        # Identifier les émergences symboliques
        emergences = self.emergence_analyzer.identify(interactions)
        
        # Créer le rapport d'analyse
        analysis = {
            "id": str(uuid.uuid4()),
            "patterns": patterns,
            "drifts": drifts,
            "emergences": emergences,
            "interaction_count": len(interactions),
            "timestamp": time.time()
        }
        
        # Enregistrer l'analyse dans l'historique
        self.analysis_history.append(analysis)
        
        return analysis
    
    def get_recent_analyses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les analyses récentes.
        
        Args:
            limit: Nombre maximum d'analyses à retourner
            
        Returns:
            Liste des analyses récentes
        """
        return self.analysis_history[-limit:]
    
    def set_baseline(self, concepts: Dict[str, Any]) -> None:
        """
        Définit une ligne de base pour la détection de dérive conceptuelle.
        
        Args:
            concepts: Dictionnaire de concepts de référence
        """
        self.drift_monitor.set_baseline(concepts)
    
    def process(self, context: Dict[str, Any], previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traite une demande dans le cadre d'un flux orchestré.
        
        Args:
            context: Contexte de la demande
            previous_results: Résultats des modules précédents
            
        Returns:
            Résultats du traitement
        """
        interactions = context.get("interactions", [])
        
        # Si pas d'interactions dans le contexte, chercher dans les résultats précédents
        if not interactions and "deep_research" in previous_results:
            interactions = previous_results["deep_research"].get("interactions", [])
        
        return self.analyze_interactions(interactions)
