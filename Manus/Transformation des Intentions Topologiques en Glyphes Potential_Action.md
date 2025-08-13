# Transformation des Intentions Topologiques en Glyphes Potential_Action

## Introduction

Ce document présente la transformation des intentions topologiques générées par le `TopologyAwareIntentionGenerator` en glyphes de type `potential_action` exploitables par le pipeline Synergesis. Ces structures GlyphData sont conçues pour être suffisamment précises et détaillées afin que le `sem-simulationengine-V01` puisse en simuler l'impact et qu'un agent puisse les exécuter si elles sont approuvées.

Nous nous concentrons sur deux types d'intentions topologiques :
1. `CONNECT_SIMILAR_GLYPHS` - pour établir des relations entre glyphes similaires
2. `CREATE_SOLUTION_FOR_PROBLEM_CLUSTER` - pour créer une solution répondant à un cluster de problèmes

## 1. Structure GlyphData pour CONNECT_SIMILAR_GLYPHS

### 1.1 Exemple d'Intention Topologique Source

```json
{
  "type": "CONNECT_SIMILAR_GLYPHS",
  "source_glyph": {
    "id": "techglyph_202505140900_1",
    "prompt": "Glyphe sans description",
    "concept_type": "PROBLEM"
  },
  "target_glyph": {
    "id": "techglyph_202505140910_1",
    "prompt": "Glyphe sans description",
    "concept_type": "PROBLEM"
  },
  "similarity_score": 0.8,
  "suggested_relation": "RELATED_TO_CONCEPT",
  "priority": "MEDIUM",
  "rationale": "Glyphes similaires (score: 0.80) sans relation sémantique directe",
  "suggested_actions": [
    "Créer une relation RELATED_TO_CONCEPT entre les glyphes",
    "Vérifier la pertinence sémantique de la connexion"
  ]
}
```

### 1.2 Structure GlyphData Correspondante

```json
{
  "id": "sem-potentialaction-TOPOGEN-CONNECT-20250605-001",
  "timestamp": 1749100674,
  "source": "topology_aware_intention_generator",
  "concept_type": "POTENTIAL_ACTION",
  "action_type": "CREATE_RELATIONSHIP",
  "status": "PROPOSED",
  "priority": 70,
  "confidence": 0.8,
  "tags": [
    "topology_generated",
    "similarity_based",
    "structural_improvement",
    "PROBLEM",
    "RELATED_TO_CONCEPT"
  ],
  "natural_prompt": "Créer une relation RELATED_TO_CONCEPT entre deux glyphes PROBLEM similaires (score: 0.80) pour améliorer la cohérence structurelle du graphe de connaissances.",
  "details_structured_json": {
    "action_parameters": {
      "source_glyph_id": "techglyph_202505140900_1",
      "target_glyph_id": "techglyph_202505140910_1",
      "relationship_type": "RELATED_TO_CONCEPT",
      "relationship_properties": {
        "similarity_score": 0.8,
        "generated_by": "topology_aware_intention_generator",
        "generation_timestamp": 1749100674,
        "rationale": "Glyphes similaires (score: 0.80) sans relation sémantique directe"
      }
    },
    "source_metadata": {
      "intention_type": "CONNECT_SIMILAR_GLYPHS",
      "source_glyph_concept_type": "PROBLEM",
      "target_glyph_concept_type": "PROBLEM",
      "similarity_score": 0.8,
      "original_priority": "MEDIUM"
    },
    "expected_impact": {
      "structural_metrics": {
        "graph_connectivity_delta": 0.05,
        "cluster_cohesion_delta": 0.1,
        "source_glyph_degree_delta": 1,
        "target_glyph_degree_delta": 1
      },
      "semantic_metrics": {
        "knowledge_coherence_delta": 0.15,
        "information_accessibility_delta": 0.1
      }
    },
    "execution_requirements": {
      "required_permissions": ["MODIFY_GRAPH_STRUCTURE"],
      "estimated_execution_time_ms": 500,
      "idempotency_key": "connect_similar_techglyph_202505140900_1_techglyph_202505140910_1",
      "preconditions": [
        "source_glyph_exists",
        "target_glyph_exists",
        "relationship_does_not_exist"
      ]
    },
    "rollback_procedure": {
      "action": "DELETE_RELATIONSHIP",
      "parameters": {
        "source_glyph_id": "techglyph_202505140900_1",
        "target_glyph_id": "techglyph_202505140910_1",
        "relationship_type": "RELATED_TO_CONCEPT"
      }
    }
  },
  "details_text": "Cette action propose de créer une relation sémantique de type RELATED_TO_CONCEPT entre deux glyphes PROBLEM qui ont été identifiés comme similaires par l'analyse topologique du graphe.\n\nGlyphe source : techglyph_202505140900_1 (PROBLEM)\nGlyphe cible : techglyph_202505140910_1 (PROBLEM)\nScore de similarité : 0.80\n\nJustification : Ces deux glyphes présentent une forte similarité structurelle et sémantique (score: 0.80) mais ne sont pas directement connectés dans le graphe de connaissances. Établir cette relation améliorera la cohérence du graphe et facilitera la navigation entre concepts similaires.\n\nImpact attendu :\n- Augmentation de la connectivité globale du graphe\n- Amélioration de la cohésion des clusters thématiques\n- Facilitation de la découverte de connaissances connexes\n\nCette action est générée automatiquement par le module d'enrichissement topologique pour améliorer la structure du graphe de connaissances Synergesis.",
  "metadata": {
    "topology_metrics": {
      "source_glyph_degree": 2,
      "target_glyph_degree": 2,
      "path_length_before": "INFINITY",
      "path_length_after": 1
    },
    "generation_context": {
      "generator_version": "1.0.0",
      "generation_timestamp": 1749100674,
      "generation_parameters": {
        "similarity_threshold": 0.6,
        "priority_mapping": {
          "HIGH": 90,
          "MEDIUM": 70,
          "LOW": 50
        }
      }
    }
  }
}
```

