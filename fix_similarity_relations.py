#!/usr/bin/env python3
# File: fix_similarity_relations.py
# Description: Script pour corriger la création des relations de similarité entre glyphes

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
logger = logging.getLogger('fix_similarity_relations')

# Configuration de la connexion
uri = "bolt://localhost:7687"
user = "neo4j"
password = "synergesis_password"

def fix_similarity_relations():
    """
    Corrige la création des relations de similarité entre glyphes.
    """
    try:
        # Connexion à Neo4j
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            # 1. Vérifier l'état actuel des glyphes et des tags
            result = session.run("""
            MATCH (g:Glyph)
            RETURN count(g) as total_glyphs,
                   count(g.tags) as glyphs_with_tags
            """)
            stats = result.single()
            total_glyphs = stats["total_glyphs"]
            glyphs_with_tags = stats["glyphs_with_tags"]
            logger.info(f"État actuel: {total_glyphs} glyphes, {glyphs_with_tags} avec tags")
            
            # 2. Vérifier le format des tags
            result = session.run("""
            MATCH (g:Glyph)
            WHERE g.tags IS NOT NULL
            RETURN g.id, g.tags
            LIMIT 5
            """)
            
            logger.info("Échantillon de tags:")
            for record in result:
                glyph_id = record["g.id"]
                tags = record["g.tags"]
                logger.info(f"- Glyphe {glyph_id}: {tags} (type: {type(tags).__name__})")
            
            # 3. Ajouter des tags par défaut si nécessaire
            result = session.run("""
            MATCH (g:Glyph)
            WHERE g.tags IS NULL OR size(g.tags) = 0
            SET g.tags = CASE
                WHEN g.concept_type IS NOT NULL THEN [g.concept_type]
                ELSE ['UNKNOWN']
            END
            RETURN count(g) as updated
            """)
            updated_tags = result.single()["updated"]
            logger.info(f"Glyphes mis à jour avec tags par défaut: {updated_tags}")
            
            # 4. Créer des relations de similarité basées sur les tags communs
            # Approche simplifiée pour garantir la création de relations
            result = session.run("""
            MATCH (g1:Glyph), (g2:Glyph)
            WHERE g1 <> g2 AND g1.id < g2.id
              AND g1.concept_type = g2.concept_type
            MERGE (g1)-[r:SIMILAR_TO]-(g2)
            SET r.score = 0.8,
                r.reason = 'Même type de concept',
                r.calculated_at = timestamp()
            RETURN count(r) AS relationships_created
            """)
            similarity_rels_concept = result.single()["relationships_created"]
            logger.info(f"Relations de similarité créées (même concept_type): {similarity_rels_concept}")
            
            # 5. Créer des relations de similarité supplémentaires basées sur les tags communs
            result = session.run("""
            MATCH (g1:Glyph), (g2:Glyph)
            WHERE g1 <> g2 AND g1.id < g2.id
              AND g1.concept_type <> g2.concept_type
              AND g1.tags IS NOT NULL AND g2.tags IS NOT NULL
              AND size([tag IN g1.tags WHERE tag IN g2.tags]) > 0
            MERGE (g1)-[r:SIMILAR_TO]-(g2)
            SET r.score = 0.5,
                r.reason = 'Tags communs',
                r.calculated_at = timestamp()
            RETURN count(r) AS relationships_created
            """)
            similarity_rels_tags = result.single()["relationships_created"]
            logger.info(f"Relations de similarité créées (tags communs): {similarity_rels_tags}")
            
            # 6. Vérifier les relations de similarité créées
            result = session.run("""
            MATCH ()-[r:SIMILAR_TO]-()
            RETURN count(r)/2 AS similarity_count
            """)
            similarity_count = result.single()["similarity_count"]
            logger.info(f"Total des relations de similarité: {similarity_count}")
            
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
            updated_degree = result.single()["updated"]
            logger.info(f"Glyphes avec degré de centralité recalculé: {updated_degree}")
            
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
            cypher_file = f"/home/ubuntu/synergesis_pipeline/llm_tests/topology_results/similarity_relations_queries_{timestamp}.cypher"
            
            with open(cypher_file, 'w', encoding='utf-8') as f:
                f.write("// Requêtes Cypher pour visualiser les relations de similarité\n\n")
                
                f.write("// Afficher toutes les relations de similarité\n")
                f.write("MATCH (g1:Glyph)-[r:SIMILAR_TO]-(g2:Glyph)\n")
                f.write("WHERE g1.id < g2.id\n")  # Pour éviter les doublons
                f.write("RETURN g1.id, g1.natural_prompt, g2.id, g2.natural_prompt, r.score, r.reason\n")
                f.write("ORDER BY r.score DESC\n")
                f.write("LIMIT 10;\n\n")
                
                f.write("// Visualiser le graphe avec les relations de similarité\n")
                f.write("MATCH p=(g1:Glyph)-[r:SIMILAR_TO]-(g2:Glyph)\n")
                f.write("WHERE g1.id < g2.id\n")  # Pour éviter les doublons
                f.write("RETURN p\n")
                f.write("LIMIT 25;\n\n")
                
                f.write("// Visualiser le graphe complet avec tous les types de relations\n")
                f.write("MATCH p=(g1:Glyph)-[r]-(g2:Glyph)\n")
                f.write("RETURN p\n")
                f.write("LIMIT 50;\n\n")
            
            logger.info(f"Requêtes Cypher sauvegardées dans: {cypher_file}")
            
        driver.close()
        return True
    
    except Exception as e:
        logger.error(f"Erreur lors de la correction des relations de similarité: {e}")
        return False

if __name__ == "__main__":
    logger.info("Correction des relations de similarité entre glyphes...")
    success = fix_similarity_relations()
    sys.exit(0 if success else 1)
