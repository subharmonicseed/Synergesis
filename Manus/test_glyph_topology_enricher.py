#!/usr/bin/env python3
# File: test_glyph_topology_enricher.py
# Description: Tests pour le module d'enrichissement topologique des glyphes

import os
import sys
import json
import time
import unittest
from datetime import datetime

# Ajouter le répertoire parent au path pour l'import des modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.glyph_topology_enricher import GlyphTopologyEnricher

class TestGlyphTopologyEnricher(unittest.TestCase):
    """Tests pour le module GlyphTopologyEnricher."""
    
    @classmethod
    def setUpClass(cls):
        """Configuration initiale pour tous les tests."""
        # Vérifier si les variables d'environnement sont définies
        cls.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        cls.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        cls.neo4j_password = os.getenv("NEO4J_PASSWORD", "synergesis_password")
        
        # Créer l'enrichisseur
        cls.enricher = GlyphTopologyEnricher(
            uri=cls.neo4j_uri,
            user=cls.neo4j_user,
            password=cls.neo4j_password
        )
        
        # Vérifier la connexion
        if not cls.enricher.test_connection():
            raise ConnectionError("Impossible de se connecter à Neo4j. Vérifiez les paramètres de connexion.")
        
        print(f"Connexion à Neo4j établie: {cls.neo4j_uri}")
    
    @classmethod
    def tearDownClass(cls):
        """Nettoyage après tous les tests."""
        if cls.enricher:
            cls.enricher.close()
    
    def test_01_connection(self):
        """Test de la connexion à Neo4j."""
        self.assertTrue(self.enricher.test_connection())
    
    def test_02_compute_degree_centrality(self):
        """Test du calcul du degré de centralité."""
        print("\n--- Test du calcul du degré de centralité ---")
        stats = self.enricher.compute_and_store_degree_centrality()
        
        # Vérifier que le calcul s'est bien déroulé
        self.assertEqual(stats["status"], "success")
        self.assertGreaterEqual(stats["glyphs_processed"], 0)
        self.assertGreaterEqual(stats["properties_set"], 0)
        
        # Afficher les statistiques
        print(f"Glyphes traités: {stats['glyphs_processed']}")
        print(f"Propriétés définies: {stats['properties_set']}")
        if "min_degree" in stats:
            print(f"Degré min: {stats['min_degree']}, max: {stats['max_degree']}, moyen: {stats['avg_degree']:.2f}")
        
        # Afficher les glyphes avec le plus haut degré de centralité
        if "top_glyphs" in stats and stats["top_glyphs"]:
            print("\nTop glyphes par degré de centralité:")
            for i, glyph in enumerate(stats["top_glyphs"]):
                print(f"{i+1}. {glyph['natural_prompt'][:50]}... (Degré: {glyph['degree_centrality']})")
    
    def test_03_compute_similarity_links(self):
        """Test du calcul des liens de similarité."""
        print("\n--- Test du calcul des liens de similarité ---")
        threshold = 0.3  # Seuil plus bas pour les tests
        stats = self.enricher.compute_and_store_similarity_links(threshold)
        
        # Vérifier que le calcul s'est bien déroulé
        self.assertEqual(stats["status"], "success")
        self.assertGreaterEqual(stats["relationships_created"], 0)
        
        # Afficher les statistiques
        print(f"Relations de similarité créées: {stats['relationships_created']}")
        if "glyphs_with_similarity" in stats:
            print(f"Glyphes avec relations de similarité: {stats['glyphs_with_similarity']}")
        
        # Afficher les paires de glyphes les plus similaires
        if "top_similar_pairs" in stats and stats["top_similar_pairs"]:
            print("\nTop paires de glyphes similaires:")
            for i, pair in enumerate(stats["top_similar_pairs"]):
                print(f"{i+1}. {pair['glyph1_prompt'][:30]}... & {pair['glyph2_prompt'][:30]}... "
                      f"(Score: {pair['similarity_score']:.2f})")
    
    def test_04_generate_topology_report(self):
        """Test de la génération du rapport de topologie."""
        print("\n--- Test de la génération du rapport de topologie ---")
        report = self.enricher.generate_topology_report()
        
        # Vérifier que la génération s'est bien déroulée
        self.assertEqual(report["status"], "success")
        self.assertIn("node_count", report)
        self.assertIn("relationship_count", report)
        
        # Afficher les statistiques générales
        print(f"Graphe: {report['node_count']} nœuds, {report['relationship_count']} relations")
        
        # Afficher la distribution des types de concepts
        if "concept_types" in report and report["concept_types"]:
            print("\nDistribution des types de concepts:")
            for concept in report["concept_types"]:
                print(f"- {concept['type']}: {concept['count']} glyphes")
        
        # Afficher la distribution des types de relations
        if "relation_types" in report and report["relation_types"]:
            print("\nDistribution des types de relations:")
            for relation in report["relation_types"]:
                print(f"- {relation['type']}: {relation['count']} relations")
        
        # Afficher les statistiques d'enrichissement
        if "enrichment_stats" in report:
            stats = report["enrichment_stats"]
            print(f"\nStatistiques d'enrichissement:")
            print(f"- Glyphes avec degré de centralité: {stats['glyphs_with_degree']}/{stats['total_glyphs']}")
            print(f"- Degré moyen: {stats['avg_degree']:.2f}")
        
        # Afficher les statistiques de similarité
        if "similarity_stats" in report:
            stats = report["similarity_stats"]
            print(f"\nStatistiques de similarité:")
            print(f"- Relations de similarité: {stats['relationship_count']}")
            print(f"- Score moyen: {stats['avg_score']:.2f}")
        
        # Sauvegarder le rapport dans un fichier JSON
        timestamp = int(time.time())
        report_file = f"/home/ubuntu/synergesis_pipeline/llm_tests/topology_results/topology_report_{timestamp}.json"
        
        # Créer le répertoire s'il n'existe pas
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nRapport sauvegardé dans: {report_file}")
        
        # Générer également un fichier de requêtes Cypher pour visualiser les résultats
        cypher_file = f"/home/ubuntu/synergesis_pipeline/llm_tests/topology_results/topology_queries_{timestamp}.cypher"
        
        with open(cypher_file, 'w', encoding='utf-8') as f:
            f.write("// Requêtes Cypher pour visualiser les résultats de l'enrichissement topologique\n\n")
            
            f.write("// Afficher tous les glyphes avec leur degré de centralité\n")
            f.write("MATCH (g:Glyph)\n")
            f.write("WHERE g.degree_centrality IS NOT NULL\n")
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
            
            f.write("// Afficher les glyphes les plus centraux par type de concept\n")
            f.write("MATCH (g:Glyph)\n")
            f.write("WHERE g.concept_type IS NOT NULL AND g.degree_centrality IS NOT NULL\n")
            f.write("RETURN g.concept_type, g.id, g.natural_prompt, g.degree_centrality\n")
            f.write("ORDER BY g.concept_type, g.degree_centrality DESC\n")
            f.write("LIMIT 15;\n\n")
            
            f.write("// Identifier les communautés potentielles basées sur les relations de similarité\n")
            f.write("MATCH (g:Glyph)-[r:SIMILAR_TO]-(g2:Glyph)\n")
            f.write("WHERE r.score > 0.5\n")
            f.write("WITH g, collect(g2) as similar_glyphs\n")
            f.write("WHERE size(similar_glyphs) > 1\n")
            f.write("RETURN g.id, g.natural_prompt, [glyph in similar_glyphs | glyph.id] as similar_ids, size(similar_glyphs) as community_size\n")
            f.write("ORDER BY community_size DESC\n")
            f.write("LIMIT 10;\n")
        
        print(f"Requêtes Cypher sauvegardées dans: {cypher_file}")

if __name__ == "__main__":
    unittest.main()