### 1.3 Description des Champs

- **id** : Identifiant unique du glyphe, suivant la convention `sem-potentialaction-TOPOGEN-[TYPE]-[DATE]-[SEQ]`
- **timestamp** : Horodatage Unix de la génération du glyphe
- **source** : Module qui a généré le glyphe
- **concept_type** : Type de concept, toujours `POTENTIAL_ACTION` pour les actions
- **action_type** : Type d'action à exécuter, ici `CREATE_RELATIONSHIP`
- **status** : État actuel de l'action, initialement `PROPOSED`
- **priority** : Priorité numérique (0-100), mappée depuis la priorité textuelle
- **confidence** : Niveau de confiance (0-1), dérivé du score de similarité
- **tags** : Liste de tags pour la catégorisation et la recherche
- **natural_prompt** : Description en langage naturel de l'action
- **details_structured_json** : Structure détaillée de l'action avec :
  - **action_parameters** : Paramètres spécifiques pour l'exécution
  - **source_metadata** : Métadonnées de l'intention d'origine
  - **expected_impact** : Impact attendu sur les métriques du graphe
  - **execution_requirements** : Prérequis pour l'exécution
  - **rollback_procedure** : Procédure pour annuler l'action si nécessaire
- **details_text** : Description détaillée en texte libre
- **metadata** : Métadonnées supplémentaires sur le contexte de génération

## 2. Structure GlyphData pour CREATE_SOLUTION_FOR_PROBLEM_CLUSTER

### 2.1 Exemple d'Intention Topologique Source

```json
{
  "type": "CREATE_SOLUTION_FOR_PROBLEM_CLUSTER",
  "target_cluster_id": "cluster_1",
  "problems": [
    {
      "id": "techglyph_202505140900_1",
      "prompt": "Glyphe sans description"
    },
    {
      "id": "techglyph_202505140910_1",
      "prompt": "Glyphe sans description"
    }
  ],
  "cluster_size": 2,
  "avg_similarity": 0.8,
  "priority": "HIGH",
  "rationale": "Cluster de 2 problèmes similaires sans solution commune",
  "suggested_actions": [
    "Créer un nouveau glyphe ProposedSolution",
    "Établir des relations ADDRESSES_PROBLEM vers chaque problème du cluster",
    "Considérer une approche unifiée qui résout tous les problèmes du cluster"
  ]
}
```

