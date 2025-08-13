"""Synergesis – Agent Chronos
=============================
Agent d'ordonnancement et de réflexion temporelle pour le système Synergesis.
Chronos orchestre l'exécution périodique des tâches et analyse l'évolution
du blackboard cognitif Nous au fil du temps.

Fonctionnalités principales:
- Ordonnancement de tâches périodiques
- Analyse de l'évolution temporelle du blackboard
- Déclenchement réflexif d'actions correctives
- Génération de rapports de santé du système
- Détection d'anomalies et de tendances
"""
from __future__ import annotations

import json
import logging
import sqlite3
import statistics
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
import threading

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field

from glyph_bus import GlyphBus


# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Types de déclencheurs pour les tâches."""
    INTERVAL = "interval"
    CRON = "cron"
    REFLEXIVE = "reflexive"


class HealthStatus(Enum):
    """Statuts de santé du système."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class SystemMetrics:
    """Métriques du système à un moment donné."""
    timestamp: float
    total_concepts: int
    knowledge_gaps: int
    logical_inconsistencies: int
    pending_suggestions: int
    applied_suggestions: int
    average_resonance: float
    average_weight: float
    concept_types_distribution: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit les métriques en dictionnaire."""
        return asdict(self)


@dataclass
class SystemHealthReport:
    """Rapport de santé du système."""
    report_id: str
    timestamp: float
    overall_status: HealthStatus
    metrics: SystemMetrics
    trends: Dict[str, str]  # "increasing", "decreasing", "stable"
    anomalies: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le rapport en dictionnaire."""
        data = asdict(self)
        data['overall_status'] = self.overall_status.value
        return data


@dataclass
class ScheduledTask:
    """Tâche planifiée."""
    task_id: str
    name: str
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    target_agent: str
    target_method: str
    parameters: Dict[str, Any]
    enabled: bool = True
    last_execution: Optional[float] = None
    next_execution: Optional[float] = None
    execution_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la tâche en dictionnaire."""
        data = asdict(self)
        data['trigger_type'] = self.trigger_type.value
        return data


