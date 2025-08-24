#!/usr/bin/env python3
# File: neo4j_exporter.py
# Description: Synergesis Neo4j Exporter - Persists validated and enriched glyphs into Neo4j.

from __future__ import annotations
import json
import time
import logging
import sys
import math
import os
import re
import random  # For temporary ID generation if strictly needed
from typing import List, Dict, Any, Optional, Tuple, Union, Set
from copy import deepcopy
from datetime import datetime, timezone

# --- Module Imports & Fallbacks ---
try:
    # Assume glyph_core defines the necessary types and constants
    from glyph_core import (
        GlyphData, RELATIONSHIP_TYPES_SET, SIMPLE_POLARITIES_SET, SIMPLE_ALIGNMENTS_SET,
        # Potentially add a type for properties on relationships if not just dict
    )
    RELATIONSHIP_TYPES = list(RELATIONSHIP_TYPES_SET)
    SIMPLE_POLARITIES = list(SIMPLE_POLARITIES_SET)
    SIMPLE_ALIGNMENTS = list(SIMPLE_ALIGNMENTS_SET)
except ImportError:
    log_exporter_core_fallback = logging.getLogger("neo4j_exporter.core_fallback")
    log_exporter_core_fallback.warning("glyph_core.py not found. Using basic Dict typing and fallback constants.")
    GlyphData = Dict[str, Any]  # type: ignore
    RELATIONSHIP_TYPES = ["ADDRESSES_PROBLEM", "PROPOSES_SOLUTION_FOR", "USES_TECHNIQUE", "IMPLEMENTS_CONCEPT",
                         "EVALUATED_ON_DATASET", "MEASURED_BY_METRIC", "RELATED_TO_CONCEPT", "IMPROVES_ON",
                         "BUILDS_UPON", "PART_OF_ARCHITECTURE", "RELATED_TO"]
    SIMPLE_POLARITIES = ['+', '-', '0', '±', '?']
    SIMPLE_ALIGNMENTS = ['Celestial', 'Chthonic', 'Void', 'Harmonic', 'Elemental', 'Error', 'Expansion']

try:
    from neo4j import GraphDatabase, basic_auth, exceptions as neo4j_exceptions  # type: ignore
    NEO4J_DRIVER_AVAILABLE = True
except ImportError:
    NEO4J_DRIVER_AVAILABLE = False
    # Dummy classes for static analysis
    class GraphDatabase:  # type: ignore
        @staticmethod
        def driver(uri, auth):
            log_exporter.warning("Neo4j driver dummy.")
            return None

    class basic_auth:  # type: ignore
        def __init__(self, *_, **__):
            pass

    class neo4j_exceptions:  # type: ignore
        class Neo4jError(Exception):
            pass

        class ClientError(Neo4jError):
            pass

# --- Logging Setup ---
log_exporter = logging.getLogger('neo4j_exporter')
if not log_exporter.handlers:
    h_exporter = logging.StreamHandler(sys.stdout)
    h_exporter.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log_exporter.addHandler(h_exporter)
log_exporter.setLevel(logging.INFO)

# --- Constants for Property Preparation ---
DIRECT_PROPS_EXPORT = [
    'id', 'timestamp', 'fréquence', 'poids', 'entropy_score', 'resonance',
    'emergence', 'status', 'loop_source', 'archetype', 'stability',
    'natural_prompt', 'semantic_hash', 'llm_prompt_version',
]
LIST_STRING_PROPS_EXPORT = ['tags', 'sourceIds', 'domain_tags']  # domain_tags from technical glyphs

# --- Concept Types for Validation ---
CONCEPT_TYPES = {
    "Problem", "TechnicalConcept", "ProposedSolution", "KeyContribution",
    "Methodology", "Dataset", "Metric", "ToolFramework",
    "TheoreticalPrinciple", "ArchitecturalPattern"
}

# --- Helper Functions ---
def _get_env_exporter(key: str, default: Optional[str] = None) -> str:
    """Get environment variable with fallback."""
    val = os.getenv(key, default)
    if val is None and default is None:
        raise EnvironmentError(f"Exporter Env var {key} required.")
    return val or ""

