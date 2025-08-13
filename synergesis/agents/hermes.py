"""
Agent Hermes - Creative Suggestion Executor
Transforms Vyra's creative suggestions into concrete Nous concept updates
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from synergesis.agents.nous import Nous
from typing import Dict, Any, List

# Define CreativeSuggestion locally to avoid import issues
class CreativeSuggestion:
    """A creative suggestion for concept enrichment."""
    def __init__(self, concept_id: str, suggestion_type: str, priority: str = "medium", metadata: Dict[str, Any] = {}):
        self.concept_id = concept_id
        self.suggestion_type = suggestion_type
        self.priority = priority
        self.metadata = metadata
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "suggestion_type": self.suggestion_type,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

logger = logging.getLogger("HermesAgent")

class HermesAgent:
    """
    Hermes: The creative executor that transforms Vyra's suggestions into Nous actions
    """
    
    def __init__(self, nous_instance: Nous):
        self.nous = nous_instance
        self.action_log = []
        self.validation_queue = []
        
    def execute_suggestion(self, suggestion: CreativeSuggestion) -> Dict[str, Any]:
        """Execute a creative suggestion on Nous concepts"""
        
        try:
            logger.info(f"Hermes executing suggestion: {suggestion.suggestion_type} for concept {suggestion.concept_id}")
            
            # Get current concept
            concept = self.nous.get_concept_by_id(suggestion.concept_id)
            if not concept:
                return {
                    "status": "error",
                    "message": f"Concept {suggestion.concept_id} not found",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Execute based on suggestion type
            result = self._execute_by_type(suggestion, concept)
            
            # Log the action
            self._log_action(suggestion, result)
            
            # Queue for validation
            if result["status"] == "success":
                self.validation_queue.append({
                    "concept_id": suggestion.concept_id,
                    "suggestion": suggestion,
                    "result": result,
                    "timestamp": datetime.now()
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Hermes execution error: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _execute_by_type(self, suggestion: CreativeSuggestion, concept: Dict[str, Any]) -> Dict[str, Any]:
        """Execute suggestion based on type"""
        
        suggestion_type = suggestion.suggestion_type
        metadata = suggestion.metadata or {}
        
        if suggestion_type == "ENRICH_CONCEPT_PROMPT":
            return self._enrich_prompt(concept, metadata)
        elif suggestion_type == "COMPLETE_MISSING_FIELD":
            return self._complete_field(concept, metadata)
        elif suggestion_type == "CLARIFY_VAGUE_DESCRIPTION":
            return self._clarify_description(concept, metadata)
        elif suggestion_type == "ADD_CONTEXTUAL_RELATIONS":
            return self._add_relations(concept, metadata)
        else:
            return {
                "status": "error",
                "message": f"Unknown suggestion type: {suggestion_type}",
                "concept_id": concept.get("id")
            }
    
    def _enrich_prompt(self, concept: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich concept's natural prompt"""
        new_prompt = metadata.get("new_prompt", "")
        if new_prompt:
            concept["natural_prompt"] = new_prompt
            self.nous.update_concept(concept["id"], concept)
            return {
                "status": "success",
                "action": "prompt_enriched",
                "concept_id": concept["id"],
                "details": {"new_prompt": new_prompt}
            }
        return {"status": "error", "message": "No new prompt provided"}
    
    def _complete_field(self, concept: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Complete missing fields in concept"""
        field_name = metadata.get("field_name")
        field_value = metadata.get("field_value")
        
        if field_name and field_value:
            concept[field_name] = field_value
            self.nous.update_concept(concept["id"], concept)
            return {
                "status": "success",
                "action": "field_completed",
                "concept_id": concept["id"],
                "details": {"field": field_name, "value": field_value}
            }
        return {"status": "error", "message": "Missing field name or value"}
    
    def _clarify_description(self, concept: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clarify vague descriptions"""
        new_description = metadata.get("new_description", "")
        if new_description:
            concept["description"] = new_description
            self.nous.update_concept(concept["id"], concept)
            return {
                "status": "success",
                "action": "description_clarified",
                "concept_id": concept["id"],
                "details": {"new_description": new_description}
            }
        return {"status": "error", "message": "No new description provided"}
    
    def _add_relations(self, concept: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add contextual relations to concept"""
        relations = metadata.get("relations", [])
        
        if "relations" not in concept:
            concept["relations"] = []
        
        concept["relations"].extend(relations)
        self.nous.update_concept(concept["id"], concept)
        
        return {
            "status": "success",
            "action": "relations_added",
            "concept_id": concept["id"],
            "details": {"relations_added": len(relations)}
        }
    
    def _log_action(self, suggestion: CreativeSuggestion, result: Dict[str, Any]):
        """Log action for audit trail"""
        action_record = {
            "timestamp": datetime.now().isoformat(),
            "suggestion_type": suggestion.suggestion_type,
            "concept_id": suggestion.concept_id,
            "result": result,
            "priority": suggestion.priority
        }
        self.action_log.append(action_record)
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of executed actions"""
        return {
            "total_actions": len(self.action_log),
            "last_action": self.action_log[-1] if self.action_log else None,
            "validation_queue_size": len(self.validation_queue),
            "recent_actions": self.action_log[-10:] if len(self.action_log) > 10 else self.action_log
        }
    
    def process_suggestions_batch(self, suggestions: List[CreativeSuggestion]) -> List[Dict[str, Any]]:
        """Process multiple suggestions in batch"""
        results = []
        
        # Sort by priority (higher priority first)
        sorted_suggestions = sorted(suggestions, key=lambda x: x.priority, reverse=True)
        
        for suggestion in sorted_suggestions:
            result = self.execute_suggestion(suggestion)
            results.append(result)
        
        return results
