"""
Agent Chronos - Temporal Orchestration and System Health Monitoring
Advanced scheduling and reflexive system health analysis
"""

import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from synergesis.agents.nous import Nous

logger = logging.getLogger("ChronosAgent")

@dataclass
class HealthMetric:
    """Health metric data structure"""
    name: str
    value: float
    threshold: float
    status: str  # "healthy", "warning", "critical"
    timestamp: datetime

class ChronosAgent:
    """
    Chronos: Advanced temporal orchestration and system health monitoring
    """
    
    def __init__(self, nous_instance: Nous):
        self.nous = nous_instance
        self.health_history = []
        self.scheduled_tasks = []
        self.system_start_time = datetime.now()
        self.metrics_cache = {}
        
    def analyze_system_health(self) -> Dict[str, Any]:
        """Comprehensive system health analysis"""
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.system_start_time).total_seconds(),
            "overall_health": "healthy",
            "metrics": {},
            "alerts": [],
            "recommendations": []
        }
        
        # Analyze Nous blackboard health
        blackboard_health = self._analyze_blackboard_health()
        health_report["metrics"]["blackboard"] = blackboard_health
        
        # Analyze concept evolution
        evolution_health = self._analyze_concept_evolution()
        health_report["metrics"]["evolution"] = evolution_health
        
        # Analyze agent activity patterns
        activity_health = self._analyze_agent_activity()
        health_report["metrics"]["activity"] = activity_health
        
        # Generate alerts and recommendations
        health_report["alerts"] = self._generate_alerts(health_report["metrics"])
        health_report["recommendations"] = self._generate_recommendations(health_report["metrics"])
        
        # Determine overall health
        critical_alerts = [alert for alert in health_report["alerts"] if alert["severity"] == "critical"]
        warning_alerts = [alert for alert in health_report["alerts"] if alert["severity"] == "warning"]
        
        if critical_alerts:
            health_report["overall_health"] = "critical"
        elif warning_alerts:
            health_report["overall_health"] = "warning"
        else:
            health_report["overall_health"] = "healthy"
        
        # Cache the report
        self.health_history.append(health_report)
        
        # Keep only last 100 reports
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        return health_report
    
    def _analyze_blackboard_health(self) -> Dict[str, Any]:
        """Analyze Nous blackboard health"""
        
        concepts = self.nous.get_all_concepts()
        total_concepts = len(concepts)
        
        # Analyze concept completeness
        complete_concepts = 0
        incomplete_concepts = 0
        concepts_with_relations = 0
        concepts_with_descriptions = 0
        
        for concept in concepts:
            is_complete = True
            
            # Check for required fields
            required_fields = ["natural_prompt", "concept_type", "description"]
            for field in required_fields:
                if field not in concept or not concept[field]:
                    is_complete = False
                    break
            
            if is_complete:
                complete_concepts += 1
            else:
                incomplete_concepts += 1
            
            if "relations" in concept and concept["relations"]:
                concepts_with_relations += 1
            
            if "description" in concept and concept["description"]:
                concepts_with_descriptions += 1
        
        return {
            "total_concepts": total_concepts,
            "complete_concepts": complete_concepts,
            "incomplete_concepts": incomplete_concepts,
            "concepts_with_relations": concepts_with_relations,
            "concepts_with_descriptions": concepts_with_descriptions,
            "completeness_ratio": complete_concepts / total_concepts if total_concepts > 0 else 0,
            "relation_coverage": concepts_with_relations / total_concepts if total_concepts > 0 else 0
        }
    
    def _analyze_concept_evolution(self) -> Dict[str, Any]:
        """Analyze how concepts have evolved over time"""
        
        concepts = self.nous.get_all_concepts()
        
        # Analyze timestamps
        timestamps = []
        for concept in concepts:
            if "created_at" in concept:
                try:
                    ts = datetime.fromisoformat(concept["created_at"])
                    timestamps.append(ts)
                except:
                    pass
        
        # Evolution metrics
        evolution = {
            "total_timestamps": len(timestamps),
            "oldest_concept": min(timestamps) if timestamps else None,
            "newest_concept": max(timestamps) if timestamps else None,
            "creation_frequency": self._calculate_creation_frequency(timestamps),
            "modification_patterns": self._analyze_modifications(concepts)
        }
        
        return evolution
    
    def _calculate_creation_frequency(self, timestamps: List[datetime]) -> Dict[str, float]:
        """Calculate concept creation frequency"""
        if not timestamps:
            return {"daily": 0, "weekly": 0, "monthly": 0}
        
        now = datetime.now()
        daily_count = sum(1 for ts in timestamps if (now - ts).days <= 1)
        weekly_count = sum(1 for ts in timestamps if (now - ts).days <= 7)
        monthly_count = sum(1 for ts in timestamps if (now - ts).days <= 30)
        
        return {
            "daily": daily_count,
            "weekly": weekly_count,
            "monthly": monthly_count
        }
    
    def _analyze_modifications(self, concepts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze modification patterns"""
        
        modifications = {
            "total_modifications": 0,
            "recent_modifications": 0,
            "modification_frequency": 0
        }
        
        # This would require tracking modification history
        # For now, return basic metrics
        return modifications
    
    def _analyze_agent_activity(self) -> Dict[str, Any]:
        """Analyze agent activity patterns"""
        
        return {
            "last_activity": datetime.now().isoformat(),
            "activity_level": "moderate",
            "agent_response_times": [],
            "error_rates": [],
            "throughput": 0
        }
    
    def _generate_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate health alerts based on metrics"""
        
        alerts = []
        
        # Blackboard health alerts
        blackboard = metrics.get("blackboard", {})
        completeness = blackboard.get("completeness_ratio", 0)
        
        if completeness < 0.5:
            alerts.append({
                "severity": "warning",
                "type": "low_completeness",
                "message": f"Concept completeness below 50% ({completeness:.1%})",
                "metric": "completeness_ratio",
                "value": completeness
            })
        
        if completeness < 0.2:
            alerts.append({
                "severity": "critical",
                "type": "very_low_completeness",
                "message": f"Concept completeness critically low ({completeness:.1%})",
                "metric": "completeness_ratio",
                "value": completeness
            })
        
        return alerts
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate system improvement recommendations"""
        
        recommendations = []
        
        blackboard = metrics.get("blackboard", {})
        completeness = blackboard.get("completeness_ratio", 0)
        
        if completeness < 0.8:
            recommendations.append({
                "type": "enrichment",
                "priority": "high",
                "description": "Trigger creative agents (Vyra) to enrich incomplete concepts",
                "target": "incomplete_concepts"
            })
        
        if blackboard.get("concepts_with_relations", 0) < blackboard.get("total_concepts", 1) * 0.5:
            recommendations.append({
                "type": "relation_enrichment",
                "priority": "medium",
                "description": "Add more contextual relations between concepts",
                "target": "relation_coverage"
            })
        
        return recommendations
    
    def schedule_task(self, task_name: str, frequency_minutes: int, task_config: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a new recurring task"""
        
        task = {
            "name": task_name,
            "frequency_minutes": frequency_minutes,
            "config": task_config,
            "last_run": None,
            "next_run": datetime.now() + timedelta(minutes=frequency_minutes),
            "run_count": 0
        }
        
        self.scheduled_tasks.append(task)
        
        return {
            "status": "scheduled",
            "task": task_name,
            "frequency": f"{frequency_minutes} minutes"
        }
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get comprehensive system summary"""
        
        health = self.analyze_system_health()
        
        return {
            "system_uptime": (datetime.now() - self.system_start_time).total_seconds(),
            "health_status": health["overall_health"],
            "total_scheduled_tasks": len(self.scheduled_tasks),
            "health_reports_count": len(self.health_history),
            "latest_health": health,
            "summary": {
                "total_concepts": health["metrics"]["blackboard"]["total_concepts"],
                "system_completeness": health["metrics"]["blackboard"]["completeness_ratio"],
                "active_alerts": len(health["alerts"]),
                "pending_recommendations": len(health["recommendations"])
            }
        }
