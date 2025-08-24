#!/usr/bin/env python3
# File: fix_neo4j_schema.py
# Description: Script pour corriger le schéma et les données Neo4j pour l'enrichissement topologique

from neo4j import GraphDatabase
import sys
import json
import time
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('fix_neo4j_schema')

# Configuration de la connexion
uri = "bolt://localhost:7687"
user = "neo4j"
password = "synergesis_password"

def fix_neo4j_schema():
    """
    Corrige le schéma et les données Neo4j pour assurer la compatibilité avec l'enrichissement topologique.
    """
    try:
        # Connexion à Neo4j
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            # 1. Vérifier l'état actuel
            result = session.run("MATCH (g:Glyph) RETURN count(g) as count")
            glyph_count = result.single()["count"]
            logger.info(f"Nombre de glyphes dans Neo4j: {glyph_count}")
            
            # 2. Ajouter la propriété natural_prompt si manquante
            result = session.run("""
            MATCH (g:Glyph)
            WHERE g.natural_prompt IS NULL
            SET g.natural_prompt = CASE
                WHEN g.details_text IS NOT NULL THEN g.details_text
                WHEN g.details_structured_json IS NOT NULL THEN g.details_structured_json
                ELSE 'Glyphe sans description'
            END
            RETURN count(g) as updated
            """)
            updated_prompt = result.single()["updated"]
            logger.info(f"Glyphes mis à jour avec natural_prompt: {updated_prompt}")
            
            # 3. Initialiser le degré de centralité à 0 pour tous les glyphes
            result = session.run("""
            MATCH (g:Glyph)
            SET g.degree_centrality = 0,
                g.in_degree = 0,
                g.out_degree = 0
            RETURN count(g) as updated
            """)
            updated_degree = result.single()["updated"]
            logger.info(f"Glyphes initialisés avec degree_centrality: {updated_degree}")
            
            # 4. Calculer le degré de centralité pour les glyphes avec des relations
            # Utilisation de COUNT() au lieu de size() pour compatibilité Neo4j 5
            result = session.run("""
            MATCH (g:Glyph)
            WITH g, 
                 COUNT { (g)--() } AS total_degree,
                 COUNT { (g)<--() } AS in_degree,
                 COUNT { (g)-->() } AS out_degree
            SET g.degree_centrality = total_degree,
                g.in_degree = in_degree,
                g.out_degree = out_degree
            RETURN count(g) as updated
            """)
            updated_degree_calc = result.single()["updated"]
            logger.info(f"Glyphes avec degré de centralité calculé: {updated_degree_calc}")
            
            # 5. Vérifier les glyphes avec degré > 0
            result = session.run("""
            MATCH (g:Glyph)
            WHERE g.degree_centrality > 0
            RETURN count(g) as count
            """)
            connected_glyphs = result.single()["count"]
            logger.info(f"Glyphes avec degré > 0: {connected_glyphs}")
            
            # 6. Créer des relations de similarité basées sur les tags communs
            # Utilisation de IS NOT NULL au lieu de exists() pour compatibilité Neo4j 5
            result = session.run("""
            MATCH (g1:Glyph), (g2:Glyph)
            WHERE g1 <> g2 AND g1.id < g2.id
              AND g1.tags IS NOT NULL AND g2.tags IS NOT NULL 
              AND size(g1.tags) > 0 AND size(g2.tags) > 0
            WITH g1, g2,
                 [tag IN g1.tags WHERE tag IN g2.tags] AS common_tags,
                 g1.tags + [tag IN g2.tags WHERE NOT tag IN g1.tags] AS all_tags
            WITH g1, g2, 
                 CASE WHEN size(all_tags) > 0 
                      THEN toFloat(size(common_tags)) / size(all_tags) 
                      ELSE 0 END AS jaccard_similarity
            WHERE jaccard_similarity >= 0.3
            MERGE (g1)-[r:SIMILAR_TO]-(g2)
            SET r.score = jaccard_similarity,
                r.calculated_at = timestamp()
            RETURN count(r) AS relationships_created
            """)
            similarity_rels = result.single()["relationships_created"]
            logger.info(f"Relations de similarité créées: {similarity_rels}")
            
            # 7. Recalculer le degré de centralité après ajout des relations de similarité
            result = session.run("""
            MATCH (g:Glyph)
            WITH g, 
                 COUNT { (g)--() } AS total_degree,
                 COUNT { (g)<--() } AS in_degree,
                 COUNT { (g)-->() } AS out_degree
            SET g.degree_centrality = total_degree,
                g.in_degree = in_degree,
                g.out_degree = out_degree
            RETURN count(g) as updated
            """)
            updated_degree_final = result.single()["updated"]
            logger.info(f"Glyphes avec degré de centralité recalculé: {updated_degree_final}")
            
            # 8. Générer un rapport final
            result = session.run("""
            MATCH (g:Glyph)
            RETURN min(g.degree_centrality) AS min_degree,
                   max(g.degree_centrality) AS max_degree,
                   avg(g.degree_centrality) AS avg_degree,
                   count(g) AS total_glyphs
            """)
            stats = result.single()
            logger.info(f"Statistiques finales:")
            logger.info(f"- Total glyphes: {stats['total_glyphs']}")
            logger.info(f"- Degré min: {stats['min_degree']}")
            logger.info(f"- Degré max: {stats['max_degree']}")
            logger.info(f"- Degré moyen: {stats['avg_degree']}")
            
            # 9. Générer des requêtes Cypher pour visualiser les résultats
            timestamp = int(time.time())
            cypher_file = f"/home/ubuntu/synergesis_pipeline/llm_tests/topology_results/fixed_schema_queries_{timestamp}.cypher"
            
            with open(cypher_file, 'w', encoding='utf-8') as f:
                f.write("// Requêtes Cypher pour visualiser les résultats après correction du schéma\n\n")
                
                f.write("// Afficher tous les glyphes avec leur degré de centralité\n")
                f.write("MATCH (g:Glyph)\n")
                f.write("RETURN g.id, g.natural_prompt, g.degree_centrality, g.in_degree, g.out_degree\n")
                f.write("ORDER BY g.degree_centrality DESC\n")
                f.write("LIMIT 10;\n\n")
                
                f.write("// Visualiser le graphe avec les relations de similarité\n")
                f.write("MATCH p=(g1:Glyph)-[r:SIMILAR_TO]-(g2:Glyph)\n")
                f.write("WHERE g1.id < g2.id\n")  # Pour éviter les doublons
                f.write("RETURN p\n")
                f.write("LIMIT 25;\n\n")
                
                f.write("// Visualiser le graphe avec les relations sémantiques\n")
                f.write("MATCH p=(g1:Glyph)-[r:RELATES_TO]->(g2:Glyph)\n")
                f.write("RETURN p\n")
                f.write("LIMIT 25;\n\n")
            
            logger.info(f"Requêtes Cypher sauvegardées dans: {cypher_file}")
            
        driver.close()
        return True
    
    except Exception as e:
        logger.error(f"Erreur lors de la correction du schéma Neo4j: {e}")
        return False

if __name__ == "__main__":
    logger.info("Correction du schéma Neo4j pour l'enrichissement topologique...")
    success = fix_neo4j_schema()
    sys.exit(0 if success else 1)
