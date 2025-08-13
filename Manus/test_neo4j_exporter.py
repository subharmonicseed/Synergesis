#!/usr/bin/env python3
# File: test_neo4j_exporter.py
# Description: Test script for the Neo4j exporter module

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import time

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent))

# Import the modules
try:
    from neo4j_exporter import Neo4jExporter, _prepare_node_properties, _prepare_relationship_data
    import logging
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log_test = logging.getLogger('test_neo4j_exporter')

# Define test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "llm_tests"
RESULTS_DIR = Path(__file__).parent.parent / "llm_tests" / "neo4j_results"
RESULTS_DIR.mkdir(exist_ok=True)

def load_test_data(filename: str) -> List[Dict[str, Any]]:
    """Load test data from JSON file"""
    try:
        filepath = TEST_DATA_DIR / filename
        if not filepath.exists():
            log_test.error(f"Test data file not found: {filepath}")
            return []
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            log_test.error(f"Test data is not a list: {filepath}")
            return []
        
        return data
    except Exception as e:
        log_test.error(f"Error loading test data from {filename}: {e}")
        return []

def save_results(data: Any, filename: str) -> str:
    """Save results to JSON file"""
    try:
        filepath = RESULTS_DIR / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return str(filepath)
    except Exception as e:
        log_test.error(f"Error saving results to {filename}: {e}")
        return ""

def save_cypher_script(script: str, filename: str) -> str:
    """Save Cypher script to file"""
    try:
        filepath = RESULTS_DIR / filename
        with open(filepath, 'w') as f:
            f.write(script)
        return str(filepath)
    except Exception as e:
        log_test.error(f"Error saving Cypher script to {filename}: {e}")
        return ""

def create_test_glyphs() -> List[Dict[str, Any]]:
    """Create a list of test glyphs with various properties and relationships"""
    current_time = time.time()
    
    return [
        {
            "id": "problem_glyph_1",
            "polarité": "-",
            "alignement": "Void",
            "fréquence": 72,
            "poids": 8,
            "entropy_score": 0.7,
            "tags": ["Problem", "machine_learning", "catastrophic_forgetting"],
            "sourceIds": ["test_source_1"],
            "timestamp": current_time,
            "status": "validated",
            "semantic_hash": "sem1_hash_problem_1",
            "natural_prompt": "The problem of catastrophic forgetting in neural networks",
            "details_json": json.dumps({
                "problem_statement": "Neural networks tend to forget previously learned tasks when trained on new ones.",
                "affected_components": ["neural_networks", "continual_learning"],
                "severity": "high"
            }),
            "relationships": [
                {"type": "ADDRESSED_BY", "target_glyph_id": "solution_glyph_1", "confidence": 0.9, "bidirectional": False}
            ]
        },
        {
            "id": "solution_glyph_1",
            "polarité": "+",
            "alignement": "Celestial",
            "fréquence": 80,
            "poids": 7,
            "entropy_score": 0.5,
            "tags": ["ProposedSolution", "elastic_weight_consolidation", "regularization"],
            "sourceIds": ["test_source_2"],
            "timestamp": current_time + 100,
            "status": "validated",
            "semantic_hash": "sem1_hash_solution_1",
            "natural_prompt": "Elastic Weight Consolidation for preventing catastrophic forgetting",
            "details_json": json.dumps({
                "solution_name": "Elastic Weight Consolidation",
                "summary": "A regularization method that slows down learning on weights important for previous tasks.",
                "key_mechanisms": ["importance_weighting", "regularization_term", "fisher_information"]
            }),
            "relationships": [
                {"type": "ADDRESSES_PROBLEM", "target_glyph_id": "problem_glyph_1", "confidence": 0.95, "bidirectional": False},
                {"type": "USES_TECHNIQUE", "target_glyph_id": "concept_glyph_1", "confidence": 0.8, "bidirectional": False}
            ]
        },
        {
            "id": "concept_glyph_1",
            "polarité": "0",
            "alignement": "Harmonic",
            "fréquence": 90,
            "poids": 6,
            "entropy_score": 0.3,
            "tags": ["TechnicalConcept", "regularization", "optimization"],
            "sourceIds": ["test_source_3"],
            "timestamp": current_time + 200,
            "status": "validated",
            "semantic_hash": "sem1_hash_concept_1",
            "natural_prompt": "Regularization techniques in neural networks",
            "details_json": json.dumps({
                "concept_name": "Regularization",
                "definition": "Methods to prevent overfitting by adding constraints or penalties to the learning process.",
                "key_properties": ["prevents_overfitting", "improves_generalization", "constrains_model_complexity"]
            }),
            "relationships": [
                {"type": "RELATED_TO", "target_glyph_id": "concept_glyph_2", "confidence": 0.7, "bidirectional": True}
            ]
        },
        {
            "id": "concept_glyph_2",
            "polarité": "0",
            "alignement": "Elemental",
            "fréquence": 85,
            "poids": 5,
            "entropy_score": 0.4,
            "tags": ["TechnicalConcept", "optimization", "gradient_descent"],
            "sourceIds": ["test_source_4"],
            "timestamp": current_time + 300,
            "status": "validated",
            "semantic_hash": "sem1_hash_concept_2",
            "natural_prompt": "Optimization algorithms for neural networks",
            "details_json": json.dumps({
                "concept_name": "Optimization Algorithms",
                "definition": "Methods to minimize the loss function during neural network training.",
                "key_properties": ["gradient_based", "iterative", "convergence_properties"]
            }),
            "relationships": [
                {"type": "RELATED_TO", "target_glyph_id": "concept_glyph_1", "confidence": 0.7, "bidirectional": True}
            ]
        },
        {
            "id": "metric_glyph_1",
            "polarité": "?",
            "alignement": "Void",
            "fréquence": 60,
            "poids": 4,
            "entropy_score": 0.6,
            "tags": ["Metric", "performance_evaluation", "accuracy"],
            "sourceIds": ["test_source_5"],
            "timestamp": current_time + 400,
            "status": "validated",
            "semantic_hash": "sem1_hash_metric_1",
            "natural_prompt": "Backward Transfer metric for continual learning",
            "details_json": json.dumps({
                "metric_name": "Backward Transfer",
                "definition": "Measures how learning new tasks affects the performance on previously learned tasks.",
                "formula": "BWT = 1/N-1 * sum(R_N,j - R_j,j) for j=1 to N-1",
                "interpretation": "Positive values indicate positive transfer, negative values indicate forgetting."
            }),
            "relationships": [
                {"type": "MEASURES", "target_glyph_id": "problem_glyph_1", "confidence": 0.85, "bidirectional": False},
                {"type": "EVALUATES", "target_glyph_id": "solution_glyph_1", "confidence": 0.8, "bidirectional": False}
            ]
        }
    ]

