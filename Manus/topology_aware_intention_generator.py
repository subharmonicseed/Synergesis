#!/usr/bin/env python3
# File: topology_aware_intention_generator.py
# Description: Module de génération d'intentions basées sur la topologie pour Synergesis

import time
import logging
import json
import os
from typing import Dict, List, Any, Optional, Set, Tuple

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('topology_aware_intention_generator')

class TopologyAwareIntentionGenerator:
    """
    Extension de l'IntentionGenerator pour intégrer l'analyse topologique du graphe.
    Génère des intentions stratégiques basées sur la structure du réseau de glyphes.
    """
    
    def __init__(self, neo4j_connector, config=None):
        """
        Initialise le générateur d'intentions avec conscience topologique.
        
        Args:
            neo4j_connector: Connecteur Neo4j pour l'accès à la base de données
            config: Configuration optionnelle
        """
        self.neo4j_connector = neo4j_connector
        self.config = config or {}
        self.topology_thresholds = {
            'high_impact_threshold': 4,  # Seuil pour considérer un glyphe comme à haut impact
            'bridge_threshold': 0.5,  # Seuil pour considérer un glyphe comme pont entre communautés
            'similarity_action_threshold': 0.6,  # Seuil pour suggérer des actions basées sur la similarité
        }
        
        # Charger les seuils depuis la configuration si disponibles
        if 'topology_thresholds' in self.config:
            self.topology_thresholds.update(self.config['topology_thresholds'])
        
        logger.info(f"TopologyAwareIntentionGenerator initialisé avec les seuils: {self.topology_thresholds}")
    
    def generate_topology_based_intentions(self, observations=None):
        """
        Génère des intentions basées sur la topologie du graphe.
        
        Args:
            observations: Observations optionnelles du ReflexiveCortex
            
        Returns:
            Liste d'intentions stratégiques
        """
        intentions = []
        
        # Traiter les observations si fournies
        if observations:
            intentions.extend(self._process_reflexive_observations(observations))
        
        # Générer des intentions pour connecter les glyphes isolés
        connect_isolated_intentions = self._generate_connect_isolated_intentions()
        intentions.extend(connect_isolated_intentions)
        
        # Générer des intentions pour enrichir les hubs
        enrich_hub_intentions = self._generate_enrich_hub_intentions()
        intentions.extend(enrich_hub_intentions)
        
        # Générer des intentions pour résoudre les clusters de problèmes
        solve_problem_cluster_intentions = self._generate_solve_problem_cluster_intentions()
        intentions.extend(solve_problem_cluster_intentions)
        
        # Générer des intentions pour créer des liens entre glyphes similaires
        connect_similar_intentions = self._generate_connect_similar_intentions()
        intentions.extend(connect_similar_intentions)
        
        return intentions
    
    def _process_reflexive_observations(self, observations):
        """
        Traite les observations du ReflexiveCortex pour générer des intentions.
        
        Args:
            observations: Liste d'observations du ReflexiveCortex
            
        Returns:
            Liste d'intentions générées à partir des observations
        """
        intentions = []
        
        for obs in observations:
            if obs['type'] == 'ISOLATED_GLYPHS_DETECTED':
                # Générer des intentions pour connecter les glyphes isolés
                for glyph in obs['data']:
                    intentions.append({
                        'type': 'CONNECT_ISOLATED_GLYPH',
                        'target_glyph_id': glyph['g.id'],
                        'target_prompt': glyph['g.natural_prompt'],
                        'priority': 'HIGH',
                        'rationale': f"Glyphe isolé détecté: {glyph['g.natural_prompt']}",
                        'suggested_actions': [
                            'Rechercher des glyphes conceptuellement liés',
                            'Créer au moins 2-3 relations pertinentes'
                        ]
                    })
            
            elif obs['type'] == 'PROBLEM_CLUSTERS_WITHOUT_SOLUTIONS':
                # Générer des intentions pour résoudre les clusters de problèmes
                for cluster in obs['data']:
                    intentions.append({
                        'type': 'SOLVE_PROBLEM_CLUSTER',
                        'target_cluster': cluster,
                        'priority': 'HIGH',
                        'rationale': f"Cluster de {cluster['size']} problèmes similaires sans solutions",
                        'suggested_actions': [
                            'Créer un glyphe ProposedSolution qui adresse ces problèmes',
                            'Établir des relations ADDRESSES_PROBLEM vers chaque problème du cluster'
                        ]
                    })
        
        return intentions
    
    def _generate_connect_isolated_intentions(self):
        """
        Génère des intentions pour connecter les glyphes isolés.
        
        Returns:
            Liste d'intentions pour connecter les glyphes isolés
        """
        query = """
        MATCH (g:Glyph)
        WHERE g.degree_centrality = 0
        RETURN g.id, g.natural_prompt, g.concept_type
        """
        isolated_glyphs = self.neo4j_connector.execute_query(query)
        
        intentions = []
        for glyph in isolated_glyphs:
            # Trouver des glyphes potentiellement liés par concept_type
            related_query = """
            MATCH (g:Glyph)
            WHERE g.concept_type = $concept_type AND g.id <> $glyph_id
            RETURN g.id, g.natural_prompt
            LIMIT 3
            """
            params = {'concept_type': glyph['g.concept_type'], 'glyph_id': glyph['g.id']}
            related_glyphs = self.neo4j_connector.execute_query(related_query, params)
            
            suggested_connections = []
            for related in related_glyphs:
                suggested_connections.append({
                    'glyph_id': related['g.id'],
                    'prompt': related['g.natural_prompt'],
                    'relation_type': 'RELATED_TO_CONCEPT'
                })
            
            intentions.append({
                'type': 'CONNECT_ISOLATED_GLYPH',
                'target_glyph_id': glyph['g.id'],
                'target_prompt': glyph['g.natural_prompt'],
                'priority': 'HIGH',
                'rationale': 'Glyphe complètement isolé dans le graphe',
                'suggested_connections': suggested_connections
            })
        
        return intentions
    
    def _generate_enrich_hub_intentions(self):
        """
        Génère des intentions pour enrichir les glyphes à haute centralité (hubs).
        
        Returns:
            Liste d'intentions pour enrichir les hubs
        """
        query = """
        MATCH (g:Glyph)
        WHERE g.degree_centrality >= $threshold
        RETURN g.id, g.natural_prompt, g.concept_type, g.degree_centrality
        ORDER BY g.degree_centrality DESC
        LIMIT 5
        """
        params = {'threshold': self.topology_thresholds['high_impact_threshold']}
        hub_glyphs = self.neo4j_connector.execute_query(query, params)
        
        intentions = []
        for glyph in hub_glyphs:
            intentions.append({
                'type': 'ENRICH_HUB_GLYPH',
                'target_glyph_id': glyph['g.id'],
                'target_prompt': glyph['g.natural_prompt'],
                'centrality': glyph['g.degree_centrality'],
                'priority': 'MEDIUM',
                'rationale': f"Glyphe central avec {glyph['g.degree_centrality']} connexions",
                'suggested_actions': [
                    'Enrichir la description avec plus de détails',
                    'Vérifier la qualité et la pertinence des connexions existantes',
                    'Considérer comme point focal pour l\'organisation des connaissances'
                ]
            })
        
        return intentions
    
    def _generate_solve_problem_cluster_intentions(self):
        """
        Génère des intentions pour résoudre les clusters de problèmes sans solutions.
        
        Returns:
            Liste d'intentions pour résoudre les clusters de problèmes
        """
        query = """
        MATCH (p1:Glyph)-[r:SIMILAR_TO]-(p2:Glyph)
        WHERE p1.concept_type = 'PROBLEM' AND p2.concept_type = 'PROBLEM'
        AND r.score >= $similarity_threshold
        AND NOT (p1)-[:RELATES_TO]->(:Glyph {concept_type: 'PROPOSEDSOLUTION'})
        AND NOT (p2)-[:RELATES_TO]->(:Glyph {concept_type: 'PROPOSEDSOLUTION'})
        AND p1.id < p2.id  // Pour éviter les doublons
        RETURN p1.id, p1.natural_prompt, p2.id, p2.natural_prompt, r.score
        ORDER BY r.score DESC
        """
        params = {'similarity_threshold': self.topology_thresholds['similarity_action_threshold']}
        problem_pairs = self.neo4j_connector.execute_query(query, params)
        
        # Regrouper les problèmes en clusters
        clusters = {}
        for row in problem_pairs:
            p1_id = row['p1.id']
            p1_prompt = row['p1.natural_prompt']
            p2_id = row['p2.id']
            p2_prompt = row['p2.natural_prompt']
            score = row['r.score']
            
            # Ajouter au cluster existant ou créer un nouveau
            cluster_found = False
            for cluster_id, cluster in clusters.items():
                if p1_id in cluster['problem_ids'] or p2_id in cluster['problem_ids']:
                    cluster['problem_ids'].add(p1_id)
                    cluster['problem_ids'].add(p2_id)
                    cluster['problems'].append({'id': p1_id, 'prompt': p1_prompt})
                    cluster['problems'].append({'id': p2_id, 'prompt': p2_prompt})
                    cluster_found = True
                    break
            
            if not cluster_found:
                cluster_id = f"cluster_{len(clusters) + 1}"
                clusters[cluster_id] = {
                    'problem_ids': {p1_id, p2_id},
                    'problems': [
                        {'id': p1_id, 'prompt': p1_prompt},
                        {'id': p2_id, 'prompt': p2_prompt}
                    ],
                    'avg_similarity': score
                }
        
        # Dédupliquer les problèmes dans chaque cluster
        for cluster_id, cluster in clusters.items():
            unique_problems = {}
            for problem in cluster['problems']:
                unique_problems[problem['id']] = problem
            cluster['problems'] = list(unique_problems.values())
            cluster['size'] = len(cluster['problems'])
        
        # Générer des intentions pour chaque cluster
        intentions = []
        for cluster_id, cluster in clusters.items():
            if cluster['size'] >= 2:  # Au moins 2 problèmes dans le cluster
                intentions.append({
                    'type': 'CREATE_SOLUTION_FOR_PROBLEM_CLUSTER',
                    'target_cluster_id': cluster_id,
                    'problems': cluster['problems'],
                    'cluster_size': cluster['size'],
                    'avg_similarity': cluster['avg_similarity'],
                    'priority': 'HIGH',
                    'rationale': f"Cluster de {cluster['size']} problèmes similaires sans solution commune",
                    'suggested_actions': [
                        'Créer un nouveau glyphe ProposedSolution',
                        'Établir des relations ADDRESSES_PROBLEM vers chaque problème du cluster',
                        'Considérer une approche unifiée qui résout tous les problèmes du cluster'
                    ]
                })
        
        return intentions
    
    def _generate_connect_similar_intentions(self):
        """
        Génère des intentions pour créer des liens sémantiques entre glyphes similaires.
        
        Returns:
            Liste d'intentions pour connecter les glyphes similaires
        """
        query = """
        MATCH (g1:Glyph)-[r:SIMILAR_TO]-(g2:Glyph)
        WHERE r.score >= $similarity_threshold
        AND NOT (g1)-[:RELATES_TO]-(g2)
        AND g1.id < g2.id  // Pour éviter les doublons
        RETURN g1.id, g1.natural_prompt, g1.concept_type,
               g2.id, g2.natural_prompt, g2.concept_type,
               r.score
        ORDER BY r.score DESC
        LIMIT 10
        """
        params = {'similarity_threshold': self.topology_thresholds['similarity_action_threshold']}
        similar_pairs = self.neo4j_connector.execute_query(query, params)
        
        intentions = []
        for pair in similar_pairs:
            # Déterminer le type de relation sémantique approprié
            relation_type = self._suggest_semantic_relation_type(
                pair['g1.concept_type'], 
                pair['g2.concept_type']
            )
            
            intentions.append({
                'type': 'CONNECT_SIMILAR_GLYPHS',
                'source_glyph': {
                    'id': pair['g1.id'],
                    'prompt': pair['g1.natural_prompt'],
                    'concept_type': pair['g1.concept_type']
                },
                'target_glyph': {
                    'id': pair['g2.id'],
                    'prompt': pair['g2.natural_prompt'],
                    'concept_type': pair['g2.concept_type']
                },
                'similarity_score': pair['r.score'],
                'suggested_relation': relation_type,
                'priority': 'MEDIUM',
                'rationale': f"Glyphes similaires (score: {pair['r.score']:.2f}) sans relation sémantique directe",
                'suggested_actions': [
                    f"Créer une relation {relation_type} entre les glyphes",
                    "Vérifier la pertinence sémantique de la connexion"
                ]
            })
        
        return intentions
    
    def _suggest_semantic_relation_type(self, source_type, target_type):
        """
        Suggère un type de relation sémantique approprié entre deux types de concepts.
        
        Args:
            source_type: Type du glyphe source
            target_type: Type du glyphe cible
            
        Returns:
            Type de relation suggéré
        """
        # Matrice de suggestion de relations basée sur les types de concepts
        relation_matrix = {
            ('PROBLEM', 'PROBLEM'): 'RELATED_TO_CONCEPT',
            ('PROBLEM', 'PROPOSEDSOLUTION'): 'ADDRESSES_PROBLEM',
            ('PROPOSEDSOLUTION', 'PROBLEM'): 'ADDRESSES_PROBLEM',
            ('TECHNICALCONCEPT', 'TECHNICALCONCEPT'): 'RELATED_TO_CONCEPT',
            ('TECHNICALCONCEPT', 'PROPOSEDSOLUTION'): 'IMPLEMENTS_CONCEPT',
            ('PROPOSEDSOLUTION', 'TECHNICALCONCEPT'): 'IMPLEMENTS_CONCEPT',
            ('KEYCONTRIBUTION', 'KEYCONTRIBUTION'): 'RELATED_TO_CONCEPT',
            ('KEYCONTRIBUTION', 'TECHNICALCONCEPT'): 'RELATED_TO_CONCEPT',
            ('TECHNICALCONCEPT', 'KEYCONTRIBUTION'): 'RELATED_TO_CONCEPT',
            ('TOOLFRAMEWORK', 'PROPOSEDSOLUTION'): 'IMPLEMENTS_CONCEPT',
            ('PROPOSEDSOLUTION', 'TOOLFRAMEWORK'): 'IMPLEMENTS_CONCEPT',
        }
        
        # Retourner le type de relation suggéré ou une relation générique par défaut
        return relation_matrix.get((source_type, target_type), 'RELATED_TO_CONCEPT')
    
    def save_intentions(self, intentions, output_dir="/home/ubuntu/synergesis_pipeline/reflexive_results"):
        """
        Sauvegarde les intentions dans un fichier JSON.
        
        Args:
            intentions: Liste d'intentions 
(Content truncated due to size limit. Use line ranges to read in chunks)