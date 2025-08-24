"""
Module Nous Enhanced - Blackboard de connaissances avec graphes de raisonnement complets,
logs introspectifs et traçabilité (audit replay, decision-lineage).
"""

import os
import json
import time
import uuid
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from sqlmodel import Field, SQLModel, Session, select, create_engine
from whoosh.fields import ID, TEXT, SchemaClass
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser

from glyph_bus import GlyphBus


class ReasoningNodeType(Enum):
    """Types de nœuds dans le graphe de raisonnement."""
    CONCEPT = "concept"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    CONTRADICTION = "contradiction"
    SYNTHESIS = "synthesis"


class DecisionType(Enum):
    """Types de décisions dans la lignée décisionnelle."""
    CONCEPT_ADDITION = "concept_addition"
    CONCEPT_MODIFICATION = "concept_modification"
    CONCEPT_DELETION = "concept_deletion"
    RELATION_CREATION = "relation_creation"
    INFERENCE_MADE = "inference_made"
    HYPOTHESIS_GENERATED = "hypothesis_generated"


@dataclass
class ReasoningNode:
    """Nœud dans le graphe de raisonnement."""
    node_id: str
    node_type: ReasoningNodeType
    content: Dict[str, Any]
    confidence: float
    created_at: float
    created_by: str  # Agent qui a créé ce nœud
    parent_nodes: List[str]  # Nœuds parents dans le raisonnement
    metadata: Dict[str, Any]


@dataclass
class ReasoningEdge:
    """Arête dans le graphe de raisonnement."""
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    strength: float
    evidence: Dict[str, Any]
    created_at: float
    created_by: str


@dataclass
class DecisionRecord:
    """Enregistrement d'une décision dans la lignée décisionnelle."""
    decision_id: str
    decision_type: DecisionType
    agent_id: str
    timestamp: float
    input_context: Dict[str, Any]
    decision_rationale: str
    affected_concepts: List[str]
    reasoning_path: List[str]  # Chemin dans le graphe de raisonnement
    confidence: float
    metadata: Dict[str, Any]


@dataclass
class IntrospectiveLog:
    """Log introspectif pour l'auto-analyse du système."""
    log_id: str
    timestamp: float
    agent_id: str
    log_type: str  # "reflection", "self_assessment", "performance_analysis"
    content: Dict[str, Any]
    insights: List[str]
    action_items: List[str]
    confidence: float


class Concept(SQLModel, table=True, extend_existing=True):
    """Modèle de concept étendu avec traçabilité."""
    id: Optional[int] = Field(default=None, primary_key=True)
    concept_id: str = Field(index=True, unique=True)
    natural_prompt: str
    concept_type: str
    source: str
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    resonance: Optional[float] = None
    weight: Optional[float] = None
    
    # Nouveaux champs pour la traçabilité
    creation_decision_id: Optional[str] = None
    last_modification_decision_id: Optional[str] = None
    reasoning_node_id: Optional[str] = None
    provenance_chain: Optional[str] = None  # JSON des décisions qui ont mené à ce concept