class TimeSeriesAnalyzer:
    """Analyseur de séries temporelles pour les métriques du système."""
    
    def __init__(self, max_history_size: int = 1000):
        self.max_history_size = max_history_size
        self.metrics_history = deque(maxlen=max_history_size)
        self.event_history = deque(maxlen=max_history_size)
    
    def add_metrics(self, metrics: SystemMetrics):
        """Ajoute des métriques à l'historique."""
        self.metrics_history.append(metrics)
        logger.debug(f"Métriques ajoutées: {len(self.metrics_history)} entrées dans l'historique")
    
    def add_event(self, event_type: str, event_data: Dict[str, Any]):
        """Ajoute un événement à l'historique."""
        event = {
            "timestamp": datetime.now().timestamp(),
            "type": event_type,
            "data": event_data
        }
        self.event_history.append(event)
        logger.debug(f"Événement ajouté: {event_type}")
    
    def analyze_trends(self, window_size: int = 10) -> Dict[str, str]:
        """Analyse les tendances sur une fenêtre glissante."""
        if len(self.metrics_history) < window_size:
            return {}
        
        recent_metrics = list(self.metrics_history)[-window_size:]
        trends = {}
        
        # Analyser les tendances pour différentes métriques
        metrics_to_analyze = [
            "total_concepts", "knowledge_gaps", "logical_inconsistencies",
            "pending_suggestions", "average_resonance", "average_weight"
        ]
        
        for metric_name in metrics_to_analyze:
            values = [getattr(m, metric_name) for m in recent_metrics]
            trend = self._calculate_trend(values)
            trends[metric_name] = trend
        
        return trends
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calcule la tendance d'une série de valeurs."""
        if len(values) < 2:
            return "stable"
        
        # Calcul de la pente de régression linéaire simple
        n = len(values)
        x = list(range(n))
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        # Seuils pour déterminer la tendance
        threshold = 0.1
        
        if slope > threshold:
            return "increasing"
        elif slope < -threshold:
            return "decreasing"
        else:
            return "stable"
    
    def detect_anomalies(self) -> List[str]:
        """Détecte les anomalies dans les métriques."""
        anomalies = []
        
        if len(self.metrics_history) < 5:
            return anomalies
        
        recent_metrics = list(self.metrics_history)[-5:]
        
        # Détection d'anomalies simples
        latest = recent_metrics[-1]
        
        # Anomalie: augmentation soudaine des lacunes
        gap_values = [m.knowledge_gaps for m in recent_metrics]
        if len(gap_values) >= 3:
            recent_avg = statistics.mean(gap_values[-3:])
            if latest.knowledge_gaps > recent_avg * 2:
                anomalies.append(f"Augmentation soudaine des lacunes de connaissance: {latest.knowledge_gaps}")
        
        # Anomalie: augmentation soudaine des incohérences
        inconsistency_values = [m.logical_inconsistencies for m in recent_metrics]
        if len(inconsistency_values) >= 3:
            recent_avg = statistics.mean(inconsistency_values[-3:])
            if latest.logical_inconsistencies > recent_avg * 2:
                anomalies.append(f"Augmentation soudaine des incohérences: {latest.logical_inconsistencies}")
        
        # Anomalie: baisse significative de la résonance moyenne
        resonance_values = [m.average_resonance for m in recent_metrics if m.average_resonance > 0]
        if len(resonance_values) >= 3:
            recent_avg = statistics.mean(resonance_values[-3:])
            if latest.average_resonance < recent_avg * 0.7:
                anomalies.append(f"Baisse significative de la résonance moyenne: {latest.average_resonance:.2f}")
        
        return anomalies
    
    def get_stagnant_concepts(self, stagnation_threshold_hours: int = 24) -> List[str]:
        """Identifie les concepts stagnants basés sur l'historique des événements."""
        stagnant_concepts = []
        current_time = datetime.now().timestamp()
        threshold_time = current_time - (stagnation_threshold_hours * 3600)
        
        # Analyser les événements concept_changed récents
        recent_changes = {}
        for event in self.event_history:
            if (event["type"] == "concept_changed" and 
                event["timestamp"] > threshold_time):
                concept_id = event["data"].get("concept_id")
                if concept_id:
                    recent_changes[concept_id] = event["timestamp"]
        
        # Pour l'instant, retourner une liste vide car nous n'avons pas accès
        # à la liste complète des concepts ici
        return stagnant_concepts


