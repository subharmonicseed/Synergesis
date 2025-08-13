# Documentation du Pipeline Réflexif Topologique Synergesis

## Vue d'ensemble

Le Pipeline Réflexif Topologique Synergesis est un système avancé d'analyse et d'enrichissement de graphes de connaissances. Il permet d'analyser la structure topologique d'un graphe Neo4j, de détecter des anomalies structurelles, de générer des intentions stratégiques et d'exécuter des actions pour améliorer la cohérence et la richesse du graphe.

Cette documentation présente l'architecture du pipeline, ses composants principaux, et fournit des exemples d'utilisation pour les différentes fonctionnalités.

## Architecture

Le pipeline est composé de plusieurs modules interconnectés :

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  Enrichissement     │     │  Analyse Réflexive  │     │  Génération         │
│  Topologique        │────▶│  Topologique        │────▶│  d'Intentions       │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
           │                                                      │
           │                                                      ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  Base de            │     │  Exécution          │     │  Transformation     │
│  Connaissances Neo4j│◀────│  d'Actions          │◀────│  en Glyphes         │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

### Couches transversales

Le pipeline intègre trois couches transversales pour garantir robustesse, validation et observabilité :

1. **Couche défensive** : Décorateurs Python qui gèrent les propriétés manquantes, valident les données et assurent la résilience
2. **Couche de validation** : Schémas Pydantic pour la validation stricte des structures de données
3. **Couche d'observabilité** : Instrumentation Prometheus pour le monitoring des performances et des erreurs

## Installation

### Prérequis

- Python 3.9+
- Neo4j 5.x
- Docker (optionnel)

### Installation depuis les sources

```bash
# Cloner le dépôt
git clone https://github.com/synergesis/synergesis-pipeline.git
cd synergesis-pipeline

# Installer les dépendances
pip install -r requirements.txt

# Installer le package en mode développement
pip install -e .
```

### Installation avec Docker

```bash
# Construire l'image
docker build -t synergesis/pipeline .

# Exécuter le conteneur
docker run -d --name synergesis-pipeline \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=synergesis \
  -p 8000:8000 \
  synergesis/pipeline
```

## Configuration

Le pipeline peut être configuré via des variables d'environnement :

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| NEO4J_URI | URI de connexion à Neo4j | bolt://localhost:7687 |
| NEO4J_USER | Nom d'utilisateur Neo4j | neo4j |
| NEO4J_PASSWORD | Mot de passe Neo4j | synergesis |
| METRICS_PORT | Port pour l'exposition des métriques Prometheus | 8000 |
| EXPOSE_METRICS | Activer l'exposition des métriques | true |
| PUSH_GATEWAY_URL | URL du Push Gateway Prometheus | "" |

## Utilisation

### Exécution du pipeline complet

```bash
# Exécution simple
python -m src.synergesis_reflexive_pipeline

# Avec exposition des métriques
python -m src.synergesis_reflexive_pipeline --expose-metrics

# En mode simulation uniquement (sans exécution des actions)
python -m src.synergesis_reflexive_pipeline --simulate-only
```

### Utilisation programmatique

```python
from src.glyph_topology_enricher import GlyphTopologyEnricher
from src.topology_aware_reflexive_cortex import TopologyAwareReflexiveCortex
from src.topology_aware_intention_generator import TopologyAwareIntentionGenerator
from src.topology_intention_transformer import TopologyIntentionTransformer
from src.refactored_glyph_action_executor import GlyphActionExecutor
from src.metrics import MetricsManager

# Initialisation des composants
metrics_manager = MetricsManager(expose_http=True, http_port=8000)
neo4j_connector = Neo4jConnector("bolt://localhost:7687", "neo4j", "synergesis")

# Enrichissement topologique
enricher = GlyphTopologyEnricher(neo4j_connector, metrics_manager)
enrichment_results = enricher.enrich_graph()

# Analyse réflexive
cortex = TopologyAwareReflexiveCortex(neo4j_connector, metrics_manager)
observations = cortex.analyze_graph_topology()

# Génération d'intentions
intention_generator = TopologyAwareIntentionGenerator(neo4j_connector, metrics_manager)
intentions = intention_generator.generate_intentions(observations)

# Transformation en glyphes potential_action
transformer = TopologyIntentionTransformer(metrics_manager)
potential_actions = transformer.transform_intentions(intentions)

# Exécution des actions
executor = GlyphActionExecutor(neo4j_connector, metrics_manager)
for action in potential_actions:
    result = executor.execute_action(action)
    print(f"Action {action.id}: {result.status} - {result.message}")
```

## Modules principaux

### Décorateurs défensifs

Le module `decorators.py` fournit des décorateurs pour renforcer la robustesse du code :

```python
from decorators import fallback_property, validate_required_properties, timing_and_logging

# Utilisation du décorateur fallback_property
@fallback_property("natural_prompt", fallback_value="Description par défaut")
def process_glyph(glyph_data):
    return f"Traitement du glyphe: {glyph_data['natural_prompt']}"

# Utilisation du décorateur validate_required_properties
@validate_required_properties(["id", "concept_type"])
def validate_glyph(glyph_data):
    return "Glyphe valide"

# Utilisation du décorateur timing_and_logging
@timing_and_logging
def long_operation():
    # Opération longue
    return "Opération terminée"
```

### Schémas Pydantic

Le module `schemas.py` définit des modèles de données validés :