def _get_dominant_from_prop_export(prop_value: Any, kind: str) -> str:
    """Helper to extract dominant value from composite property."""
    if kind == 'polarité':
        if isinstance(prop_value, list) and prop_value and all(isinstance(t, tuple) and len(t) == 2 for t in prop_value):
            return max(prop_value, key=lambda t: t[1])[0]
        if isinstance(prop_value, str) and prop_value in SIMPLE_POLARITIES:
            return prop_value
        return "?"
    if kind == 'alignement':
        if isinstance(prop_value, dict) and prop_value:
            return max(prop_value, key=prop_value.get)
        if isinstance(prop_value, str) and prop_value in SIMPLE_ALIGNMENTS:
            return prop_value
        return "Error"
    return str(prop_value) if prop_value is not None else ""

def _prepare_node_properties(glyph_dict: GlyphData) -> Dict[str, Any]:
    """Prepares a flat dictionary of properties for a single glyph node for Neo4j storage."""
    props: Dict[str, Any] = {}
    gid = glyph_dict.get('id')
    if not gid or not isinstance(gid, str):
        log_exporter.error(f"Glyph missing or invalid ID: {str(glyph_dict)[:100]}. Skipping property prep for this field.")
        return {"id": f"INVALID_ID_{random.randint(1000, 9999)}", "_export_error": "Missing or invalid ID"}
    props['id'] = str(gid)

    # Direct properties
    for key in DIRECT_PROPS_EXPORT:
        if key == 'id':
            continue
        val = glyph_dict.get(key)
        if val is not None and not (isinstance(val, float) and math.isnan(val)):
            if isinstance(val, datetime):
                val = (val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val).timestamp()
            props[key] = val

    # List string properties
    for key in LIST_STRING_PROPS_EXPORT:
        val = glyph_dict.get(key)
        if isinstance(val, list):
            props[key] = [str(x) for x in val if x is not None and isinstance(x, (str, int, float))]  # Ensure basic types
        elif val is not None:  # If not a list but exists, store as string or log warning
            props[key] = [str(val)]
            log_exporter.debug(f"Glyph {gid}: Field '{key}' was not a list, converted to list of one string.")

    # Polarity and Alignment (handling simple/composite)
    pol = glyph_dict.get('polarité')
    if isinstance(pol, list):
        props["polarité_composite_json"] = json.dumps(pol)
        props["polarité"] = _get_dominant_from_prop_export(pol, 'polarité')
    elif isinstance(pol, str) and pol in SIMPLE_POLARITIES:
        props["polarité"] = pol
    else:
        props["polarité"] = "?"

    align = glyph_dict.get('alignement')
    if isinstance(align, dict):
        props["alignement_composite_json"] = json.dumps(align)
        props["alignement"] = _get_dominant_from_prop_export(align, 'alignement')
    elif isinstance(align, str) and align in SIMPLE_ALIGNMENTS:
        props["alignement"] = align
    else:
        props["alignement"] = "Error"

    # Details (store as JSON string) and specific extracted details
    details_raw = glyph_dict.get('details')  # This can be from initial glyph
    details_json_from_llm = glyph_dict.get('details_json')  # This is from tech_glyph_prompt

    if isinstance(details_json_from_llm, str):  # Already a JSON string
        props['details_structured_json'] = details_json_from_llm
    elif isinstance(details_raw, dict):  # A dict in 'details'
        try:
            props['details_generic_json'] = json.dumps(details_raw)
        except TypeError:
            log_exporter.warning(f"Could not JSON-serialize 'details' field for glyph {gid}")
    elif isinstance(details_raw, str):  # A simple string in 'details'
        props['details_text'] = details_raw

    # Add 'concept_type' as a direct property if it's in tags (for easier querying)
    glyph_tags = props.get('tags', [])
    found_concept_types = [tag for tag in glyph_tags if tag in CONCEPT_TYPES]
    if found_concept_types:
        props['concept_type'] = found_concept_types[0]  # Take the first one found
        if len(found_concept_types) > 1:
            log_exporter.warning(f"Glyph {gid} has multiple concept_type tags: {found_concept_types}. Using '{props['concept_type']}'.")

    return props