class ReflexiveTrigger:
    """Déclencheur réflexif pour les actions automatiques."""
    
    def __init__(self, nous_api_url: str, api_token: str):
        self.nous_api_url = nous_api_url
        self.api_token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self.rules = self._initialize_rules()
    
    def _initialize_rules(self) -> List[Dict[str, Any]]:
        """Initialise les règles de déclenchement réflexif."""
        return [
            {
                "name": "high_knowledge_gaps",
                "condition": lambda metrics: metrics.knowledge_gaps > 10,
                "action": "trigger_vyra_high_priority",
                "description": "Déclencher Vyra avec haute priorité si trop de lacunes"
            },
            {
                "name": "high_inconsistencies",
                "condition": lambda metrics: metrics.logical_inconsistencies > 5,
                "action": "trigger_thales_deep_analysis",
                "description": "Déclencher une analyse approfondie de Thales"
            },
            {
                "name": "low_average_resonance",
                "condition": lambda metrics: metrics.average_resonance < 0.3,
                "action": "trigger_apollo_content_generation",
                "description": "Déclencher Apollo pour générer du contenu"
            },
            {
                "name": "many_pending_suggestions",
                "condition": lambda metrics: metrics.pending_suggestions > 20,
                "action": "trigger_hermes_batch_processing",
                "description": "Déclencher le traitement en lot par Hermes"
            }
        ]
    
    def evaluate_rules(self, metrics: SystemMetrics) -> List[str]:
        """Évalue les règles et retourne les actions à déclencher."""
        triggered_actions = []
        
        for rule in self.rules:
            try:
                if rule["condition"](metrics):
                    triggered_actions.append(rule["action"])
                    logger.info(f"Règle déclenchée: {rule['name']} -> {rule['action']}")
            except Exception as e:
                logger.error(f"Erreur lors de l'évaluation de la règle {rule['name']}: {e}")
        
        return triggered_actions
    
    def execute_action(self, action: str) -> bool:
        """Exécute une action déclenchée."""
        try:
            if action == "trigger_vyra_high_priority":
                return self._trigger_vyra_high_priority()
            elif action == "trigger_thales_deep_analysis":
                return self._trigger_thales_deep_analysis()
            elif action == "trigger_apollo_content_generation":
                return self._trigger_apollo_content_generation()
            elif action == "trigger_hermes_batch_processing":
                return self._trigger_hermes_batch_processing()
            else:
                logger.warning(f"Action inconnue: {action}")
                return False
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de l'action {action}: {e}")
            return False
    
    def _trigger_vyra_high_priority(self) -> bool:
        """Déclenche Vyra avec haute priorité."""
        # Pour l'instant, c'est un placeholder
        logger.info("Déclenchement de Vyra avec haute priorité")
        return True
    
    def _trigger_thales_deep_analysis(self) -> bool:
        """Déclenche une analyse approfondie de Thales."""
        # Pour l'instant, c'est un placeholder
        logger.info("Déclenchement d'une analyse approfondie de Thales")
        return True
    
    def _trigger_apollo_content_generation(self) -> bool:
        """Déclenche la génération de contenu par Apollo."""
        # Pour l'instant, c'est un placeholder
        logger.info("Déclenchement de la génération de contenu par Apollo")
        return True
    
    def _trigger_hermes_batch_processing(self) -> bool:
        """Déclenche le traitement en lot par Hermes."""
        # Pour l'instant, c'est un placeholder
        logger.info("Déclenchement du traitement en lot par Hermes")
        return True


