"""
Test script for the complete ingestion pipeline: text → Glyphs → Neo4j

This script demonstrates the complete flow from raw text input to storage in Neo4j.
"""

import os
from ingestion.glyphifier import Glyphifier
from processing.glyph_lint import GlyphValidator
from storage.neo4j_interface import Neo4jStorage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    # Initialize components
    glyphifier = Glyphifier(source="test_pipeline")
    validator = GlyphValidator()
    storage = Neo4jStorage()
    
    # Example text inputs
    texts = [
        "This is a test text input that should be converted into a glyph.",
        "Another example of text that will be processed.",
        "A third piece of text to demonstrate bulk processing."
    ]
    
    # Step 1: Convert text to glyphs
    print("\n1. Converting text to glyphs...")
    glyphs = glyphifier.bulk_process(texts)
    print(f"Generated {len(glyphs)} glyphs")
    
    # Step 2: Validate glyphs
    print("\n2. Validating glyphs...")
    validation_results = validator.validate_batch(glyphs)
    valid_count = sum(1 for valid in validation_results.values() if valid)
    print(f"{valid_count}/{len(glyphs)} glyphs are valid")
    
    # Step 3: Store glyphs in Neo4j
    print("\n3. Storing glyphs in Neo4j...")
    success_count = storage.bulk_upsert_glyphs(glyphs)
    print(f"Successfully stored {success_count} glyphs")
    
    # Step 4: Verify storage
    print("\n4. Verifying storage...")
    count = storage.get_glyph_count()
    print(f"Total glyphs in Neo4j: {count}")

if __name__ == "__main__":
    main()
