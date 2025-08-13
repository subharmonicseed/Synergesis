"""Script to apply Neo4j schema definitions."""

import os
import sys
import pathlib

# Add the project root to Python path
project_root = str(pathlib.Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from storage.neo4j_interface import Neo4jStorage

if __name__ == "__main__":
    try:
        # Initialize storage with environment variables
        storage = Neo4jStorage()
        
        # Apply schema
        from storage.neo4j_schema import apply_schema
        apply_schema(storage)
        
        print("Schema applied successfully ✓")
    except Exception as e:
        print(f"Error applying schema: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'storage' in locals():
            storage.close()