def test_property_preparation():
    """Test the property preparation functions"""
    log_test.info("=== Testing property preparation ===")
    
    # Create test glyphs
    test_glyphs = create_test_glyphs()
    
    # Test node property preparation
    for glyph in test_glyphs:
        node_props = _prepare_node_properties(glyph)
        log_test.info(f"Prepared properties for glyph {glyph['id']}: {len(node_props)} properties")
        
        # Check that essential properties are present
        for essential_prop in ['id', 'polarité', 'alignement', 'tags']:
            if essential_prop not in node_props:
                log_test.error(f"Missing essential property {essential_prop} in prepared node properties")
        
        # Check that details_json is properly handled
        if 'details_structured_json' not in node_props:
            log_test.error(f"Missing details_structured_json in prepared node properties")
            
        # Check that concept_type is extracted from tags
        if 'concept_type' not in node_props and any(tag in glyph.get('tags', []) for tag in [
            "Problem", "TechnicalConcept", "ProposedSolution", "KeyContribution",
            "Methodology", "Dataset", "Metric", "ToolFramework"
        ]):
            log_test.error(f"Missing concept_type in prepared node properties")
    
    # Test relationship preparation
    for glyph in test_glyphs:
        # Test with APOC
        rel_data_apoc = _prepare_relationship_data(glyph, use_apoc_rels=True)
        log_test.info(f"Prepared {len(rel_data_apoc)} APOC relationships for glyph {glyph['id']}")
        
        # Test without APOC
        rel_data_generic = _prepare_relationship_data(glyph, use_apoc_rels=False)
        log_test.info(f"Prepared {len(rel_data_generic)} generic relationships for glyph {glyph['id']}")
        
        # Check that relationships are properly prepared
        if len(rel_data_apoc) != len(glyph.get('relationships', [])):
            log_test.error(f"Mismatch in relationship count for glyph {glyph['id']}")
            
        # Check that relationship properties are properly prepared
        for rel_data in rel_data_apoc:
            if 'src_id' not in rel_data or 'dst_id' not in rel_data or 'type' not in rel_data or 'properties' not in rel_data:
                log_test.error(f"Missing essential fields in prepared relationship data")
                
        # Check that relationship_type is stored as property for generic approach
        for rel_data in rel_data_generic:
            if 'relationship_type' not in rel_data['properties']:
                log_test.error(f"Missing relationship_type in generic relationship properties")
    
    # Save prepared data for inspection
    save_results([_prepare_node_properties(glyph) for glyph in test_glyphs], "prepared_node_properties.json")
    save_results([_prepare_relationship_data(glyph, True) for glyph in test_glyphs], "prepared_relationships_apoc.json")
    save_results([_prepare_relationship_data(glyph, False) for glyph in test_glyphs], "prepared_relationships_generic.json")
    
    log_test.info("Property preparation tests completed")

