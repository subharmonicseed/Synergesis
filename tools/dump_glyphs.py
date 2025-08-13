from neo4j import GraphDatabase
import json
import os

def dump_glyphs_to_file(output_file="glyphs_dump.json"):
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "blackstar1989")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session(database=database) as session:
            result = session.run("""
                MATCH (g:Glyph)
                RETURN g
                ORDER BY g.timestamp DESC
                LIMIT 100
            """)
            
            glyphs = []
            for record in result:
                glyph = record["g"]
                glyph_data = {
                    "id": glyph["id"],
                    "timestamp": glyph["timestamp"],
                    "source": glyph["source"],
                    "concept_type": glyph["concept_type"],
                    "status": glyph["status"],
                    "polarité": glyph["polarité"],
                    "alignement": glyph["alignement"],
                    "content": glyph["content"],
                    "metadata": glyph["metadata"]
                }
                glyphs.append(glyph_data)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({"glyphs": glyphs}, f, indent=2, ensure_ascii=False)
            
            print(f"Successfully dumped {len(glyphs)} glyphs to {output_file}")
            
    except Exception as e:
        print(f"Error dumping glyphs: {e}")
    finally:
        if 'driver' in locals():
            driver.close()

if __name__ == "__main__":
    dump_glyphs_to_file()
