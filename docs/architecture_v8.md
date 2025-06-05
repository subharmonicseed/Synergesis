# Architecture de Base Synergesis V8

Cette spécification résume la structure modulaire proposée pour le projet **Synergesis** telle que définie durant la Vague VIII. Elle sert de référence pour initier le squelette de code et guider l'organisation des modules.

## 1. Structure des dossiers

```
synergesis/
├── synergesis/
│   ├── __init__.py
│   ├── glyph_core.py
│   ├── utils/
│   │   └── __init__.py
│   │   └── common_helpers.py
│   ├── llm_interface/
│   │   └── __init__.py
│   │   └── backends.py
│   │   └── prompts.py
│   ├── ingestion/
│   │   └── __init__.py
│   │   └── glyphifier.py
│   │   └── text_to_glyph.py
│   │   └── ai_to_glyph.py
│   ├── processing/
│   │   └── __init__.py
│   │   └── delta_translate.py
│   │   └── glyph_fixer.py
│   │   └── glyph_lint.py
│   │   └── glyph_enricher.py
│   ├── storage/
│   │   └── __init__.py
│   │   └── neo4j_interface.py
│   │   └── neo4j_schema.py
│   ├── analysis/
│   │   └── __init__.py
│   │   └── topology_engine.py
│   │   └── fusion_engine.py
│   ├── cognitive_core/
│   │   └── __init__.py
│   │   └── reflexive_cortex.py
│   │   └── simulation_engine.py
│   │   └── intention_generator.py
│   │   └── memory_system.py
│   ├── protocols/
│   │   └── __init__.py
│   │   └── metabolic_protocol.py
│   │   └── prospective_protocol.py
│   │   └── contextual_thresholds.py
│   │   └── conflict_monitor.py
│   │   └── system_goals.py
│   └── agent_loop.py
├── scripts/
│   └── migrate_to_neo4j.py
│   └── run_pipeline_test.py
│   └── run_agent_loop.py
├── tests/
├── data/
├── docs/
│   └── architecture.md
│   └── glyph_schema.md
├── .github/
│   └── workflows/
│       └── main_ci.yml
├── README.md
├── requirements.txt
└── .gitignore
```

## 2. Contenu des modules clés

- **`glyph_core.py`** : définitions des types `GlyphData`, `CompositePolarity`, `CompositeAlignment`, `GlyphRelationship`. Contient les constantes (`SIMPLE_POLARITIES`, `STATUS_VALUES`, etc.) et des helpers (`is_composite_polarity`, `is_composite_alignment`).
- **`utils/common_helpers.py`** : fonctions `_normalize` et `_get_map_value`.
- **`llm_interface/backends.py`** : classes `BaseLLM`, `StubLLM`, `HFLocalLLM` et factory `get_llm`.
- **`llm_interface/prompts.py`** : stockage du `GLYPH_PROMPT_TECH_V1_1`.
- **`ingestion/glyphifier.py`** : fonction `glyphify_sleep_phase` qui appelle un backend LLM, parse la réponse et valide chaque glyphe.
- **`processing/`** : modules pour `glyph_fixer`, `glyph_lint`, `glyph_enricher`, etc.
- **`storage/neo4j_interface.py`** : interface avec Neo4j et fonction `bulk_upsert_glyphs`.
- **`analysis/topology_engine.py`** : logique d'analyse du graphe.
- **`cognitive_core/`** : `ReflexiveCortex`, `SimulationEngine`, `IntentionGenerator`, `MemorySystem`.
- **`protocols/`** : définitions de protocoles (metabolic, prospective, etc.).
- **`agent_loop.py`** : boucle d'orchestration principale.

## 3. Autres fichiers

- **`scripts/`** : scripts exécutables (migration, tests, lancement de la boucle).
- **`tests/`** : contiendra les tests unitaires.
- **`requirements.txt`** : dépendances principales (neo4j, pydantic, transformers, etc.).
- **`README.md`** : présentation rapide et instructions d'installation.

Cette architecture sert de point de départ pour implémenter progressivement les différentes composantes de Synergesis. Les fonctions internes peuvent dans un premier temps contenir des `pass` ou des logiques minimales, l'objectif étant de bâtir un socle modulaire prêt à être étendu.
