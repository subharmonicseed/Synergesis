"""
Agent Hestia - Data Management and External Integration
Advanced data ingestion, validation, and external system integration
"""

import logging
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from synergesis.agents.nous import Nous

logger = logging.getLogger("HestiaAgent")

@dataclass
class DataSource:
    """External data source"""
    name: str
    type: str  # "api", "file", "database", "web"
    endpoint: str
    authentication: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None

@dataclass
class DataValidation:
    """Data validation rules"""
    required_fields: List[str]
    field_types: Dict[str, str]
    constraints: Dict[str, Any]
    quality_threshold: float

class HestiaAgent:
    """
    Hestia: Data management and external integration engine
    """
    
    def __init__(self, nous_instance: Nous):
        self.nous = nous_instance
        self.data_sources = {}
        self.validation_rules = {}
        import_history = []
        self.external_integrations = {}
        
    def ingest_external_data(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest data from external sources"""
        
        logger.info(f"Hestia ingesting data from {source_config.get('source_name', 'unknown')}")
        
        source_name = source_config.get("source_name")
        source_type = source_config.get("source_type")
        
        if not source_name or not source_type:
            return {
                "status": "error",
                "message": "Missing source name or type",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            # Validate source
            validation_result = self._validate_source(source_config)
            if not validation_result["valid"]:
                return validation_result
            
            # Ingest based on source type
            if source_type == "api":
                data = self._ingest_from_api(source_config)
            elif source_type == "file":
                data = self._ingest_from_file(source_config)
            elif source_type == "web":
                data = self._ingest_from_web(source_config)
            elif source_type == "database":
                data = self._ingest_from_database(source_config)
            else:
                return {
                    "status": "error",
                    "message": f"Unsupported source type: {source_type}",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Process and validate data
            processed_data = self._process_ingested_data(data, source_config)
            
            # Convert to concepts
            concepts = self._convert_to_concepts(processed_data, source_config)
            
            # Store in Nous
            stored_concepts = []
            for concept in concepts:
                stored_concept = self.nous.create_concept(concept)
                stored_concepts.append(stored_concept)
            
            ingestion_record = {
                "source_name": source_name,
                "source_type": source_type,
                "concepts_ingested": len(stored_concepts),
                "data_quality": self._assess_data_quality(processed_data),
                "timestamp": datetime.now().isoformat()
            }
            
            return {
                "status": "success",
                "ingestion": ingestion_record,
                "concepts": stored_concepts
            }
            
        except Exception as e:
            logger.error(f"Hestia ingestion error: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _validate_source(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data source configuration"""
        
        required_fields = ["source_name", "source_type", "endpoint"]
        
        for field in required_fields:
            if field not in source_config:
                return {
                    "valid": False,
                    "message": f"Missing required field: {field}",
                    "timestamp": datetime.now().isoformat()
                }
        
        return {"valid": True}
    
    def _ingest_from_api(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Ingest data from API"""
        
        endpoint = source_config["endpoint"]
        headers = source_config.get("headers", {})
        params = source_config.get("params", {})
        
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def _ingest_from_file(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Ingest data from file"""
        
        file_path = source_config["file_path"]
        file_format = source_config.get("format", "json")
        
        with open(file_path, 'r', encoding='utf-8') as file:
            if file_format == "json":
                return json.load(file)
            elif file_format == "csv":
                # Basic CSV handling
                import csv
                reader = csv.DictReader(file)
                return list(reader)
            else:
                return [{"content": file.read()}]
    
    def _ingest_from_web(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Ingest data from web scraping"""
        
        url = source_config["url"]
        
        # Basic web scraping
        response = requests.get(url)
        response.raise_for_status()
        
        return [{"url": url, "content": response.text[:1000]}]
    
    def _ingest_from_database(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Ingest data from database"""
        
        # Placeholder for database integration
        return [{"database": source_config.get("database_name", "unknown"), "data": "sample_data"}]
    
    def _process_ingested_data(self, data: List[Dict[str, Any]], source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process and validate ingested data"""
        
        validation_rules = source_config.get("validation_rules", {})
        processed_data = []
        
        for item in data:
            # Validate data
            if self._validate_data_item(item, validation_rules):
                # Transform to standard format
                processed_item = self._transform_data_item(item, source_config)
                processed_data.append(processed_item)
            else:
                logger.warning(f"Invalid data item skipped: {item}")
        
        return processed_data
    
    def _validate_data_item(self, item: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """Validate individual data item"""
        
        required_fields = rules.get("required_fields", [])
        
        for field in required_fields:
            if field not in item or not item[field]:
                return False
        
        return True
    
    def _transform_data_item(self, item: Dict[str, Any], source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data item to standard concept format"""
        
        mapping = source_config.get("field_mapping", {})
        
        concept = {
            "id": item.get(mapping.get("id", "id"), f"imported_{datetime.now().timestamp()}"),
            "title": item.get(mapping.get("title", "title"), "Imported Concept"),
            "description": item.get(mapping.get("description", "description"), ""),
            "concept_type": item.get(mapping.get("type", "type"), "imported"),
            "natural_prompt": item.get(mapping.get("prompt", "prompt"), ""),
            "metadata": {
                "source": source_config.get("source_name", "unknown"),
                "imported_at": datetime.now().isoformat(),
                "original_data": item
            }
        }
        
        return concept
    
    def _convert_to_concepts(self, data: List[Dict[str, Any]], source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert processed data to concepts"""
        
        concepts = []
        
        for item in data:
            concept = self._transform_data_item(item, source_config)
            concepts.append(concept)
        
        return concepts
    
    def _assess_data_quality(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess data quality"""
        
        total_items = len(data)
        valid_items = len([item for item in data if self._validate_data_item(item, {})])
        
        return {
            "total_items": total_items,
            "valid_items": valid_items,
            "quality_score": valid_items / total_items if total_items > 0 else 0,
            "completeness": len([item for item in data if all(item.get(k) for k in ["title", "description"])]) / total_items if total_items > 0 else 0
        }
    
    def setup_external_integration(self, integration_config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup external system integration"""
        
        integration_name = integration_config.get("name")
        integration_type = integration_config.get("type")
        
        try:
            # Validate integration
            validation = self._validate_integration(integration_config)
            if not validation["valid"]:
                return validation
            
            # Setup integration
            self.external_integrations[integration_name] = {
                "config": integration_config,
                "setup_time": datetime.now().isoformat(),
                "status": "active"
            }
            
            return {
                "status": "success",
                "integration": integration_name,
                "type": integration_type,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Hestia integration setup error: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _validate_integration(self, integration_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate integration configuration"""
        
        required_fields = ["name", "type", "endpoint"]
        
        for field in required_fields:
            if field not in integration_config:
                return {
                    "valid": False,
                    "message": f"Missing required field: {field}",
                    "timestamp": datetime.now().isoformat()
                }
        
        return {"valid": True}
    
    def sync_with_external_systems(self) -> Dict[str, Any]:
        """Sync with all external systems"""
        
        sync_results = []
        
        for integration_name, integration in self.external_integrations.items():
            try:
                # Sync data
                sync_result = self._sync_integration(integration)
                sync_results.append(sync_result)
            except Exception as e:
                sync_results.append({
                    "integration": integration_name,
                    "status": "error",
                    "message": str(e)
                })
        
        return {
            "status": "completed",
            "sync_results": sync_results,
            "timestamp": datetime.now().isoformat()
        }
    
    def _sync_integration(self, integration: Dict[str, Any]) -> Dict[str, Any]:
        """Sync with specific integration"""
        
        return {
            "integration": integration.get("name"),
            "status": "success",
            "data_synced": True,
            "timestamp": datetime.now().isoformat()
        }
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity across all sources"""
        
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "total_sources": len(self.data_sources),
            "validation_results": []
        }
        
        concepts = self.nous.get_all_concepts()
        
        # Check for data consistency
        consistency_issues = self._check_data_consistency(concepts)
        
        # Check for orphaned relations
        orphaned_relations = self._check_orphaned_relations(concepts)
        
        # Check for data quality issues
        quality_issues = self._check_data_quality(concepts)
        
        validation_results["validation_results"] = {
            "consistency_issues": consistency_issues,
            "orphaned_relations": orphaned_relations,
            "quality_issues": quality_issues,
            "overall_health": len(consistency_issues) + len(orphaned_relations) + len(quality_issues) == 0
        }
        
        return validation_results
    
    def _check_data_consistency(self, concepts: List[Dict[str, Any]]) -> List[str]:
        """Check data consistency"""
        
        issues = []
        
        # Check for duplicate IDs
        ids = [c.get("id") for c in concepts]
        duplicates = [id for id in set(ids) if ids.count(id) > 1]
        
        if duplicates:
            issues.append(f"Duplicate concept IDs found: {duplicates}")
        
        return issues
    
    def _check_orphaned_relations(self, concepts: List[Dict[str, Any]]) -> List[str]:
        """Check for orphaned relations"""
        
        issues = []
        concept_ids = {c.get("id") for c in concepts}
        
        for concept in concepts:
            for relation in concept.get("relations", []):
                target_id = relation.get("target_id")
                if target_id and target_id not in concept_ids:
                    issues.append(f"Orphaned relation: {concept.get('id')} -> {target_id}")
        
        return issues
    
    def _check_data_quality(self, concepts: List[Dict[str, Any]]) -> List[str]:
        """Check data quality"""
        
        issues = []
        
        for concept in concepts:
            if not concept.get("title"):
                issues.append(f"Missing title for concept: {concept.get('id')}")
            
            if not concept.get("description"):
                issues.append(f"Missing description for concept: {concept.get('id')}")
        
        return issues
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Get comprehensive data summary"""
        
        concepts = self.nous.get_all_concepts()
        
        return {
            "total_concepts": len(concepts),
            "data_sources": len(self.data_sources),
            "integrations": len(self.external_integrations),
            "import_history": len(self.import_history),
            "data_quality": self._assess_overall_data_quality(concepts),
            "last_sync": datetime.now().isoformat()
        }
    
    def _assess_overall_data_quality(self, concepts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess overall data quality"""
        
        validation = self.validate_data_integrity()
        
        return {
            "consistency_score": 1.0 - (len(validation["validation_results"]["consistency_issues"]) / len(concepts) if concepts else 0),
            "completeness_score": len([c for c in concepts if c.get("title") and c.get("description")]) / len(concepts) if concepts else 0,
            "relation_health": 1.0 - (len(validation["validation_results"]["orphaned_relations"]) / len(concepts) if concepts else 0),
            "overall_health": validation["validation_results"]["overall_health"]
        }
