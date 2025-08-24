#!/usr/bin/env python3
# File: check_neo4j_status.py
# Description: Script pour vérifier l'état de la base Neo4j et les propriétés des glyphes

from neo4j import GraphDatabase
import sys

# Configuration de la connexion
uri = "bolt://localhost:7687"
user = "neo4j"
password = "synergesis_password"

def check_neo4j_status():
    """Vérifie l'état de la base Neo4j et affiche des informations sur les glyphes et relations."""
    try:
        # Connexion à Neo4j
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            # Vérifier le nombre de glyphes
            result = session.run("MATCH (g:Glyph) RETURN count(g) as count")
            glyph_count = result.single()["count"]
            print(f"Nombre de glyphes dans Neo4j: {glyph_count}")
            
            # Vérifier le nombre de relations
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            print(f"Nombre de relations dans Neo4j: {rel_count}")
            
            # Vérifier les types de relations
            result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            ORDER BY count DESC
            """)
            print("\nTypes de relations:")
            for record in result:
                print(f"- {record['rel_type']}: {record['count']} relations")
            
            # Vérifier les propriétés des relations RELATES_TO
            result = session.run("""
            MATCH ()-[r:RELATES_TO]->()
            RETURN r.relationship_type as type, count(r) as count
            ORDER BY count DESC
            """)
            print("\nTypes de relations sémantiques (RELATES_TO.relationship_type):")
            for record in result:
                print(f"- {record['type']}: {record['count']} relations")
            
            # Vérifier les propriétés des glyphes
            result = session.run("""
            MATCH (g:Glyph)
            RETURN g.id as id, g.natural_prompt as prompt, g.concept_type as type
            LIMIT 5
            """)
            print("\nExemples de glyphes:")
            for record in result:
                print(f"- ID: {record['id']}")
                print(f"  Type: {record['type']}")
                print(f"  Prompt: {record['prompt'][:50]}...")
            
            # Vérifier si la propriété degree_centrality existe
            result = session.run("""
            MATCH (g:Glyph)
            WHERE g.degree_centrality IS NOT NULL
            RETURN count(g) as count
            """)
            degree_count = result.single()["count"]
            print(f"\nGlyphes avec propriété degree_centrality: {degree_count}/{glyph_count}")
            
            # Tester une requête SET simple pour vérifier les permissions
            try:
                result = session.run("""
                MATCH (g:Glyph)
                WITH g LIMIT 1
                SET g.test_property = 'test_value'
                RETURN g.id
                """)
                test_id = result.single()["g.id"]
                print(f"\nTest SET réussi sur le glyphe {test_id}")
                
                # Nettoyer la propriété de test
                session.run("""
                MATCH (g:Glyph)
                WHERE g.test_property = 'test_value'
                REMOVE g.test_property
                """)
            except Exception as e:
                print(f"\nErreur lors du test SET: {e}")
        
        driver.close()
        return True
    
    except Exception as e:
        print(f"Erreur de connexion à Neo4j: {e}")
        return False

if __name__ == "__main__":
    print("Vérification de l'état de Neo4j...")
    success = check_neo4j_status()
    sys.exit(0 if success else 1)