class ReasoningGraph:
    """Gestionnaire du graphe de raisonnement complet."""
    
    def __init__(self, storage_path: str = "reasoning_graph.json"):
        self.storage_path = storage_path
        self.nodes: Dict[str, ReasoningNode] = {}
        self.edges: Dict[str, ReasoningEdge] = {}
        self.load_graph()
    
    def add_node(self, node: ReasoningNode) -> str:
        """Ajoute un nœud au graphe de raisonnement."""
        self.nodes[node.node_id] = node
        self.save_graph()
        return node.node_id
    
    def add_edge(self, edge: ReasoningEdge) -> str:
        """Ajoute une arête au graphe de raisonnement."""
        # Vérification que les nœuds source et cible existent
        if edge.source_node_id not in self.nodes or edge.target_node_id not in self.nodes:
            raise ValueError("Les nœuds source et cible doivent exister")
        
        self.edges[edge.edge_id] = edge
        self.save_graph()
        return edge.edge_id
    
    def create_reasoning_chain(self, concept_id: str, reasoning_steps: List[Dict[str, Any]], 
                             agent_id: str) -> List[str]:
        """Crée une chaîne de raisonnement pour un concept."""
        node_ids = []
        previous_node_id = None
        
        for i, step in enumerate(reasoning_steps):
            # Création du nœud de raisonnement
            node = ReasoningNode(
                node_id=f"{concept_id}_reasoning_{i}_{uuid.uuid4().hex[:8]}",
                node_type=ReasoningNodeType(step.get("type", "inference")),
                content=step,
                confidence=step.get("confidence", 0.7),
                created_at=time.time(),
                created_by=agent_id,
                parent_nodes=[previous_node_id] if previous_node_id else [],
                metadata={"step_index": i, "concept_id": concept_id}
            )
            
            node_id = self.add_node(node)
            node_ids.append(node_id)
            
            # Création de l'arête avec le nœud précédent
            if previous_node_id:
                edge = ReasoningEdge(
                    edge_id=f"edge_{previous_node_id}_{node_id}",
                    source_node_id=previous_node_id,
                    target_node_id=node_id,
                    relation_type="leads_to",
                    strength=0.8,
                    evidence={"reasoning_step": i},
                    created_at=time.time(),
                    created_by=agent_id
                )
                self.add_edge(edge)
            
            previous_node_id = node_id
        
        return node_ids
    
    def get_reasoning_path(self, start_node_id: str, end_node_id: str) -> List[str]:
        """Trouve le chemin de raisonnement entre deux nœuds."""
        # Implémentation d'un algorithme de recherche de chemin simple
        visited = set()
        queue = [(start_node_id, [start_node_id])]
        
        while queue:
            current_node, path = queue.pop(0)
            
            if current_node == end_node_id:
                return path
            
            if current_node in visited:
                continue
            
            visited.add(current_node)
            
            # Recherche des nœuds connectés
            for edge in self.edges.values():
                if edge.source_node_id == current_node:
                    next_node = edge.target_node_id
                    if next_node not in visited:
                        queue.append((next_node, path + [next_node]))
        
        return []  # Aucun chemin trouvé
    
    def get_node_ancestors(self, node_id: str, max_depth: int = 10) -> List[ReasoningNode]:
        """Récupère les ancêtres d'un nœud dans le graphe."""
        ancestors = []
        visited = set()
        queue = [(node_id, 0)]
        
        while queue:
            current_node_id, depth = queue.pop(0)
            
            if depth >= max_depth or current_node_id in visited:
                continue
            
            visited.add(current_node_id)
            
            if current_node_id in self.nodes:
                node = self.nodes[current_node_id]
                if depth > 0:  # Exclure le nœud de départ
                    ancestors.append(node)
                
                # Ajout des parents à la queue
                for parent_id in node.parent_nodes:
                    queue.append((parent_id, depth + 1))
        
        return ancestors
    
    def save_graph(self):
        """Sauvegarde le graphe de raisonnement."""
        graph_data = {
            "nodes": {node_id: asdict(node) for node_id, node in self.nodes.items()},
            "edges": {edge_id: asdict(edge) for edge_id, edge in self.edges.items()},
            "metadata": {
                "last_saved": time.time(),
                "node_count": len(self.nodes),
                "edge_count": len(self.edges)
            }
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(graph_data, f, indent=2, default=str)
    
    def load_graph(self):
        """Charge le graphe de raisonnement."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    graph_data = json.load(f)
                
                # Reconstruction des nœuds
                for node_id, node_data in graph_data.get("nodes", {}).items():
                    node_data["node_type"] = ReasoningNodeType(node_data["node_type"])
                    self.nodes[node_id] = ReasoningNode(**node_data)
                
                # Reconstruction des arêtes
                for edge_id, edge_data in graph_data.get("edges", {}).items():
                    self.edges[edge_id] = ReasoningEdge(**edge_data)
                
            except Exception as e:
                print(f"Erreur lors du chargement du graphe: {e}")
                self.nodes = {}
                self.edges = {}


class DecisionLineageTracker:
    """Gestionnaire de la lignée décisionnelle avec audit replay."""
    
    def __init__(self, storage_path: str = "decision_lineage.json"):
        self.storage_path = storage_path
        self.decisions: Dict[str, DecisionRecord] = {}
        self.decision_chains: Dict[str, List[str]] = {}  # concept_id -> liste des decision_ids
        self.load_lineage()
    
    def record_decision(self, decision: DecisionRecord) -> str:
        """Enregistre une décision dans la lignée."""
        self.decisions[decision.decision_id] = decision
        
        # Mise à jour des chaînes de décisions pour les concepts affectés
        for concept_id in decision.affected_concepts:
            if concept_id not in self.decision_chains:
                self.decision_chains[concept_id] = []
            self.decision_chains[concept_id].append(decision.decision_id)
        
        self.save_lineage()
        return decision.decision_id
    
    def get_concept_lineage(self, concept_id: str) -> List[DecisionRecord]:
        """Récupère la lignée décisionnelle complète d'un concept."""
        if concept_id not in self.decision_chains:
            return []
        
        decision_ids = self.decision_chains[concept_id]
        return [self.decisions[decision_id] for decision_id in decision_ids if decision_id in self.decisions]
    
    def replay_decisions(self, concept_id: str, target_timestamp: float) -> Dict[str, Any]:
        """Rejoue les décisions jusqu'à un timestamp donné (audit replay)."""
        lineage = self.get_concept_lineage(concept_id)
        
        # Filtrage des décisions jusqu'au timestamp cible
        relevant_decisions = [
            decision for decision in lineage
            if decision.timestamp <= target_timestamp
        ]
        
        # Reconstruction de l'état du concept
        concept_state = {
            "concept_id": concept_id,
            "replay_timestamp": target_timestamp,
            "decisions_applied": len(relevant_decisions),
            "state_reconstruction": {},
            "reasoning_path": []
        }
        
        for decision in sorted(relevant_decisions, key=lambda d: d.timestamp):
            # Application de la décision
            if decision.decision_type == DecisionType.CONCEPT_ADDITION:
                concept_state["state_reconstruction"]["created"] = True
                concept_state["state_reconstruction"]["creation_context"] = decision.input_context
            
            elif decision.decision_type == DecisionType.CONCEPT_MODIFICATION:
                if "modifications" not in concept_state["state_reconstruction"]:
                    concept_state["state_reconstruction"]["modifications"] = []
                concept_state["state_reconstruction"]["modifications"].append({
                    "timestamp": decision.timestamp,
                    "agent": decision.agent_id,
                    "changes": decision.input_context
                })
            
            # Ajout du chemin de raisonnement
            concept_state["reasoning_path"].extend(decision.reasoning_path)
        
        return concept_state
    
    def analyze_decision_patterns(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Analyse les patterns de décision pour un agent ou globalement."""
        decisions_to_analyze = [
            decision for decision in self.decisions.values()
            if agent_id is None or decision.agent_id == agent_id
        ]
        
        if not decisions_to_analyze:
            return {"error": "Aucune décision à analyser"}
        
        # Analyse des patterns
        decision_types = {}
        confidence_scores = []
        temporal_patterns = {}
        
        for decision in decisions_to_analyze:
            # Comptage des types de décisions
            decision_type = decision.decision_type.value
            decision_types[decision_type] = decision_types.get(decision_type, 0) + 1
            
            # Collecte des scores de confiance
            confidence_scores.append(decision.confidence)
            
            # Analyse temporelle
            hour = datetime.fromtimestamp(decision.timestamp).hour
            temporal_patterns[hour] = temporal_patterns.get(hour, 0) + 1
        
        return {
            "total_decisions": len(decisions_to_analyze),
            "decision_types": decision_types,
            "avg_confidence": sum(confidence_scores) / len(confidence_scores),
            "confidence_distribution": {
                "min": min(confidence_scores),
                "max": max(confidence_scores),
                "std": self._calculate_std(confidence_scores)
            },
            "temporal_patterns": temporal_patterns,
            "most_active_hour": max(temporal_patterns.items(), key=lambda x: x[1])[0] if temporal_patterns else None
        }
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calcule l'écart-type d'une liste de valeurs."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def save_lineage(self):
        """Sauvegarde la lignée décisionnelle."""
        lineage_data = {
            "decisions": {
                decision_id: {
                    **asdict(decision),
                    "decision_type": decision.decision_type.value
                }
                for decision_id, decision in self.decisions.items()
            },
            "decision_chains": self.decision_chains,
            "metadata": {
                "last_saved": time.time(),
                "total_decisions": len(self.decisions),
                "total_chains": len(self.decision_chains)
            }
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(lineage_data, f, indent=2, default=str)
    
    def load_lineage(self):
        """Charge la lignée décisionnelle."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    lineage_data = json.load(f)
                
                # Reconstruction des décisions
                for decision_id, decision_data in lineage_data.get("decisions", {}).items():
                    decision_data["decision_type"] = DecisionType(decision_data["decision_type"])
                    self.decisions[decision_id] = DecisionRecord(**decision_data)
                
                # Reconstruction des chaînes
                self.decision_chains = lineage_data.get("decision_chains", {})
                
            except Exception as e:
                print(f"Erreur lors du chargement de la lignée: {e}")
                self.decisions = {}
                self.decision_chains = {}


class IntrospectiveLogger:
    """Système de logs introspectifs pour l'auto-analyse."""
    
    def __init__(self, storage_path: str = "introspective_logs.json"):
        self.storage_path = storage_path
        self.logs: Dict[str, IntrospectiveLog] = {}
        self.reflection_triggers: Dict[str, Callable] = {}
        self._setup_reflection_triggers()
        self.load_logs()
    
    def _setup_reflection_triggers(self):
        """Configure les déclencheurs de réflexion automatique."""
        self.reflection_triggers = {
            "performance_degradation": self._trigger_performance_reflection,
            "error_pattern": self._trigger_error_pattern_reflection,
            "concept_growth": self._trigger_concept_growth_reflection,
            "decision_confidence_drop": self._trigger_confidence_reflection
        }
    
    def log_reflection(self, agent_id: str, reflection_type: str, 
                      content: Dict[str, Any]) -> str:
        """Enregistre une réflexion introspective."""
        log_id = str(uuid.uuid4())
        
        # Analyse automatique du contenu pour extraire des insights
        insights = self._extract_insights(content, reflection_type)
        action_items = self._generate_action_items(content, insights)
        
        log = IntrospectiveLog(
            log_id=log_id,
            timestamp=time.time(),
            agent_id=agent_id,
            log_type=reflection_type,
            content=content,
            insights=insights,
            action_items=action_items,
            confidence=content.get("confidence", 0.7)
        )
        
        self.logs[log_id] = log
        self.save_logs()
        
        return log_id
    
    def trigger_reflection(self, trigger_type: str, context: Dict[str, Any]) -> Optional[str]:
        """Déclenche une réflexion automatique."""
        if trigger_type in self.reflection_triggers:
            reflection_content = self.reflection_triggers[trigger_type](context)
            if reflection_content:
                return self.log_reflection(
                    agent_id=context.get("agent_id", "system"),
                    reflection_type=trigger_type,
                    content=reflection_content
                )
        return None
    
    def _extract_insights(self, content: Dict[str, Any], reflection_type: str) -> List[str]:
        """Extrait des insights automatiquement du contenu de réflexion."""
        insights = []
        
        if reflection_type == "performance_degradation":
            if content.get("success_rate", 1.0) < 0.7:
                insights.append("Taux de succès en baisse, révision des stratégies nécessaire")
            
            if content.get("response_time", 0) > 5.0:
                insights.append("Temps de réponse élevé, optimisation requise")
        
        elif reflection_type == "concept_growth":
            growth_rate = content.get("growth_rate", 0)
            if growth_rate > 0.5:
                insights.append("Croissance rapide des concepts, surveillance de la qualité nécessaire")
            elif growth_rate < 0.1:
                insights.append("Croissance lente des concepts, stimulation de l'innovation requise")
        
        elif reflection_type == "error_pattern":
            error_frequency = content.get("error_frequency", 0)
            if error_frequency > 0.1:
                insights.append("Fréquence d'erreurs élevée, analyse des causes racines nécessaire")
        
        return insights
    
    def _generate_action_items(self, content: Dict[str, Any], insights: List[str]) -> List[str]:
        """Génère des éléments d'action basés sur les insights."""
        action_items = []
        
        for insight in insights:
            if "révision des stratégies" in insight:
                action_items.append("Analyser les échecs récents et ajuster les algorithmes")
            
            elif "optimisation requise" in insight:
                action_items.append("Profiler les performances et identifier les goulots d'étranglement")
            
            elif "surveillance de la qualité" in insight:
                action_items.append("Mettre en place des métriques de qualité automatisées")
            
            elif "stimulation de l'innovation" in insight:
                action_items.append("Augmenter la diversité des sources et des méthodes de génération")
            
            elif "analyse des causes racines" in insight:
                action_items.append("Effectuer une analyse détaillée des patterns d'erreur")
        
        return action_items
    
    def _trigger_performance_reflection(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Déclenche une réflexion sur les performances."""
        return {
            "trigger": "performance_degradation",
            "metrics": context.get("performance_metrics", {}),
            "threshold_breached": context.get("threshold_breached"),
            "analysis_period": context.get("analysis_period", "24h"),
            "confidence": 0.8
        }
    
    def _trigger_error_pattern_reflection(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Déclenche une réflexion sur les patterns d'erreur."""
        return {
            "trigger": "error_pattern",
            "error_types": context.get("error_types", []),
            "error_frequency": context.get("error_frequency", 0),
            "affected_components": context.get("affected_components", []),
            "confidence": 0.9
        }
    
    def _trigger_concept_growth_reflection(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Déclenche une réflexion sur la croissance des concepts."""
        return {
            "trigger": "concept_growth",
            "growth_rate": context.get("growth_rate", 0),
            "quality_metrics": context.get("quality_metrics", {}),
            "diversity_score": context.get("diversity_score", 0.5),
            "confidence": 0.7
        }
    
    def _trigger_confidence_reflection(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Déclenche une réflexion sur la baisse de confiance."""
        return {
            "trigger": "decision_confidence_drop",
            "avg_confidence": context.get("avg_confidence", 0.5),
            "confidence_trend": context.get("confidence_trend", "declining"),
            "decision_types_affected": context.get("decision_types_affected", []),
            "confidence": 0.8
        }
    
    def save_logs(self):
        """Sauvegarde les logs introspectifs."""
        logs_data = {
            "logs": {log_id: asdict(log) for log_id, log in self.logs.items()},
            "metadata": {
                "last_saved": time.time(),
                "total_logs": len(self.logs)
            }
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(logs_data, f, indent=2, default=str)
    
    def load_logs(self):
        """Charge les logs introspectifs."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    logs_data = json.load(f)
                
                # Reconstruction des logs
                for log_id, log_data in logs_data.get("logs", {}).items():
                    self.logs[log_id] = IntrospectiveLog(**log_data)
                
            except Exception as e:
                print(f"Erreur lors du chargement des logs: {e}")
                self.logs = {}


class NousEnhanced:
    """Version améliorée de Nous avec graphes de raisonnement et traçabilité complète."""
    
    def __init__(self, db_path: str = "nous_enhanced.db", 
                 index_dir: str = "nous_enhanced_index"):
        self.db_path = db_path
        self.index_dir = index_dir
        self.bus = GlyphBus()
        
        # Composants de traçabilité
        self.reasoning_graph = ReasoningGraph("reasoning_graph.json")
        self.decision_tracker = DecisionLineageTracker("decision_lineage.json")
        self.introspective_logger = IntrospectiveLogger("introspective_logs.json")
        
        # Initialisation
        self._init_db()
        self._init_search_index()
        self._setup_event_handlers()
        
        print("Nous Enhanced initialisé avec traçabilité complète")
    
    def _init_db(self):
        """Initialise la base de données."""
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        SQLModel.metadata.create_all(self.engine)
    
    def _init_search_index(self):
        """Initialise l'index de recherche."""
        class ConceptSchema(SchemaClass):
            concept_id = ID(stored=True, unique=True)
            natural_prompt = TEXT(stored=True)
            concept_type = TEXT(stored=True)
            source = TEXT(stored=True)
        
        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir)
            self.index = create_in(self.index_dir, ConceptSchema)
        else:
            self.index = open_dir(self.index_dir)
    
    def _setup_event_handlers(self):
        """Configure les gestionnaires d'événements pour la traçabilité."""
        self.bus.subscribe("concept_added", self._handle_concept_added)
        self.bus.subscribe("concept_modified", self._handle_concept_modified)
        self.bus.subscribe("reasoning_completed", self._handle_reasoning_completed)
    
    def add_concept_with_reasoning(self, concept: Concept, reasoning_steps: List[Dict[str, Any]], 
                                 agent_id: str) -> Tuple[Concept, str]:
        """Ajoute un concept avec son graphe de raisonnement complet."""
        # Création de la décision
        decision_id = str(uuid.uuid4())
        
        # Création du graphe de raisonnement
        reasoning_node_ids = self.reasoning_graph.create_reasoning_chain(
            concept.concept_id, reasoning_steps, agent_id
        )
        
        # Mise à jour du concept avec les informations de traçabilité
        concept.creation_decision_id = decision_id
        concept.reasoning_node_id = reasoning_node_ids[-1] if reasoning_node_ids else None
        
        # Ajout du concept à la base de données
        with Session(self.engine) as session:
            existing_concept = session.exec(
                select(Concept).where(Concept.concept_id == concept.concept_id)
            ).first()
            
            if existing_concept:
                # Mise à jour du concept existant
                for field, value in concept.dict(exclude={"id"}).items():
                    setattr(existing_concept, field, value)
                session.add(existing_concept)
                session.commit()
                session.refresh(existing_concept)
                result_concept = existing_concept
            else:
                # Ajout du nouveau concept
                session.add(concept)
                session.commit()
                session.refresh(concept)
                result_concept = concept
        
        # Enregistrement de la décision
        decision = DecisionRecord(
            decision_id=decision_id,
            decision_type=DecisionType.CONCEPT_ADDITION,
            agent_id=agent_id,
            timestamp=time.time(),
            input_context={"concept_data": concept.dict(), "reasoning_steps": reasoning_steps},
            decision_rationale=f"Ajout du concept {concept.concept_id} avec raisonnement complet",
            affected_concepts=[concept.concept_id],
            reasoning_path=reasoning_node_ids,
            confidence=0.8,
            metadata={"reasoning_steps_count": len(reasoning_steps)}
        )
        
        self.decision_tracker.record_decision(decision)
        
        # Mise à jour de l'index de recherche
        self._add_to_index(result_concept)
        
        # Publication de l'événement
        self.bus.publish("concept_added_with_reasoning", {
            "concept": result_concept.dict(),
            "decision_id": decision_id,
            "reasoning_nodes": reasoning_node_ids
        })
        
        return result_concept, decision_id
    
    def get_concept_with_lineage(self, concept_id: str) -> Dict[str, Any]:
        """Récupère un concept avec sa lignée décisionnelle complète."""
        # Récupération du concept
        concept = self.get_concept_by_id(concept_id)
        if not concept:
            return {"error": "Concept non trouvé"}
        
        # Récupération de la lignée décisionnelle
        lineage = self.decision_tracker.get_concept_lineage(concept_id)
        
        # Récupération du graphe de raisonnement
        reasoning_nodes = []
        if concept.reasoning_node_id:
            reasoning_nodes = self.reasoning_graph.get_node_ancestors(concept.reasoning_node_id)
        
        return {
            "concept": concept.dict(),
            "decision_lineage": [asdict(decision) for decision in lineage],
            "reasoning_graph": [asdict(node) for node in reasoning_nodes],
            "lineage_length": len(lineage),
            "reasoning_depth": len(reasoning_nodes)
        }
    
    def replay_concept_evolution(self, concept_id: str, 
                               target_timestamp: float) -> Dict[str, Any]:
        """Rejoue l'évolution d'un concept jusqu'à un timestamp donné."""
        return self.decision_tracker.replay_decisions(concept_id, target_timestamp)
    
    def perform_introspective_analysis(self, agent_id: str) -> str:
        """Effectue une analyse introspective pour un agent."""
        # Analyse des patterns de décision
        decision_patterns = self.decision_tracker.analyze_decision_patterns(agent_id)
        
        # Analyse des performances
        performance_metrics = self._calculate_agent_performance(agent_id)
        
        # Génération de la réflexion
        reflection_content = {
            "agent_id": agent_id,
            "analysis_timestamp": time.time(),
            "decision_patterns": decision_patterns,
            "performance_metrics": performance_metrics,
            "recommendations": self._generate_recommendations(decision_patterns, performance_metrics)
        }
        
        # Enregistrement de la réflexion
        log_id = self.introspective_logger.log_reflection(
            agent_id=agent_id,
            reflection_type="self_assessment",
            content=reflection_content
        )
        
        return log_id
    
    def _calculate_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """Calcule les métriques de performance d'un agent."""
        # Récupération des décisions de l'agent
        agent_decisions = [
            decision for decision in self.decision_tracker.decisions.values()
            if decision.agent_id == agent_id
        ]
        
        if not agent_decisions:
            return {"error": "Aucune décision trouvée pour cet agent"}
        
        # Calcul des métriques
        total_decisions = len(agent_decisions)
        avg_confidence = sum(d.confidence for d in agent_decisions) / total_decisions
        
        # Analyse temporelle
        recent_decisions = [
            d for d in agent_decisions
            if time.time() - d.timestamp < 86400  # 24 dernières heures
        ]
        
        return {
            "total_decisions": total_decisions,
            "recent_decisions": len(recent_decisions),
            "avg_confidence": avg_confidence,
            "decision_types": list(set(d.decision_type.value for d in agent_decisions)),
            "activity_trend": "increasing" if len(recent_decisions) > total_decisions * 0.3 else "stable"
        }
    
    def _generate_recommendations(self, decision_patterns: Dict[str, Any], 
                                performance_metrics: Dict[str, Any]) -> List[str]:
        """Génère des recommandations basées sur l'analyse."""
        recommendations = []
        
        # Recommandations basées sur la confiance
        avg_confidence = decision_patterns.get("avg_confidence", 0.7)
        if avg_confidence < 0.6:
            recommendations.append("Améliorer la confiance des décisions via plus de validation")
        
        # Recommandations basées sur l'activité
        activity_trend = performance_metrics.get("activity_trend", "stable")
        if activity_trend == "increasing":
            recommendations.append("Surveiller la qualité avec l'augmentation d'activité")
        
        # Recommandations basées sur la diversité
        decision_types = len(performance_metrics.get("decision_types", []))
        if decision_types < 3:
            recommendations.append("Diversifier les types de décisions pour plus de robustesse")
        
        return recommendations
    
    def _handle_concept_added(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événement pour l'ajout de concept."""
        # Déclenchement d'une réflexion sur la croissance
        self.introspective_logger.trigger_reflection("concept_growth", {
            "agent_id": "system",
            "growth_rate": 0.1,  # Simulation
            "quality_metrics": {"avg_completeness": 0.8}
        })
    
    def _handle_concept_modified(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événement pour la modification de concept."""
        # Log de la modification
        concept_id = event_data.get("concept_id")
        if concept_id:
            self.introspective_logger.log_reflection(
                agent_id="system",
                reflection_type="concept_modification",
                content={
                    "concept_id": concept_id,
                    "modification_type": "update",
                    "timestamp": time.time()
                }
            )
    
    def _handle_reasoning_completed(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événement pour la complétion de raisonnement."""
        # Analyse de la qualité du raisonnement
        reasoning_quality = event_data.get("quality_score", 0.7)
        if reasoning_quality < 0.6:
            self.introspective_logger.trigger_reflection("performance_degradation", {
                "agent_id": event_data.get("agent_id", "unknown"),
                "success_rate": reasoning_quality,
                "component": "reasoning"
            })
    
    # Méthodes héritées de Nous original avec traçabilité
    def add_concept(self, concept: Concept, agent_id: str = "system") -> Concept:
        """Ajoute un concept avec traçabilité basique."""
        reasoning_steps = [
            {
                "type": "concept_validation",
                "description": "Validation basique du concept",
                "confidence": 0.7
            }
        ]
        
        result_concept, _ = self.add_concept_with_reasoning(concept, reasoning_steps, agent_id)
        return result_concept
    
    def get_concept_by_id(self, concept_id: str) -> Optional[Concept]:
        """Récupère un concept par son ID."""
        with Session(self.engine) as session:
            return session.exec(select(Concept).where(Concept.concept_id == concept_id)).first()
    
    def get_all_concepts(self) -> List[Concept]:
        """Récupère tous les concepts."""
        with Session(self.engine) as session:
            return session.exec(select(Concept)).all()
    
    def query_concepts(self, query_string: str) -> List[Concept]:
        """Recherche des concepts via l'index."""
        results = []
        with self.index.searcher() as searcher:
            parser = QueryParser("natural_prompt", schema=self.index.schema)
            query = parser.parse(query_string)
            for hit in searcher.search(query):
                concept_id = hit["concept_id"]
                concept = self.get_concept_by_id(concept_id)
                if concept:
                    results.append(concept)
        return results
    
    def _add_to_index(self, concept: Concept):
        """Ajoute un concept à l'index de recherche."""
        writer = self.index.writer()
        writer.add_document(
            concept_id=concept.concept_id,
            natural_prompt=concept.natural_prompt,
            concept_type=concept.concept_type,
            source=concept.source
        )
        writer.commit()
    
    def get_system_introspection(self) -> Dict[str, Any]:
        """Retourne une introspection complète du système."""
        return {
            "reasoning_graph": {
                "nodes": len(self.reasoning_graph.nodes),
                "edges": len(self.reasoning_graph.edges)
            },
            "decision_lineage": {
                "total_decisions": len(self.decision_tracker.decisions),
                "concept_chains": len(self.decision_tracker.decision_chains)
            },
            "introspective_logs": {
                "total_logs": len(self.introspective_logger.logs),
                "reflection_triggers": len(self.introspective_logger.reflection_triggers)
            },
            "database": {
                "concepts_count": len(self.get_all_concepts())
            }
        }