def _sanitize_relationship_type(rel_type: str) -> str:
    """Sanitize relationship type for Neo4j (valid identifier)."""
    # Replace non-alphanumeric chars with underscore and uppercase
    return re.sub(r'[^a-zA-Z0-9_]', '_', rel_type).upper()

def _prepare_relationship_data(glyph_dict: GlyphData, use_apoc_rels: bool = False) -> List[Dict[str, Any]]:
    """Prepares relationship data for a single glyph."""
    rel_data_list = []
    src_id = str(glyph_dict.get("id", ""))
    if not src_id:
        log_exporter.warning(f"Skipping relationship prep for glyph with missing ID: {str(glyph_dict)[:100]}")
        return []

    for rel in glyph_dict.get("relationships", []):
        if isinstance(rel, dict) and "target_glyph_id" in rel and "type" in rel:
            rel_type_semantic = str(rel["type"])
            
            # For APOC, we need a valid Neo4j relationship type
            # For generic approach, we store the original type as a property
            apoc_rel_type = _sanitize_relationship_type(rel_type_semantic) if use_apoc_rels else "LINKS_TO"
            
            # All other keys in rel dict become properties of the relationship
            rel_attributes = {k: v for k, v in rel.items() if k not in ['target_glyph_id', 'type']}
            
            # For generic approach, store the original type as a property
            if not use_apoc_rels:
                rel_attributes["relationship_type"] = rel_type_semantic
                
            # Add timestamp if not present
            rel_attributes.setdefault('timestamp', glyph_dict.get('timestamp', time.time()))

            rel_data_list.append({
                "src_id": src_id,
                "dst_id": str(rel["target_glyph_id"]),
                "type": apoc_rel_type,
                "properties": rel_attributes
            })
        else:
            log_exporter.warning(f"Malformed relationship in glyph {src_id}: {rel}. Skipping this relationship.")

    return rel_data_list