```python
from schemas import GlyphData, PotentialActionGlyph, ConceptType, ActionType

# Création d'un glyphe
glyph = GlyphData(
    id="techglyph_202505140900_1",
    concept_type=ConceptType.TECHNICALCONCEPT,
    tags=["ai", "machine_learning"]
)

# Création d'une action potentielle
from schemas import DetailsStructuredJson, ActionParameters, SourceMetadata

action = PotentialActionGlyph(
    id="sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001",
    action_type=ActionType.ENRICH_HUB_NODE,
    priority=70,
    confidence=0.95,
    details_structured_json=DetailsStructuredJson(
        action_parameters=ActionParameters(
            target_glyph_id="techglyph_202505140900_3"
        )
    ),
    details_text="Enrichir un glyphe hub"
)
```

### Métriques Prometheus

Le module `metrics.py` permet d'instrumenter le code pour le monitoring :

```python
from metrics import MetricsManager, measure_execution_time

# Création d'un gestionnaire de métriques
metrics_manager = MetricsManager(expose_http=True, http_port=8000)

# Enregistrement d'une exécution du pipeline
metrics_manager.record_pipeline_run("success")

# Utilisation du décorateur pour mesurer le temps d'exécution
@measure_execution_time("operation_name", metrics_manager)
def my_function():
    # Code à mesurer
    return "Résultat"
```

### Exécuteur d'actions

Le module `refactored_glyph_action_executor.py` exécute les actions sur le graphe :

```python
from refactored_glyph_action_executor import GlyphActionExecutor
from schemas import PotentialActionGlyph, ActionType, DetailsStructuredJson, ActionParameters

# Création d'un exécuteur d'actions
executor = GlyphActionExecutor(neo4j_connector, metrics_manager)

# Création d'une action
action = PotentialActionGlyph(
    id="sem-potentialaction-TOPOGEN-CONNECT-20250620-001",
    action_type=ActionType.CREATE_RELATIONSHIP,
    priority=80,
    confidence=0.9,
    details_structured_json=DetailsStructuredJson(
        action_parameters=ActionParameters(
            source_glyph_id="techglyph_202505140900_1",
            target_glyph_id="techglyph_202505140900_2",
            relationship_type="SIMILAR_TO"
        )
    ),
    details_text="Créer une relation de similarité"
)

# Exécution de l'action
result = executor.execute_action(action)
print(f"Statut: {result.status}, Message: {result.message}")
```

## Monitoring avec Prometheus

Le pipeline expose des métriques Prometheus sur le port 8000 par défaut. Voici quelques métriques clés :

- `synergesis_pipeline_runs_total` : Nombre total d'exécutions du pipeline
- `synergesis_action_executions_total` : Nombre d'exécutions d'actions par type et statut
- `synergesis_execution_time_seconds` : Temps d'exécution des opérations
- `synergesis_fallback_usage_total` : Utilisation des mécanismes de fallback
- `synergesis_graph_nodes_total` : Nombre de nœuds dans le graphe par type
- `synergesis_graph_relationships_total` : Nombre de relations dans le graphe par type

### Configuration de Prometheus

Exemple de configuration Prometheus :

```yaml
scrape_configs:
  - job_name: 'synergesis_pipeline'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

## Bonnes pratiques

### Gestion des propriétés manquantes

Utilisez systématiquement les décorateurs défensifs pour gérer les propriétés manquantes :

```python
@fallback_property("natural_prompt", fallback_source="metadata.source.target_prompt", fallback_value="Description par défaut")
def process_glyph(glyph_data):
    # Le code peut utiliser glyph_data["natural_prompt"] en toute sécurité
    return glyph_data["natural_prompt"]
```

### Validation des données

Utilisez les schémas Pydantic pour valider les données :

```python
from schemas import GlyphData, ConceptType

# La validation est automatique
try:
    glyph = GlyphData(
        id="techglyph_202505140900_1",
        concept_type=ConceptType.TECHNICALCONCEPT
    )
except ValidationError as e:
    print(f"Données invalides: {e}")
```

### Instrumentation

Instrumentez les fonctions critiques pour le monitoring :

```python
@measure_execution_time("operation_critique", metrics_manager)
def operation_critique():
    # Code critique à monitorer
    return "Résultat"
```

## Dépannage

### Problèmes de connexion à Neo4j

Si vous rencontrez des problèmes de connexion à Neo4j :

1. Vérifiez que Neo4j est en cours d'exécution
2. Vérifiez les variables d'environnement NEO4J_URI, NEO4J_USER et NEO4J_PASSWORD
3. Assurez-vous que le port 7687 est accessible

### Métriques Prometheus non disponibles

Si les métriques Prometheus ne sont pas accessibles :

1. Vérifiez que EXPOSE_METRICS est défini sur true
2. Vérifiez que le port METRICS_PORT est accessible
3. Vérifiez les logs pour d'éventuelles erreurs de démarrage du serveur HTTP

## Contribution

Les contributions sont les bienvenues ! Veuillez suivre ces étapes :

1. Forker le dépôt
2. Créer une branche pour votre fonctionnalité (`git checkout -b feature/ma-fonctionnalite`)
3. Committer vos changements (`git commit -am 'Ajout de ma fonctionnalité'`)
4. Pousser vers la branche (`git push origin feature/ma-fonctionnalite`)
5. Créer une Pull Request

## Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.