class Chronos:
    """Agent Chronos - Ordonnancement et Réflexion Temporelle."""
    
    def __init__(self, nous_api_url: str = "http://localhost:8001",
                 api_token: str = "synergesis_nous_token_2025",
                 db_path: str = "chronos.db"):
        self.nous_api_url = nous_api_url
        self.api_token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self.db_path = db_path
        
        # Composants internes
        self.scheduler = BackgroundScheduler()
        self.time_series_analyzer = TimeSeriesAnalyzer()
        self.reflexive_trigger = ReflexiveTrigger(nous_api_url, api_token)
        self.bus = GlyphBus()
        
        # État interne
        self.running = False
        self.scheduled_tasks = {}
        
        # Initialiser la base de données
        self._init_database()
        
        # S'abonner aux événements du bus
        self._subscribe_to_events()
        
        logger.info("Agent Chronos initialisé")
    
    def _init_database(self):
        """Initialise la base de données SQLite pour la persistance."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table pour les tâches planifiées
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                trigger_config TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                target_method TEXT NOT NULL,
                parameters TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                last_execution REAL,
                execution_count INTEGER DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        
        # Table pour l'historique des métriques
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                total_concepts INTEGER,
                knowledge_gaps INTEGER,
                logical_inconsistencies INTEGER,
                pending_suggestions INTEGER,
                applied_suggestions INTEGER,
                average_resonance REAL,
                average_weight REAL,
                concept_types_distribution TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Base de données Chronos initialisée")
    
    def _subscribe_to_events(self):
        """S'abonne aux événements du GlyphBus."""
        self.bus.subscribe("knowledge_gap", self._on_knowledge_gap)
        self.bus.subscribe("logical_inconsistency", self._on_logical_inconsistency)
        self.bus.subscribe("creative_suggestion", self._on_creative_suggestion)
        self.bus.subscribe("suggestion_applied", self._on_suggestion_applied)
        self.bus.subscribe("concept_changed", self._on_concept_changed)
    
    def _on_knowledge_gap(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événements pour les lacunes de connaissance."""
        self.time_series_analyzer.add_event("knowledge_gap", event_data)
    
    def _on_logical_inconsistency(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événements pour les incohérences logiques."""
        self.time_series_analyzer.add_event("logical_inconsistency", event_data)
    
    def _on_creative_suggestion(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événements pour les suggestions créatives."""
        self.time_series_analyzer.add_event("creative_suggestion", event_data)
    
    def _on_suggestion_applied(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événements pour les suggestions appliquées."""
        self.time_series_analyzer.add_event("suggestion_applied", event_data)
    
    def _on_concept_changed(self, event_data: Dict[str, Any]):
        """Gestionnaire d'événements pour les changements de concepts."""
        self.time_series_analyzer.add_event("concept_changed", event_data)
    
    def start(self):
        """Démarre l'agent Chronos."""
        if self.running:
            logger.warning("Chronos est déjà en cours d'exécution")
            return
        
        self.scheduler.start()
        self.running = True
        
        # Charger les tâches planifiées depuis la base de données
        self._load_scheduled_tasks()
        
        # Planifier la collecte périodique de métriques
        self._schedule_metrics_collection()
        
        logger.info("Agent Chronos démarré")
    
    def stop(self):
        """Arrête l'agent Chronos."""
        if not self.running:
            logger.warning("Chronos n'est pas en cours d'exécution")
            return
        
        self.scheduler.shutdown()
        self.running = False
        logger.info("Agent Chronos arrêté")
    
    def _load_scheduled_tasks(self):
        """Charge les tâches planifiées depuis la base de données."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM scheduled_tasks WHERE enabled = 1")
        rows = cursor.fetchall()
        
        for row in rows:
            task_id, name, trigger_type, trigger_config, target_agent, target_method, parameters, enabled, last_execution, execution_count, created_at = row
            
            task = ScheduledTask(
                task_id=task_id,
                name=name,
                trigger_type=TriggerType(trigger_type),
                trigger_config=json.loads(trigger_config),
                target_agent=target_agent,
                target_method=target_method,
                parameters=json.loads(parameters),
                enabled=bool(enabled),
                last_execution=last_execution,
                execution_count=execution_count
            )
            
            self._add_task_to_scheduler(task)
            self.scheduled_tasks[task_id] = task
        
        conn.close()
        logger.info(f"Chargé {len(self.scheduled_tasks)} tâches planifiées")
    
    def _add_task_to_scheduler(self, task: ScheduledTask):
        """Ajoute une tâche au planificateur."""
        if task.trigger_type == TriggerType.INTERVAL:
            trigger = IntervalTrigger(**task.trigger_config)
        elif task.trigger_type == TriggerType.CRON:
            trigger = CronTrigger(**task.trigger_config)
        else:
            logger.error(f"Type de déclencheur non supporté: {task.trigger_type}")
            return
        
        self.scheduler.add_job(
            func=self._execute_scheduled_task,
            trigger=trigger,
            args=[task.task_id],
            id=task.task_id,
            name=task.name
        )
    
    def _execute_scheduled_task(self, task_id: str):
        """Exécute une tâche planifiée."""
        task = self.scheduled_tasks.get(task_id)
        if not task:
            logger.error(f"Tâche introuvable: {task_id}")
            return
        
        logger.info(f"Exécution de la tâche planifiée: {task.name}")
        
        try:
            # Pour l'instant, c'est un placeholder
            # Dans une implémentation complète, cela appellerait réellement les agents
            success = True
            
            # Mettre à jour les statistiques de la tâche
            task.last_execution = datetime.now().timestamp()
            task.execution_count += 1
            
            # Sauvegarder en base de données
            self._update_task_execution_stats(task_id, task.last_execution, task.execution_count)
            
            logger.info(f"Tâche {task.name} exécutée avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la tâche {task.name}: {e}")
    
    def _update_task_execution_stats(self, task_id: str, last_execution: float, execution_count: int):
        """Met à jour les statistiques d'exécution d'une tâche."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE scheduled_tasks 
            SET last_execution = ?, execution_count = ?
            WHERE task_id = ?
        """, (last_execution, execution_count, task_id))
        
        conn.commit()
        conn.close()
    
    def _schedule_metrics_collection(self):
        """Planifie la collecte périodique de métriques."""
        # Collecter les métriques toutes les 5 minutes
        self.scheduler.add_job(
            func=self._collect_system_metrics,
            trigger=IntervalTrigger(minutes=5),
            id="metrics_collection",
            name="Collecte de métriques système"
        )
        
        # Générer un rapport de santé toutes les heures
        self.scheduler.add_job(
            func=self._generate_health_report,
            trigger=IntervalTrigger(hours=1),
            id="health_report_generation",
            name="Génération de rapport de santé"
        )
    
    def _collect_system_metrics(self):
        """Collecte les métriques du système."""
        try:
            logger.info("Collecte des métriques système")
            
            # Récupérer tous les concepts
            response = requests.get(f"{self.nous_api_url}/concepts", headers=self.headers)
            if response.status_code != 200:
                logger.error(f"Erreur lors de la récupération des concepts: {response.status_code}")
                return
            
            concepts = response.json()
            
            # Calculer les métriques
            total_concepts = len(concepts)
            
            # Calculer la résonance et le poids moyens
            resonances = [c.get("resonance", 0) for c in concepts if c.get("resonance") is not None]
            weights = [c.get("weight", 0) for c in concepts if c.get("weight") is not None]
            
            average_resonance = statistics.mean(resonances) if resonances else 0.0
            average_weight = statistics.mean(weights) if weights else 0.0
            
            # Distribution des types de concepts
            concept_types_distribution = defaultdict(int)
            for concept in concepts:
                concept_type = concept.get("concept_type", "UNKNOWN")
                concept_types_distribution[concept_type] += 1
            
            # Pour l'instant, utiliser des valeurs par défaut pour les autres métriques
            # Dans une implémentation complète, ces valeurs seraient récupérées depuis les autres agents
            knowledge_gaps = 0
            logical_inconsistencies = 0
            pending_suggestions = 0
            applied_suggestions = 0
            
            metrics = SystemMetrics(
                timestamp=datetime.now().timestamp(),
                total_concepts=total_concepts,
                knowledge_gaps=knowledge_gaps,
                logical_inconsistencies=logical_inconsistencies,
                pending_suggestions=pending_suggestions,
                applied_suggestions=applied_suggestions,
                average_resonance=average_resonance,
                average_weight=average_weight,
                concept_types_distribution=dict(concept_types_distribution)
            )
            
            # Ajouter aux analyses de séries temporelles
            self.time_series_analyzer.add_metrics(metrics)
            
            # Sauvegarder en base de données
            self._save_metrics_to_db(metrics)
            
            # Évaluer les règles réflexives
            triggered_actions = self.reflexive_trigger.evaluate_rules(metrics)
            for action in triggered_actions:
                self.reflexive_trigger.execute_action(action)
            
            logger.info(f"Métriques collectées: {total_concepts} concepts, résonance moyenne: {average_resonance:.2f}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des métriques: {e}")
    
    def _save_metrics_to_db(self, metrics: SystemMetrics):
        """Sauvegarde les métriques en base de données."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO metrics_history (
                timestamp, total_concepts, knowledge_gaps, logical_inconsistencies,
                pending_suggestions, applied_suggestions, average_resonance,
                average_weight, concept_types_distribution
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metrics.timestamp, metrics.total_concepts, metrics.knowledge_gaps,
            metrics.logical_inconsistencies, metrics.pending_suggestions,
            metrics.applied_suggestions, metrics.average_resonance,
            metrics.average_weight, json.dumps(metrics.concept_types_distribution)
        ))
        
        conn.commit()
        conn.close()
    
    def _generate_health_report(self):
        """Génère un rapport de santé du système."""
        try:
            logger.info("Génération du rapport de santé système")
            
            if not self.time_series_analyzer.metrics_history:
                logger.warning("Aucune métrique disponible pour le rapport de santé")
                return
            
            latest_metrics = self.time_series_analyzer.metrics_history[-1]
            trends = self.time_series_analyzer.analyze_trends()
            anomalies = self.time_series_analyzer.detect_anomalies()
            
            # Déterminer le statut global de santé
            overall_status = self._determine_overall_health_status(latest_metrics, anomalies)
            
            # Générer des recommandations
            recommendations = self._generate_recommendations(latest_metrics, trends, anomalies)
            
            report = SystemHealthReport(
                report_id=str(uuid.uuid4()),
                timestamp=datetime.now().timestamp(),
                overall_status=overall_status,
                metrics=latest_metrics,
                trends=trends,
                anomalies=anomalies,
                recommendations=recommendations
            )
            
            # Publier le rapport sur le bus
            self.bus.publish("system_health_report", report.to_dict())
            
            logger.info(f"Rapport de santé généré: statut {overall_status.value}, {len(anomalies)} anomalies détectées")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport de santé: {e}")
    
    def _determine_overall_health_status(self, metrics: SystemMetrics, anomalies: List[str]) -> HealthStatus:
        """Détermine le statut global de santé du système."""
        if len(anomalies) > 2:
            return HealthStatus.CRITICAL
        elif len(anomalies) > 0 or metrics.logical_inconsistencies > 5:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def _generate_recommendations(self, metrics: SystemMetrics, trends: Dict[str, str], anomalies: List[str]) -> List[str]:
        """Génère des recommandations basées sur l'état du système."""
        recommendations = []
        
        if metrics.knowledge_gaps > 10:
            recommendations.append("Considérer l'exécution de Vyra pour générer plus de suggestions")
        
        if metrics.logical_inconsistencies > 5:
            recommendations.append("Exécuter Thales pour résoudre les incohérences logiques")
        
        if metrics.average_resonance < 0.3:
            recommendations.append("Envisager l'enrichissement du contenu avec Apollo")
        
        if trends.get("total_concepts") == "decreasing":
            recommendations.append("Vérifier les processus d'ingestion de données avec Hestia")
        
        if len(anomalies) > 0:
            recommendations.append("Investiguer les anomalies détectées dans le système")
        
        return recommendations
    
    def add_scheduled_task(self, task: ScheduledTask) -> bool:
        """Ajoute une nouvelle tâche planifiée."""
        try:
            # Sauvegarder en base de données
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO scheduled_tasks (
                    task_id, name, trigger_type, trigger_config, target_agent,
                    target_method, parameters, enabled, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id, task.name, task.trigger_type.value,
                json.dumps(task.trigger_config), task.target_agent,
                task.target_method, json.dumps(task.parameters),
                task.enabled, datetime.now().timestamp()
            ))
            
            conn.commit()
            conn.close()
            
            # Ajouter au planificateur si Chronos est en cours d'exécution
            if self.running:
                self._add_task_to_scheduler(task)
            
            self.scheduled_tasks[task.task_id] = task
            logger.info(f"Tâche planifiée ajoutée: {task.name}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de la tâche planifiée: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut de l'agent Chronos."""
        return {
            "running": self.running,
            "scheduled_tasks_count": len(self.scheduled_tasks),
            "metrics_history_size": len(self.time_series_analyzer.metrics_history),
            "event_history_size": len(self.time_series_analyzer.event_history),
            "scheduler_jobs": len(self.scheduler.get_jobs()) if self.running else 0
        }


if __name__ == "__main__":
    # Exemple d'utilisation
    chronos = Chronos()
    chronos.start()
    
    try:
        # Ajouter une tâche d'exemple
        task = ScheduledTask(
            task_id="test_task",
            name="Tâche de test",
            trigger_type=TriggerType.INTERVAL,
            trigger_config={"minutes": 1},
            target_agent="selene",
            target_method="check_gaps",
            parameters={}
        )
        
        chronos.add_scheduled_task(task)
        
        # Attendre un peu
        time.sleep(5)
        
        # Afficher le statut
        print("Statut de Chronos:", chronos.get_status())
        
    finally:
        chronos.stop()