class Neo4jExporter:
    """
    Handles exporting validated and enriched Synergesis glyphs to a Neo4j database.
    """
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, use_apoc_rels: bool = False):
        """
        Initialize the Neo4j exporter.
        
        Args:
            uri: Neo4j connection URI (default: from env NEO4J_URI or "bolt://localhost:7687")
            user: Neo4j username (default: from env NEO4J_USER or "neo4j")
            password: Neo4j password (default: from env NEO4J_PASSWORD)
            use_apoc_rels: Whether to use APOC for dynamic relationship types (default: False)
        """
        self.driver = None
        self.use_apoc_rels = use_apoc_rels
        
        if not NEO4J_DRIVER_AVAILABLE:
            log_exporter.error("Neo4jExporter initialized but Neo4j driver is NOT available.")
            return
            
        self.uri = uri or _get_env_exporter("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or _get_env_exporter("NEO4J_USER", "neo4j")
        pwd = password or _get_env_exporter("NEO4J_PASSWORD", "password")  # Default for testing only
        
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=basic_auth(self.user, pwd))
            self.driver.verify_connectivity()  # type: ignore
            log_exporter.info(f"Neo4jExporter connected to {self.uri}. APOC for rels: {self.use_apoc_rels}")
        except Exception as e:
            log_exporter.critical(f"Neo4jExporter connection failed: {e}", exc_info=True)
            self.driver = None

    def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()  # type: ignore
            log_exporter.info("Neo4jExporter connection closed.")

    def test_connection(self) -> bool:
        """Test the Neo4j connection."""
        if not self.driver:
            log_exporter.error("Cannot test connection: Neo4j driver not available.")
            return False
            
        try:
            with self.driver.session(database="neo4j") as session:  # type: ignore
                result = session.run("RETURN 1 as test")
                return result.single()["test"] == 1
        except Exception as e:
            log_exporter.error(f"Connection test failed: {e}")
            return False

    def setup_constraints(self) -> bool:
        """Set up Neo4j constraints for the Glyph model."""
        if not self.driver:
            log_exporter.error("Cannot set up constraints: Neo4j driver not available.")
            return False
            
        try:
            with self.driver.session(database="neo4j") as session:  # type: ignore
                # Create constraint for Glyph.id uniqueness
                session.run("""
                CREATE CONSTRAINT glyph_id_unique IF NOT EXISTS
                FOR (g:Glyph) REQUIRE g.id IS UNIQUE
                """)
                
                # Create index for concept_type
                session.run("""
                CREATE INDEX glyph_concept_type IF NOT EXISTS
                FOR (g:Glyph) ON (g.concept_type)
                """)
                
                # Create index for semantic_hash
                session.run("""
                CREATE INDEX glyph_semantic_hash IF NOT EXISTS
                FOR (g:Glyph) ON (g.semantic_hash)
                """)
                
                log_exporter.info("Neo4j constraints and indexes set up successfully.")
                return True
        except Exception as e:
            log_exporter.error(f"Failed to set up constraints: {e}")
            return False

    @staticmethod
    def _cypher_batch_upsert_nodes(tx, batch_node_props: List[Dict[str, Any]]):
        """Cypher for batch creating/merging nodes."""
        # MERGE on ID, SET ensures properties are updated if node exists
        query = """
        UNWIND $batch as props
        MERGE (g:Glyph {id: props.id})
        SET g = props // Overwrites all properties with new ones, including removing old ones not in new props
        RETURN count(g) as nodes_processed
        """
        result = tx.run(query, batch=batch_node_props)
        summary = result.consume()
        log_exporter.debug(f"Node batch: {summary.counters.nodes_created} created, {summary.counters.properties_set} props set.")

    @staticmethod
    def _cypher_batch_upsert_relationships_generic(tx, batch_rel_data: List[Dict[str, Any]]):
        """Cypher for batch creating/merging generic :LINKS_TO relationships."""
        # Each item in batch_rel_data: {src_id, dst_id, type (semantic), properties (for rel)}
        query = """
        UNWIND $batch as rel_data
        MATCH (src:Glyph {id: rel_data.src_id})
        MATCH (dst:Glyph {id: rel_data.dst_id})
        MERGE (src)-[r:LINKS_TO {relationship_type: rel_data.properties.relationship_type}]->(dst)
        SET r = rel_data.properties // Overwrite existing properties on match
        RETURN count(r) as rels_processed
        """
        result = tx.run(query, batch=batch_rel_data)
        summary = result.consume()
        log_exporter.debug(f"Generic relationship batch: {summary.counters.relationships_created} created/merged.")

    @staticmethod
    def _cypher_batch_upsert_relationships_apoc(tx, batch_rel_data: List[Dict[str, Any]]):
        """Cypher for batch creating/merging relationships with dynamic types using APOC."""
        # Each item in batch_rel_data: {src_id, dst_id, type (sanitized), properties (for rel)}
        query = """
        UNWIND $batch as rel_data
        MATCH (src:Glyph {id: rel_data.src_id})
        MATCH (dst:Glyph {id: rel_data.dst_id})
        CALL apoc.merge.relationship(src, rel_data.type, {}, rel_data.properties, dst) YIELD rel
        RETURN count(rel) as rels_processed
        """
        result = tx.run(query, batch=batch_rel_data)
        summary = result.consume()
        log_exporter.debug(f"APOC relationship batch: {summary.counters.relationships_created} created/merged.")

    def export_glyphs(self, glyphs_to_export: List[GlyphData], batch_size: int = 200) -> Tuple[int, int, Dict[str, Any]]:
        """
        Exports a list of glyphs to Neo4j. Handles nodes and then relationships.
        
        Args:
            glyphs_to_export: List of glyphs to export
            batch_size: Number of nodes/relationships to process in each batch
            
        Returns:
            Tuple[int, int, Dict[str, Any]]: (nodes_processed_count, relationships_processed_count, stats)
        """
        stats = {
            "start_time": time.time(),
            "end_time": None,
            "duration_seconds": 0,
            "total_glyphs": len(glyphs_to_export),
            "valid_glyphs": 0,
            "invalid_glyphs": 0,
            "nodes_processed": 0,
            "relationships_processed": 0,
            "errors": []
        }
        
        if not self.driver:
            error_msg = "Cannot export: Neo4j driver not available or not connected."
            log_exporter.error(error_msg)
            stats["errors"].append(error_msg)
            return 0, 0, stats
            
        if not glyphs_to_export:
            log_exporter.info("No glyphs provided for export.")
            stats["end_time"] = time.time()
            stats["duration_seconds"] = stats["end_time"] - stats["start_time"]
            return 0, 0, stats

        log_exporter.info(f"Starting export of {len(glyphs_to_export)} glyphs to Neo4j (batch size: {batch_size})...")

        # 1. Prepare all node and relationship data
        all_node_props: List[Dict[str, Any]] = []
        all_rel_data_for_batch: List[Dict[str, Any]] = []
        
        for glyph_dict in glyphs_to_export:
            if not isinstance(glyph_dict, dict) or "id" not in glyph_dict:
                log_exporter.warning(f"Skipping invalid glyph data item: {str(glyph_dict)[:100]}")
                stats["invalid_glyphs"] += 1
                continue
            
            # Prepare node properties
            node_p = _prepare_node_properties(glyph_dict)
            if "_export_error" in node_p:  # Skip if property prep failed critically
                error_msg = f"Skipping glyph {node_p.get('id')} due to property preparation error: {node_p['_export_error']}"
                log_exporter.error(error_msg)
                stats["errors"].append(error_msg)
                stats["invalid_glyphs"] += 1
                continue
                
            all_node_props.append(node_p)
            stats["valid_glyphs"] += 1
            
            # Prepare relationship data
            rel_data_list = _prepare_relationship_data(glyph_dict, self.use_apoc_rels)
            all_rel_data_for_batch.extend(rel_data_list)

        nodes_processed_count = len(all_node_props)
        rels_processed_count = len(all_rel_data_for_batch)
        log_exporter.info(f"Data preparation complete: {nodes_processed_count} nodes, {rels_processed_count} relationships.")

        # 2. Upsert Nodes in Batches
        try:
            with self.driver.session(database="neo4j") as session:  # type: ignore
                log_exporter.info("Upserting nodes...")
                for i in range(0, nodes_processed_count, batch_size):
                    batch = all_node_props[i : i + batch_size]
                    try:
                        session.write_transaction(self._cypher_batch_upsert_nodes, batch)
                        log_exporter.debug(f"Upserted node batch {i // batch_size + 1}")
                    except Exception as e:
                        error_msg = f"Error upserting node batch {i // batch_size + 1}: {e}"
                        log_exporter.error(error_msg, exc_info=True)
                        stats["errors"].append(error_msg)
                log_exporter.info("Node upsertion complete.")

                # 3. Upsert Relationships in Batches
                log_exporter.info("Upserting relationships...")
                for i in range(0, rels_processed_count, batch_size):
                    batch = all_rel_data_for_batch[i : i + batch_size]
                    try:
                        if self.use_apoc_rels:
                            session.write_transaction(self._cypher_batch_upsert_relationships_apoc, batch)
                        else:
                            session.write_transaction(self._cypher_batch_upsert_relationships_generic, batch)
                        log_exporter.debug(f"Upserted relationship batch {i // batch_size + 1}")
                    except Exception as e:
                        error_msg = f"Error upserting relationship batch {i // batch_size + 1}: {e}"
                        log_exporter.error(error_msg, exc_info=True)
                        stats["errors"].append(error_msg)
                log_exporter.info("Relationship upsertion complete.")
        except Exception as e:
            error_msg = f"Critical error during export: {e}"
            log_exporter.critical(error_msg, exc_info=True)
            stats["errors"].append(error_msg)

        # Update stats
        stats["end_time"] = time.time()
        stats["duration_seconds"] = stats["end_time"] - stats["start_time"]
        stats["nodes_processed"] = nodes_processed_count
        stats["relationships_processed"] = rels_processed_count
        
        log_exporter.info(f"Export completed in {stats['duration_seconds']:.2f} seconds. "
                         f"Processed {nodes_processed_count} nodes and {rels_processed_count} relationships.")
        
        return nodes_processed_count, rels_processed_count, stats

    def generate_cypher_for_glyphs(self, glyphs_to_export: List[GlyphData]) -> Tuple[str, Dict[str, Any]]:
        """
        Generate Cypher queries for a list of glyphs without executing them.
        Useful for debugging, testing, or manual execution.
        
        Args:
            glyphs_to_export: List of glyphs to generate Cypher for
            
        Returns:
            Tuple[str, Dict[str, Any]]: (cypher_script, stats)
        """
        stats = {
            "total_glyphs": len(glyphs_to_export),
            "valid_glyphs": 0,
            "invalid_glyphs": 0,
            "nodes_count": 0,
            "relationships_count": 0,
            "errors": []
        }
        
        if not glyphs_to_export:
            return "// No glyphs provided for export.", stats
            
        # Prepare all node and relationship data
        all_node_props: List[Dict[str, Any]] = []
        all_rel_data_for_batch: List[Dict[str, Any]] = []
        
        for glyph_dict in glyphs_to_export:
            if not isinstance(glyph_dict, dict) or "id" not in glyph_dict:
                stats["invalid_glyphs"] += 1
                continue
                
            # Prepare node properties
            node_p = _prepare_node_properties(glyph_dict)
            if "_export_error" in node_p:
                stats["invalid_glyphs"] += 1
                stats["errors"].append(f"Error preparing glyph {node_p.get('id')}: {node_p['_export_error']}")
                continue
                
            all_node_props.append(node_p)
            stats["valid_glyphs"] += 1
            
            # Prepare relationship data
            rel_data_list = _prepare_relationship_data(glyph_dict, self.use_apoc_rels)
            all_rel_data_for_batch.extend(rel_data_list)
            
        stats["nodes_count"] = len(all_node_props)
        stats["relationships_count"] = len(all_rel_data_for_batch)
        
        # Generate Cypher script
        cypher_lines = [
            "// Synergesis Glyph Export Cypher Script",
            f"// Generated: {datetime.now().isoformat()}",
            f"// Total Glyphs: {stats['total_glyphs']}",
            f"// Valid Glyphs: {stats['valid_glyphs']}",
            f"// Nodes: {stats['nodes_count']}",
            f"// Relationships: {stats['relationships_count']}",
            "",
            "// === CONSTRAINTS AND INDEXES ===",
            "CREATE CONSTRAINT glyph_id_unique IF NOT EXISTS",
            "FOR (g:Glyph) REQUIRE g.id IS UNIQUE;",
            "",
            "CREATE INDEX glyph_concept_type IF NOT EXISTS",
            "FOR (g:Glyph) ON (g.concept_type);",
            "",
            "CREATE INDEX glyph_semantic_hash IF NOT EXISTS",
            "FOR (g:Glyph) ON (g.semantic_hash);",
            "",
            "// === NODES ===",
        ]
        
        # Add node creation statements
        for node_props in all_node_props:
            node_id = node_props.get("id", "unknown")
            props_str = ", ".join([f"{k}: {json.dumps(v)}" for k, v in node_props.items()])
            cypher_lines.append(f"MERGE (g:{node_id}:Glyph {{id: {json.dumps(node_id)}}});")
            cypher_lines.append(f"SET g:{node_id} = {{{props_str}}};")
            
        cypher_lines.append("")
        cypher_lines.append("// === RELATIONSHIPS ===")
        
        # Add relationship creation statements
        for rel_data in all_rel_data_for_batch:
            src_id = rel_data["src_id"]
            dst_id = rel_data["dst_id"]
            rel_type = rel_data["type"]
            props_str = ", ".join([f"{k}: {json.dumps(v)}" for k, v in rel_data["properties"].items()])
            
            if self.use_apoc_rels:
                # APOC style with dynamic relationship type
                cypher_lines.append(f"MATCH (src:Glyph {{id: {json.dumps(src_id)}}}), (dst:Glyph {{id: {json.dumps(dst_id)}}})")
                cypher_lines.append(f"CALL apoc.merge.relationship(src, {json.dumps(rel_type)}, {{}}, {{{props_str}}}, dst) YIELD rel")
                cypher_lines.append("RETURN rel;")
            else:
                # Generic style with relationship_type property
                cypher_lines.append(f"MATCH (src:Glyph {{id: {json.dumps(src_id)}}}), (dst:Glyph {{id: {json.dumps(dst_id)}}})")
                cypher_lines.append(f"MERGE (src)-[r:LINKS_TO {{relationship_type: {json.dumps(rel_data['properties'].get('relationship_type', 'UNKNOWN'))}}}]->(dst)")
                cypher_lines.append(f"SET r = {{{props_str}}};")
                
        return "\n".join(cypher_lines), stats

    def query_glyphs(self, query_params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Query glyphs from Neo4j based on parameters.
        
        Args:
            query_params: Dictionary of query parameters
                - concept_type: Filter by concept type
                - tags: List of tags to filter by
                - limit: Maximum number of results
                
        Returns:
            List[Dict[str, Any]]: List of glyph dictionaries
        """
        if not self.driver:
            log_exporter.error("Cannot query: Neo4j driver not available or not connected.")
            return []
            
        params = query_params or {}
        limit = params.get("limit", 100)
        
        # Build query based on parameters
        query_conditions = []
        query_params = {}
        
        if "concept_type" in params:
            query_conditions.append("g.concept_type = $concept_type")
            query_params["concept_type"] = params["concept_type"]
            
        if "tags" in params and params["tags"]:
            query_conditions.append("ANY(tag IN g.tags WHERE tag IN $tags)")
            query_params["tags"] = params["tags"]
            
        if "semantic_hash" in params:
            query_conditions.append("g.semantic_hash = $semantic_hash")
            query_params["semantic_hash"] = params["semantic_hash"]
            
        # Build the query
        query = "MATCH (g:Glyph)"
        if query_conditions:
            query += " WHERE " + " AND ".join(query_conditions)
        query += f" RETURN g LIMIT {limit}"
        
        # Execute query
        try:
            with self.driver.session(database="neo4j") as session:  # type: ignore
                result = session.run(query, **query_params)
                return [record["g"] for record in result]
        except Exception as e:
            log_exporter.error(f"Error querying glyphs: {e}")
            return []

def test_neo4j_exporter():
    """Test the Neo4j exporter with sample data."""
    # Sample glyphs
    sample_glyphs = [
        {
            "id": "test_glyph_1",
            "polarité": "+",
            "alignement": "Void",
            "fréquence": 72,
            "poids": 5,
            "tags": ["TechnicalConcept", "machine_learning"],
            "sourceIds": ["test_source"],
            "timestamp": time.time(),
            "status": "validated",
            "semantic_hash": "sem1_hash1",
            "details_json": json.dumps({"key": "value"}),
            "relationships": [
                {"type": "IMPLEMENTS_CONCEPT", "target_glyph_id": "test_glyph_2", "confidence": 0.9}
            ]
        },
        {
            "id": "test_glyph_2",
            "polarité": "-",
            "alignement": "Celestial",
            "fréquence": 80,
            "poids": 7,
            "tags": ["Problem", "neural_networks"],
            "sourceIds": ["test_source"],
            "timestamp": time.time(),
            "status": "validated",
            "semantic_hash": "sem1_hash2",
            "details_json": json.dumps({"problem": "description"}),
            "relationships": [
                {"type": "ADDRESSES_PROBLEM", "target_glyph_id": "test_glyph_1", "confidence": 0.8}
            ]
        }
    ]
    
    # Test with both APOC and generic approaches
    for use_apoc in [False, True]:
        print(f"\n=== Testing Neo4jExporter with use_apoc_rels={use_apoc} ===")
        
        # Initialize exporter
        exporter = Neo4jExporter(use_apoc_rels=use_apoc)
        
        # Generate Cypher script
        cypher_script, stats = exporter.generate_cypher_for_glyphs(sample_glyphs)
        print(f"Generated Cypher script with {stats['nodes_count']} nodes and {stats['relationships_count']} relationships.")
        
        # Test connection if available
        if NEO4J_DRIVER_AVAILABLE:
            connection_ok = exporter.test_connection()
            print(f"Connection test: {'OK' if connection_ok else 'FAILED'}")
            
            if connection_ok:
                # Set up constraints
                exporter.setup_constraints()
                
                # Export glyphs
                nodes, rels, export_stats = exporter.export_glyphs(sample_glyphs)
                print(f"Exported {nodes} nodes and {rels} relationships in {export_stats['duration_seconds']:.2f} seconds.")
                
                # Query glyphs
                glyphs = exporter.query_glyphs({"concept_type": "TechnicalConcept"})
                print(f"Queried {len(glyphs)} glyphs with concept_type=TechnicalConcept.")
        
        # Close connection
        exporter.close()
    
    return cypher_script, stats

if __name__ == "__main__":
    test_neo4j_exporter()