### 2.2 Structure GlyphData Correspondante

```json
{
  "id": "sem-potentialaction-TOPOGEN-CREATESOL-20250605-001",
  "timestamp": 1749100674,
  "source": "topology_aware_intention_generator",
  "concept_type": "POTENTIAL_ACTION",
  "action_type": "CREATE_SOLUTION_NODE",
  "status": "PROPOSED",
  "priority": 90,
  "confidence": 0.85,
  "tags": [
    "topology_generated",
    "cluster_based",
    "gap_filling",
    "PROBLEM",
    "PROPOSEDSOLUTION",
    "ADDRESSES_PROBLEM"
  ],
  "natural_prompt": "Créer un nouveau glyphe PROPOSEDSOLUTION qui adresse un cluster de 2 problèmes similaires (score moyen: 0.80) actuellement sans solution commune.",
  "details_structured_json": {
    "action_parameters": {
      "solution_glyph": {
        "id_template": "sem-proposedsolution-TOPOGEN-{timestamp}",
        "concept_type": "PROPOSEDSOLUTION",
        "natural_prompt_template": "Solution unifiée pour les problèmes liés à {common_themes} identifiés dans le cluster {cluster_id}",
        "tags": ["topology_generated", "cluster_solution", "unified_approach"]
      },
      "problem_glyphs": [
        "techglyph_202505140900_1",
        "techglyph_202505140910_1"
      ],
      "relationships_to_create": [
        {
          "source_template": "{solution_id}",
          "target": "techglyph_202505140900_1",
          "type": "ADDRESSES_PROBLEM",
          "properties": {
            "generated_by": "topology_aware_intention_generator",
            "generation_timestamp": 1749100674,
            "cluster_id": "cluster_1"
          }
        },
        {
          "source_template": "{solution_id}",
          "target": "techglyph_202505140910_1",
          "type": "ADDRESSES_PROBLEM",
          "properties": {
            "generated_by": "topology_aware_intention_generator",
            "generation_timestamp": 1749100674,
            "cluster_id": "cluster_1"
          }
        }
      ]
    },
    "source_metadata": {
      "intention_type": "CREATE_SOLUTION_FOR_PROBLEM_CLUSTER",
      "target_cluster_id": "cluster_1",
      "cluster_size": 2,
      "avg_similarity": 0.8,
      "original_priority": "HIGH"
    },
    "solution_generation_parameters": {
      "generation_method": "LLM_SYNTHESIS",
      "prompt_template": "Générer une solution unifiée qui adresse les problèmes suivants :\n{problem_descriptions}\n\nCes problèmes sont similaires (score moyen: {avg_similarity}) et appartiennent au même cluster thématique. La solution doit proposer une approche cohérente qui résout l'ensemble des problèmes identifiés.",
      "required_solution_aspects": [
        "unified_approach",
        "comprehensive_coverage",
        "technical_feasibility",
        "implementation_steps"
      ]
    },
    "expected_impact": {
      "structural_metrics": {
        "graph_connectivity_delta": 0.15,
        "problem_solution_ratio_delta": -0.05,
        "cluster_completeness_delta": 0.3
      },
      "semantic_metrics": {
        "knowledge_coherence_delta": 0.2,
        "solution_coverage_delta": 0.25
      }
    },
    "execution_requirements": {
      "required_permissions": ["CREATE_NODE", "CREATE_RELATIONSHIP"],
      "estimated_execution_time_ms": 5000,
      "idempotency_key": "create_solution_for_cluster_1",
      "preconditions": [
        "all_problem_glyphs_exist",
        "no_existing_solution_for_cluster",
        "llm_service_available"
      ]
    },
    "rollback_procedure": {
      "actions": [
        {
          "action": "DELETE_NODE",
          "parameters": {
            "node_id_template": "{created_solution_id}"
          }
        }
      ]
    }
  },
  "details_text": "Cette action propose de créer un nouveau glyphe de type PROPOSEDSOLUTION qui adresse un cluster de problèmes similaires actuellement sans solution commune.\n\nCluster cible : cluster_1\nProblèmes concernés :\n- techglyph_202505140900_1\n- techglyph_202505140910_1\nSimilarité moyenne : 0.80\n\nJustification : L'analyse topologique a identifié un cluster de 2 problèmes fortement similaires qui ne sont actuellement associés à aucune solution. Créer une solution unifiée qui adresse l'ensemble de ces problèmes permettra de combler cette lacune dans le graphe de connaissances et d'améliorer la complétude du domaine.\n\nProcédure d'exécution :\n1. Générer un nouveau glyphe PROPOSEDSOLUTION via LLM en synthétisant les problèmes identifiés\n2. Créer des relations ADDRESSES_PROBLEM entre la solution générée et chaque problème du cluster\n3. Vérifier la cohérence et la pertinence de la solution générée\n\nImpact attendu :\n- Amélioration de la complétude du graphe\n- Réduction du ratio problèmes/solutions\n- Augmentation de la cohérence des connaissances\n\nCette action est générée automatiquement par le module d'enrichissement topologique pour combler les lacunes structurelles du graphe de connaissances Synergesis.",
  "metadata": {
    "topology_metrics": {
      "cluster_problem_count": 2,
      "cluster_solution_count_before": 0,
      "cluster_solution_count_after": 1,
      "cluster_density_before": 0.5,
      "cluster_density_after": 0.67
    },
    "generation_context": {
      "generator_version": "1.0.0",
      "generation_timestamp": 1749100674,
      "generation_parameters": {
        "cluster_similarity_threshold": 0.7,
        "priority_mapping": {
          "HIGH": 90,
          "MEDIUM": 70,
          "LOW": 50
        }
      }
    },
    "problem_analysis": {
      "common_themes": ["à déterminer par analyse LLM des problèmes"],
      "estimated_complexity": "MEDIUM",
      "domain_specificity": "HIGH"
    }
  }
}
```