def test_cypher_generation():
    """Test the Cypher generation functionality"""
    log_test.info("=== Testing Cypher generation ===")
    
    # Create test glyphs
    test_glyphs = create_test_glyphs()
    
    # Initialize exporter with both APOC and generic approaches
    exporter_apoc = Neo4jExporter(use_apoc_rels=True)
    exporter_generic = Neo4jExporter(use_apoc_rels=False)
    
    # Generate Cypher scripts
    cypher_apoc, stats_apoc = exporter_apoc.generate_cypher_for_glyphs(test_glyphs)
    cypher_generic, stats_generic = exporter_generic.generate_cypher_for_glyphs(test_glyphs)
    
    # Log statistics
    log_test.info(f"Generated APOC Cypher script: {stats_apoc['nodes_count']} nodes, {stats_apoc['relationships_count']} relationships")
    log_test.info(f"Generated generic Cypher script: {stats_generic['nodes_count']} nodes, {stats_generic['relationships_count']} relationships")
    
    # Save Cypher scripts
    save_cypher_script(cypher_apoc, "cypher_script_apoc.cypher")
    save_cypher_script(cypher_generic, "cypher_script_generic.cypher")
    
    # Check that scripts contain expected elements
    if "CREATE CONSTRAINT" not in cypher_apoc:
        log_test.error("Missing constraint creation in APOC Cypher script")
    
    if "CREATE INDEX" not in cypher_apoc:
        log_test.error("Missing index creation in APOC Cypher script")
    
    if "MERGE (g:" not in cypher_apoc:
        log_test.error("Missing node creation in APOC Cypher script")
    
    if "apoc.merge.relationship" not in cypher_apoc:
        log_test.error("Missing APOC relationship creation in APOC Cypher script")
    
    if "MERGE (src)-[r:LINKS_TO" not in cypher_generic:
        log_test.error("Missing generic relationship creation in generic Cypher script")
    
    log_test.info("Cypher generation tests completed")

def test_with_llm_output():
    """Test the Neo4j exporter with LLM output"""
    log_test.info("=== Testing with LLM output ===")
    
    # Load LLM output
    codepde_glyphs = load_test_data("pipeline_results/codepde_v1_2_full_glyphs_1748375518.json")
    seps_glyphs = load_test_data("pipeline_results/seps_v1_2_strict_glyphs_1748375518.json")
    
    if not codepde_glyphs or not seps_glyphs:
        log_test.error("Failed to load LLM output")
        return
    
    # Initialize exporter
    exporter = Neo4jExporter(use_apoc_rels=True)
    
    # Generate Cypher scripts
    log_test.info("Generating Cypher for CodePDE glyphs...")
    cypher_codepde, stats_codepde = exporter.generate_cypher_for_glyphs(codepde_glyphs)
    
    log_test.info("Generating Cypher for SEPS glyphs...")
    cypher_seps, stats_seps = exporter.generate_cypher_for_glyphs(seps_glyphs)
    
    # Log statistics
    log_test.info(f"CodePDE: {stats_codepde['nodes_count']} nodes, {stats_codepde['relationships_count']} relationships")
    log_test.info(f"SEPS: {stats_seps['nodes_count']} nodes, {stats_seps['relationships_count']} relationships")
    
    # Save Cypher scripts
    save_cypher_script(cypher_codepde, "cypher_script_codepde.cypher")
    save_cypher_script(cypher_seps, "cypher_script_seps.cypher")
    
    # Save statistics
    save_results(stats_codepde, "cypher_stats_codepde.json")
    save_results(stats_seps, "cypher_stats_seps.json")
    
    log_test.info("LLM output tests completed")

def test_neo4j_connection():
    """Test the Neo4j connection if available"""
    log_test.info("=== Testing Neo4j connection ===")
    
    # Initialize exporter
    exporter = Neo4jExporter()
    
    # Test connection
    connection_ok = exporter.test_connection()
    log_test.info(f"Connection test: {'OK' if connection_ok else 'FAILED'}")
    
    if connection_ok:
        # Set up constraints
        constraints_ok = exporter.setup_constraints()
        log_test.info(f"Constraints setup: {'OK' if constraints_ok else 'FAILED'}")
        
        # Create test glyphs
        test_glyphs = create_test_glyphs()
        
        # Export glyphs
        nodes, rels, stats = exporter.export_glyphs(test_glyphs)
        log_test.info(f"Exported {nodes} nodes and {rels} relationships in {stats['duration_seconds']:.2f} seconds")
        
        # Save export statistics
        save_results(stats, "export_stats.json")
        
        # Query glyphs
        for concept_type in ["Problem", "ProposedSolution", "TechnicalConcept", "Metric"]:
            glyphs = exporter.query_glyphs({"concept_type": concept_type})
            log_test.info(f"Queried {len(glyphs)} glyphs with concept_type={concept_type}")
    
    # Close connection
    exporter.close()
    
    log_test.info("Neo4j connection tests completed")

def main():
    """Main test function"""
    log_test.info("Starting Neo4j exporter tests...")
    
    # Test property preparation
    test_property_preparation()
    
    # Test Cypher generation
    test_cypher_generation()
    
    # Test with LLM output
    test_with_llm_output()
    
    # Test Neo4j connection if available
    try:
        from neo4j import GraphDatabase
        test_neo4j_connection()
    except ImportError:
        log_test.warning("Neo4j driver not available, skipping connection tests")
    
    log_test.info("All tests completed")

if __name__ == "__main__":
    main()
