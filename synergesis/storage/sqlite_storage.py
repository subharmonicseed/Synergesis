import sqlite3
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime

class GlyphNode(BaseModel):
    id: str
    type: str
    properties: Dict[str, Any]
    relationships: Optional[List[Dict]] = None

class SQLiteStorage:
    def __init__(self, db_path: str = "synergesis.db"):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        """Create database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS glyphs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                properties TEXT NOT NULL,
                relationships TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def upsert_glyph_node(self, glyph: GlyphNode) -> bool:
        """
        Create or update a glyph node in the database
        
        Args:
            glyph: GlyphNode object containing node data
            
        Returns:
            bool: True if operation was successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO glyphs (id, type, properties, relationships)
                VALUES (?, ?, ?, ?)
            ''', (
                glyph.id,
                glyph.type,
                str(glyph.properties),  # Convert to string instead of JSON
                str(glyph.relationships) if glyph.relationships else None
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.exception("SQLite operation failed")
            print(f"Error upserting glyph: {e}")
            return False

    def bulk_upsert_glyphs(self, glyphs: List[GlyphNode]) -> int:
        """
        Create or update multiple glyph nodes in the database
        
        Args:
            glyphs: List of GlyphNode objects
            
        Returns:
            int: Number of nodes processed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for glyph in glyphs:
                cursor.execute('''
                    INSERT OR REPLACE INTO glyphs (id, type, properties, relationships)
                    VALUES (?, ?, ?, ?)
                ''', (
                    glyph.id,
                    glyph.type,
                    str(glyph.properties),
                    str(glyph.relationships) if glyph.relationships else None
                ))
            conn.commit()
            conn.close()
            return len(glyphs)
        except Exception as e:
            logger.exception("SQLite operation failed")
            print(f"Error bulk upserting glyphs: {e}")
            return 0

    def get_glyph_count(self) -> int:
        """
        Get the total number of glyphs in the database
        
        Returns:
            int: Number of glyphs
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM glyphs")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.exception("SQLite operation failed")
            print(f"Error getting glyph count: {e}")
            return 0

    def query_glyphs(self, type: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Query glyphs from the database
        
        Args:
            type: Optional type filter
            limit: Maximum number of results (reduced from 100 to 10)
            
        Returns:
            List of glyph dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            query = "SELECT * FROM glyphs ORDER BY created_at DESC LIMIT ?"
            params = [limit]
            
            if type:
                query = "SELECT * FROM glyphs WHERE type = ? ORDER BY created_at DESC LIMIT ?"
                params = [type, limit]
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'id': row[0],
                'type': row[1],
                'properties': eval(row[2]),  # Use eval instead of json.loads for better performance
                'relationships': eval(row[3]) if row[3] else None,
                'created_at': row[4]
            } for row in rows]
        except Exception as e:
            logger.exception("SQLite operation failed")
            print(f"Error querying glyphs: {e}")
            return []

# Example usage
def main():
    # Initialize storage
    storage = SQLiteStorage()
    
    # Create example glyph
    example_glyph = GlyphNode(
        id="test_glyph_1",
        type="test",
        properties={
            "name": "Test Glyph",
            "created_at": str(datetime.now()),
            "metadata": {"source": "initial_test"}
        }
    )
    
    # Upsert glyph
    success = storage.upsert_glyph_node(example_glyph)
    print(f"Glyph upsert successful: {success}")
    
    # Get glyph count
    count = storage.get_glyph_count()
    print(f"Total glyphs in storage: {count}")
    
    # Query glyphs
    glyphs = storage.query_glyphs()
    print("\nFound glyphs:")
    for glyph in glyphs:
        print(f"- {glyph['id']}: {glyph['properties']['name']}")

if __name__ == "__main__":
    main()