### 2.3 Description des Champs

- **id** : Identifiant unique du glyphe, suivant la convention `sem-potentialaction-TOPOGEN-[TYPE]-[DATE]-[SEQ]`
- **timestamp** : Horodatage Unix de la génération du glyphe
- **source** : Module qui a généré le glyphe
- **concept_type** : Type de concept, toujours `POTENTIAL_ACTION` pour les actions
- **action_type** : Type d'action à exécuter, ici `CREATE_SOLUTION_NODE`
- **status** : État actuel de l'action, initialement `PROPOSED`
- **priority** : Priorité numérique (0-100), mappée depuis la priorité textuelle
- **confidence** : Niveau de confiance (0-1), basé sur la similarité et la taille du cluster
- **tags** : Liste de tags pour la catégorisation et la recherche
- **natural_prompt** : Description en langage naturel de l'action
- **details_structured_json** : Structure détaillée de l'action avec :
  - **action_parameters** : Paramètres pour la création du nœud solution et des relations
  - **source_metadata** : Métadonnées de l'intention d'origine
  - **solution_generation_parameters** : Paramètres pour la génération de la solution via LLM
  - **expected_impact** : Impact attendu sur les métriques du graphe
  - **execution_requirements** : Prérequis pour l'exécution
  - **rollback_procedure** : Procédure pour annuler l'action si nécessaire
- **details_text** : Description détaillée en texte libre
- **metadata** : Métadonnées supplémentaires sur le contexte de génération et l'analyse des problèmes

## 3. Intégration dans le Pipeline Synergesis

### 3.1 Flux de Traitement

1. **Génération des Intentions** : Le `TopologyAwareIntentionGenerator` analyse le graphe et génère des intentions topologiques.

2. **Transformation en GlyphData** : Les intentions sont transformées en glyphes `potential_action` selon les structures définies ci-dessus.

3. **Ingestion dans Neo4j** : Les glyphes `potential_action` sont ingérés dans la base Neo4j comme tout autre glyphe.

4. **Simulation** : Le `sem-simulationengine-V01` simule l'impact de ces actions en utilisant les paramètres définis dans `details_structured_json`.

5. **Évaluation** : Le `sem-anticipatoryfeedback-V01` évalue le `simulated_outcome` pour déterminer si l'action est bénéfique.

