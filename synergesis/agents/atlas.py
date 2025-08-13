"""
Agent Atlas - Advanced Visualization and User Interface
Provides comprehensive visualization and interactive dashboard for Synergesis system
"""

import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from synergesis.agents.nous import Nous

logger = logging.getLogger("AtlasAgent")

@dataclass
class VisualizationData:
    """Data structure for visualization"""
    type: str
    title: str
    data: Dict[str, Any]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class AtlasAgent:
    """
    Atlas: Advanced visualization and interactive dashboard system
    """
    
    def __init__(self, nous_instance: Nous):
        self.nous = nous_instance
        self.visualizations = []
        self.dashboard_data = {}
        self.realtime_updates = []
        
    def generate_comprehensive_dashboard(self) -> Dict[str, Any]:
        """Generate comprehensive system dashboard"""
        
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "system_overview": self._generate_system_overview(),
            "concept_network": self._generate_concept_network(),
            "agent_activity": self._generate_agent_activity(),
            "health_metrics": self._generate_health_metrics(),
            "interactive_elements": self._generate_interactive_elements()
        }
        
        self.dashboard_data = dashboard
        return dashboard
    
    def _generate_system_overview(self) -> Dict[str, Any]:
        """Generate high-level system overview"""
        
        concepts = self.nous.get_all_concepts()
        total_concepts = len(concepts)
        
        # System metrics
        overview = {
            "total_concepts": total_concepts,
            "system_health": "operational",
            "uptime": self._calculate_uptime(),
            "last_update": datetime.now().isoformat(),
            "key_indicators": {
                "knowledge_completeness": self._calculate_knowledge_completeness(concepts),
                "network_density": self._calculate_network_density(concepts),
                "concept_diversity": self._calculate_concept_diversity(concepts),
                "growth_rate": self._calculate_growth_rate()
            }
        }
        
        return overview
    
    def _generate_concept_network(self) -> Dict[str, Any]:
        """Generate interactive concept network visualization"""
        
        concepts = self.nous.get_all_concepts()
        
        # Build network structure
        nodes = []
        edges = []
        
        for concept in concepts:
            node = {
                "id": concept["id"],
                "label": concept.get("title", concept.get("natural_prompt", "Unnamed"))[:50],
                "type": concept.get("concept_type", "unknown"),
                "size": self._calculate_node_size(concept),
                "color": self._get_node_color(concept),
                "x": hash(concept["id"]) % 1000,
                "y": hash(concept["id"][::-1]) % 1000,
                "metadata": {
                    "completeness": self._calculate_concept_completeness(concept),
                    "relations_count": len(concept.get("relations", [])),
                    "last_modified": concept.get("updated_at", concept.get("created_at", "unknown"))
                }
            }
            nodes.append(node)
            
            # Add relations as edges
            for relation in concept.get("relations", []):
                edge = {
                    "source": concept["id"],
                    "target": relation.get("target_id", relation.get("concept_id", "")),
                    "type": relation.get("relation_type", "related"),
                    "weight": relation.get("strength", 1.0),
                    "color": self._get_edge_color(relation)
                }
                edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "network_stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "cluster_count": self._identify_clusters(nodes, edges),
                "density": len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0
            }
        }
    
    def _generate_agent_activity(self) -> Dict[str, Any]:
        """Generate agent activity visualization"""
        
        return {
            "activity_timeline": self._generate_activity_timeline(),
            "agent_performance": self._generate_agent_performance(),
            "glyph_emissions": self._generate_glyph_emissions(),
            "system_events": self._generate_system_events()
        }
    
    def _generate_health_metrics(self) -> Dict[str, Any]:
        """Generate health metrics visualization"""
        
        return {
            "system_health": {
                "status": "healthy",
                "score": 85,
                "alerts": [],
                "trends": self._generate_health_trends()
            },
            "performance_metrics": {
                "response_times": [],
                "throughput": 0,
                "error_rates": [],
                "resource_usage": {}
            },
            "quality_indicators": {
                "knowledge_completeness": 0,
                "consistency_score": 0,
                "coverage_metrics": {}
            }
        }
    
    def _generate_interactive_elements(self) -> Dict[str, Any]:
        """Generate interactive dashboard elements"""
        
        return {
            "filters": {
                "time_range": ["last_hour", "last_day", "last_week", "all_time"],
                "concept_types": self._get_concept_types(),
                "agent_types": self._get_agent_types(),
                "severity_levels": ["all", "info", "warning", "error", "critical"]
            },
            "actions": {
                "refresh_data": True,
                "export_visualizations": True,
                "interactive_exploration": True,
                "real_time_updates": True
            },
            "controls": {
                "auto_refresh": {"enabled": True, "interval": 30},
                "notifications": {"enabled": True, "types": ["alerts", "updates", "milestones"]},
                "customization": {"enabled": True, "themes": ["light", "dark", "high_contrast"]}
            }
        }
    
    def _calculate_node_size(self, concept: Dict[str, Any]) -> int:
        """Calculate node size based on concept richness"""
        
        base_size = 10
        
        # Size based on field completeness
        completeness = self._calculate_concept_completeness(concept)
        size = base_size + int(completeness * 20)
        
        # Size based on relations
        relations = len(concept.get("relations", []))
        size += min(relations * 2, 20)
        
        return min(size, 50)
    
    def _get_node_color(self, concept: Dict[str, Any]) -> str:
        """Get node color based on concept type and completeness"""
        
        concept_type = concept.get("concept_type", "unknown")
        completeness = self._calculate_concept_completeness(concept)
        
        color_map = {
            "core": "#FF6B6B",
            "supporting": "#4ECDC4", 
            "context": "#45B7D1",
            "unknown": "#95A5A6"
        }
        
        base_color = color_map.get(concept_type, color_map["unknown"])
        
        # Adjust color intensity based on completeness
        if completeness < 0.5:
            return self._lighten_color(base_color, 0.3)
        elif completeness < 0.8:
            return base_color
        else:
            return self._darken_color(base_color, 0.2)
    
    def _get_edge_color(self, relation: Dict[str, Any]) -> str:
        """Get edge color based on relation type"""
        
        relation_type = relation.get("relation_type", "related")
        
        color_map = {
            "hierarchical": "#E74C3C",
            "associative": "#3498DB",
            "causal": "#2ECC71",
            "temporal": "#F39C12",
            "related": "#95A5A6"
        }
        
        return color_map.get(relation_type, color_map["related"])
    
    def _calculate_concept_completeness(self, concept: Dict[str, Any]) -> float:
        """Calculate concept completeness score"""
        
        required_fields = ["natural_prompt", "concept_type", "description"]
        optional_fields = ["relations", "metadata", "tags"]
        
        score = 0
        total_fields = len(required_fields) + len(optional_fields)
        
        for field in required_fields:
            if field in concept and concept[field]:
                score += 2  # Required fields worth more
        
        for field in optional_fields:
            if field in concept and concept[field]:
                score += 1
        
        return min(score / total_fields, 1.0)
    
    def _calculate_knowledge_completeness(self, concepts: List[Dict[str, Any]]) -> float:
        """Calculate overall knowledge completeness"""
        
        if not concepts:
            return 0.0
        
        total_completeness = sum(self._calculate_concept_completeness(c) for c in concepts)
        return total_completeness / len(concepts)
    
    def _calculate_network_density(self, concepts: List[Dict[str, Any]]) -> float:
        """Calculate network density"""
        
        if not concepts:
            return 0.0
        
        total_relations = sum(len(c.get("relations", [])) for c in concepts)
        max_possible_relations = len(concepts) * (len(concepts) - 1) / 2
        
        return total_relations / max_possible_relations if max_possible_relations > 0 else 0.0
    
    def _calculate_concept_diversity(self, concepts: List[Dict[str, Any]]) -> float:
        """Calculate concept type diversity"""
        
        if not concepts:
            return 0.0
        
        types = set(c.get("concept_type", "unknown") for c in concepts)
        return len(types) / len(concepts)
    
    def _calculate_growth_rate(self) -> float:
        """Calculate concept growth rate"""
        
        # This would require historical data
        return 0.0
    
    def _identify_clusters(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> int:
        """Identify concept clusters"""
        
        # Basic clustering based on connected components
        # This is a simplified version - real implementation would use graph algorithms
        return 1
    
    def _calculate_uptime(self) -> str:
        """Calculate system uptime"""
        
        return "system_active"
    
    def _get_concept_types(self) -> List[str]:
        """Get available concept types"""
        
        return ["core", "supporting", "context", "unknown"]
    
    def _get_agent_types(self) -> List[str]:
        """Get available agent types"""
        
        return ["Aura", "Selene", "Vyra", "Thales", "Hermes", "Chronos", "Atlas", "Morpheus", "Apollo", "Hestia"]
    
    def _lighten_color(self, color: str, factor: float) -> str:
        """Lighten a hex color"""
        
        # Simplified color manipulation
        return color
    
    def _darken_color(self, color: str, factor: float) -> str:
        """Darken a hex color"""
        
        # Simplified color manipulation
        return color
    
    def generate_realtime_update(self) -> Dict[str, Any]:
        """Generate real-time dashboard update"""
        
        return {
            "timestamp": datetime.now().isoformat(),
            "type": "realtime_update",
            "data": {
                "system_overview": self._generate_system_overview(),
                "concept_count": len(self.nous.get_all_concepts()),
                "last_activity": datetime.now().isoformat()
            }
        }
    
    def export_dashboard_data(self, format: str = "json") -> str:
        """Export dashboard data in specified format"""
        
        dashboard = self.generate_comprehensive_dashboard()
        
        if format == "json":
            return json.dumps(dashboard, indent=2, default=str)
        elif format == "html":
            return self._generate_html_dashboard(dashboard)
        else:
            return json.dumps(dashboard, indent=2, default=str)
    
    def _generate_html_dashboard(self, data: Dict[str, Any]) -> str:
        """Generate HTML dashboard"""
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Synergesis Atlas Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                .concept {{ border: 1px solid #ddd; padding: 10px; margin: 5px 0; }}
            </style>
        </head>
        <body>
            <h1>Synergesis Atlas Dashboard</h1>
            <div class="metric">
                <h2>System Overview</h2>
                <p>Total Concepts: {data['system_overview']['total_concepts']}</p>
                <p>System Health: {data['system_overview']['system_health']}</p>
            </div>
        </body>
        </html>
        """
        
        return html
