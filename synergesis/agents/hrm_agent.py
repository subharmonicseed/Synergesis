"""
HRMControllerAgent
Meta-controller that uses the Hierarchical Reasoning Model (HRM)
to decide which Synergesis agents to invoke and in what sequence.
"""
import logging
import json
import torch
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("HRMControllerAgent")

class HRMControllerAgent:
    """
    Wrapper around the HRM dual-module reasoning system.
    High-level module chooses agent sequences; low-level executes.
    """
    
    def __init__(self, agent_registry: Dict[str, Any], glyph_bus: List[Dict[str, Any]]):
        self.agent_registry = agent_registry
        self.glyph_bus = glyph_bus
        self.action_log = []
        
        # Load HRM model (placeholder for now)
        self.hrm_model = self._load_hrm_model()
        
    def _load_hrm_model(self):
        """Load HRM model from cloned repo"""
        try:
            # Placeholder for actual HRM model loading
            logger.info("HRM model placeholder loaded")
            return {"status": "placeholder"}
        except Exception as e:
            logger.warning(f"HRM model load failed: {e}")
            return None
    
    def decide_agent_sequence(self, current_glyphs: List[Dict[str, Any]]) -> List[str]:
        """
        Use HRM to decide which agents to run based on glyph state.
        Returns ordered list of agent names to invoke.
        """
        if not self.hrm_model:
            # Fallback to simple heuristic
            return self._fallback_sequence(current_glyphs)
        
        # Prepare input for HRM
        context = self._prepare_hrm_input(current_glyphs)
        
        # Simulate HRM decision
        # In real implementation, this would use actual HRM inference
        sequence = self._simulate_hrm_decision(context)
        
        logger.info(f"HRM decided sequence: {sequence}")
        return sequence
    
    def _prepare_hrm_input(self, glyphs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare glyph state for HRM processing"""
        return {
            "glyph_count": len(glyphs),
            "types": [g.get("type") for g in glyphs[-10:]],
            "timestamps": [g.get("timestamp") for g in glyphs[-10:]],
            "contradictions": self._detect_contradictions(glyphs),
            "knowledge_gaps": self._detect_knowledge_gaps(glyphs)
        }
    
    def _detect_contradictions(self, glyphs: List[Dict[str, Any]]) -> List[str]:
        """Detect logical contradictions in glyphs"""
        # Simple contradiction detection
        contradictions = []
        content_list = [g.get("content", "") for g in glyphs]
        
        # Look for conflicting statements
        for i, c1 in enumerate(content_list):
            for j, c2 in enumerate(content_list[i+1:], i+1):
                if self._is_contradictory(c1, c2):
                    contradictions.append(f"Glyph {i} vs {j}")
        
        return contradictions
    
    def _detect_knowledge_gaps(self, glyphs: List[Dict[str, Any]]) -> List[str]:
        """Detect missing knowledge areas"""
        # Simple gap detection based on content analysis
        gaps = []
        
        # Check for missing fields in concepts
        concept_glyphs = [g for g in glyphs if g.get("type") == "concept"]
        for concept in concept_glyphs:
            if not concept.get("description"):
                gaps.append("missing_description")
            if not concept.get("relations"):
                gaps.append("missing_relations")
        
        return gaps
    
    def _is_contradictory(self, text1: str, text2: str) -> bool:
        """Simple contradiction detection"""
        # Placeholder for contradiction logic
        return "not" in text1.lower() and text1.lower().replace("not", "") == text2.lower()
    
    def _simulate_hrm_decision(self, context: Dict[str, Any]) -> List[str]:
        """Simulate HRM decision-making"""
        sequence = []
        
        # Priority-based agent selection
        if context["contradictions"]:
            sequence.append("thales")
        
        if context["knowledge_gaps"]:
            sequence.extend(["deepresearch", "vyra"])
        
        # Always include creative agents
        sequence.extend(["selene", "lumen"])
        
        # Add monitoring
        sequence.append("aura")
        
        return sequence
    
    def _fallback_sequence(self, glyphs: List[Dict[str, Any]]) -> List[str]:
        """Fallback sequence when HRM not available"""
        return ["thales", "vyra", "selene", "lumen", "aura"]
    
    def execute_sequence(self, sequence: List[str]) -> Dict[str, Any]:
        """Execute the decided agent sequence"""
        results = {
            "sequence": sequence,
            "executions": [],
            "timestamp": datetime.now().isoformat()
        }
        
        for agent_name in sequence:
            if agent_name in self.agent_registry:
                try:
                    # Execute agent
                    agent = self.agent_registry[agent_name]
                    result = self._execute_agent(agent, agent_name)
                    results["executions"].append({
                        "agent": agent_name,
                        "result": result,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error executing {agent_name}: {e}")
        
        return results
    
    def _execute_agent(self, agent, agent_name: str) -> Dict[str, Any]:
        """Execute individual agent"""
        # Placeholder for agent execution
        return {
            "status": "success",
            "action": f"{agent_name}_executed",
            "glyphs_generated": 1
        }
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of HRM controller activity"""
        return {
            "total_sequences": len(self.action_log),
            "last_sequence": self.action_log[-1] if self.action_log else None,
            "recent_actions": self.action_log[-5:] if len(self.action_log) > 5 else self.action_log
        }