6. **Décision** : Le `sem-metabolicprotocol-V01` décide de déclencher ou non l'action en fonction de l'évaluation.

7. **Exécution** : Si approuvée, l'action est exécutée par le `GlyphTopologyEngine` ou l'API "Glyph Ops".

8. **Monitoring** : La `MemoryApplicator` enregistre le succès/échec de l'action pour apprentissage futur.

### 3.2 Module de Transformation

Pour automatiser la transformation des intentions en glyphes `potential_action`, nous proposons un nouveau module `TopologyIntentionTransformer` :

```python
class TopologyIntentionTransformer:
    """
    Transforme les intentions topologiques en glyphes potential_action.
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        self.priority_mapping = {
            "HIGH": 90,
            "MEDIUM": 70,
            "LOW": 50
        }
        self.timestamp = int(time.time())
        self.date_str = time.strftime("%Y%m%d", time.localtime())
        self.sequence_counters = {}
    
    def transform_intentions(self, intentions):
        """
        Transforme une liste d'intentions en glyphes potential_action.
        
        Args:
            intentions: Liste d'intentions générées par TopologyAwareIntentionGenerator
            
        Returns:
            Liste de structures GlyphData pour les glyphes potential_action
        """
        glyph_data_list = []
        
        for intention in intentions:
            if intention["type"] == "CONNECT_SIMILAR_GLYPHS":
                glyph_data = self._transform_connect_similar_glyphs(intention)
                glyph_data_list.append(glyph_data)
            
            elif intention["type"] == "CREATE_SOLUTION_FOR_PROBLEM_CLUSTER":
                glyph_data = self._transform_create_solution_for_problem_cluster(intention)
                glyph_data_list.append(glyph_data)
            
            # Ajouter d'autres transformations pour les autres types d'intentions
        
        return glyph_data_list
    
    def _get_next_sequence(self, intention_type):
        """
        Génère un numéro de séquence unique pour un type d'intention.
        """
        if intention_type not in self.sequence_counters:
            self.sequence_counters[intention_type] = 1
        else:
            self.sequence_counters[intention_type] += 1
        
        return f"{self.sequence_counters[intention_type]:03d}"
    
    def _transform_connect_similar_glyphs(self, intention):
        """
        Transforme une intention CONNECT_SIMILAR_GLYPHS en glyphe potential_action.
        """
        # Implémentation de la transformation selon la structure définie
        # ...
    
    def _transform_create_solution_for_problem_cluster(self, intention):
        """
        Transforme une intention CREATE_SOLUTION_FOR_PROBLEM_CLUSTER en glyphe potential_action.
        """
        # Implémentation de la transformation selon la structure définie
        # ...
```

## 4. Validation et Tests

Pour valider l'intégrabilité et la précision des glyphes `potential_action` générés, nous proposons les tests suivants :

1. **Tests Unitaires** : Vérifier que la transformation des intentions en glyphes est correcte et complète.

2. **Tests d'Intégration** : Vérifier que les glyphes générés peuvent être ingérés dans Neo4j et traités par le pipeline Synergesis.

3. **Tests de Simulation** : Vérifier que le `sem-simulationengine-V01` peut simuler correctement l'impact des actions.

4. **Tests d'Exécution** : Vérifier que les actions peuvent être exécutées correctement par le `GlyphTopologyEngine`.

5. **Tests de Rollback** : Vérifier que les procédures de rollback fonctionnent correctement en cas d'échec.

## 5. Conclusion

La transformation des intentions topologiques en glyphes `potential_action` permet d'intégrer les logiques réflexives topologiques dans le pipeline d'action et de simulation de Synergesis. Les structures GlyphData proposées sont suffisamment précises et détaillées pour permettre la simulation et l'exécution des actions, tout en étant compatibles avec l'architecture existante.

Cette approche permet de fermer la boucle entre l'analyse topologique du graphe et l'action concrète pour améliorer sa structure, transformant ainsi Synergesis en un système capable non seulement de comprendre la structure de son propre savoir, mais aussi d'agir pour l'améliorer de manière autonome.
