# Conception du GLYPH_PROMPT Technique et Structure GlyphData Associée (Révisé V1.2)

## 1. Objectif

Ce document détaille la proposition pour un `GLYPH_PROMPT` spécialisé destiné à un Grand Modèle de Langage (LLM) et la structure `GlyphData` correspondante. L'objectif est d'extraire des concepts techniques, des problèmes, des solutions, et leurs relations sémantiques à partir de textes scientifiques (principalement des abstracts et introductions/conclusions d'articles de recherche en IA), afin d'alimenter un graphe de connaissances pour l'auto-amélioration du système Synergesis.

## 2. `GLYPH_PROMPT` Technique (Proposition V1.2)

Le prompt sera structuré pour guider le LLM à travers plusieurs étapes d'analyse et de génération. Il sera crucial de lui demander de retourner une liste JSON valide d'objets `GlyphData`.

```text
Vous êtes un expert en analyse de documents scientifiques et techniques dans le domaine de l'Intelligence Artificielle. Votre tâche est de lire attentivement le texte fourni (provenant du document avec l'ID `{source_doc_id_param}` et du segment `{source_chunk_idx_param}`) et de le décomposer en une série de "glyphes techniques" interconnectés. Chaque glyphe représente un concept, un problème, une solution/mécanisme, ou une contribution clé.

Pour chaque texte source, vous devez générer une liste JSON d'objets "GlyphData". Chaque objet GlyphData doit suivre la structure spécifiée ci-dessous.

**Instructions Générales pour la Génération des Glyphes Techniques:**

1.  **Identification des Éléments Clés** : Pour chaque texte, identifiez :
    *   **Problèmes Principaux (Problem)** : Les défis, limitations ou questions de recherche que le texte aborde.
    *   **Concepts Techniques Clés (TechnicalConcept)** : Les algorithmes, architectures, modèles, principes théoriques, ou méthodologies fondamentales discutés ou introduits.
    *   **Solutions/Mécanismes Proposés (ProposedSolution)** : Les nouvelles approches, techniques, systèmes, ou améliorations spécifiques que le texte propose pour adresser les problèmes identifiés.
    *   **Contributions/Résultats Majeurs (KeyContribution)** : Les découvertes, résultats d'évaluation, ou avancées significatives présentées.

2.  **Granularité des Glyphes** : Créez un glyphe distinct uniquement pour les éléments majeurs du texte. Pour les éléments secondaires comme les méthodologies d'évaluation, intégrez-les dans les glyphes de contribution clé correspondants, sauf si ces méthodologies constituent une innovation majeure en elles-mêmes. Visez généralement 4-6 glyphes pour un abstract typique.

3.  **Assignation du `concept_type`** : Pour chaque glyphe, assignez un `concept_type` parmi la liste suivante : `Problem`, `TechnicalConcept`, `ProposedSolution`, `KeyContribution`, `Methodology`, `Dataset`, `Metric`, `ToolFramework`, `TheoreticalPrinciple`, `ArchitecturalPattern`. Ce `concept_type` doit être inclus dans la liste des `tags`.

4.  **Extraction des Détails Spécifiques** : 
    *   Remplissez le champ `details_json` avec des informations structurées pertinentes pour le `concept_type` (voir section 3.2).
    *   Pour chaque type de glyphe, respectez strictement les champs spécifiés. Par exemple, pour les glyphes de type `Problem`, incluez uniquement les champs `problem_statement` et `affected_components` sauf si le contexte ou les conséquences sont explicitement mentionnés dans le texte.
    *   Maintenez une cohérence dans la longueur des descriptions. Pour les champs comme `problem_statement`, `definition`, ou `summary`, visez 1-2 phrases concises (environ 30-50 mots).

5.  **Identification des Relations Sémantiques** : 
    *   Identifiez et décrivez les relations entre les glyphes que vous générez à partir du MÊME texte source. Utilisez les types de relations suivants : `ADDRESSES_PROBLEM`, `PROPOSES_SOLUTION_FOR`, `USES_TECHNIQUE`, `IMPLEMENTS_CONCEPT`, `EVALUATED_ON_DATASET`, `MEASURED_BY_METRIC`, `RELATED_TO_CONCEPT`, `IMPROVES_ON`, `BUILDS_UPON`, `PART_OF_ARCHITECTURE`.
    *   Lorsque vous créez une relation, le `target_glyph_id` doit correspondre à l' `id` d'un autre glyphe généré à partir du même texte source lors de CET APPEL.
    *   Privilégiez les relations directes entre problèmes et solutions (`ADDRESSES_PROBLEM`), ou entre concepts et implémentations (`IMPLEMENTS_CONCEPT`). N'établissez des relations entre concepts techniques et problèmes (`ADDRESSES_PROBLEM`) que si le texte indique explicitement que le concept vise à résoudre le problème.

6.  **Génération des `domain_tags`** : 
    *   Pour chaque glyphe, générez une liste de 3-5 `domain_tags` pertinents et spécifiques.
    *   Les `domain_tags` doivent être suffisamment spécifiques pour être utiles à la recherche, mais pas trop techniques. Visez un niveau intermédiaire de spécificité (ex: préférez `reinforcement_learning` à `machine_learning` ou à `proximal_policy_optimization`).
    *   Utilisez des tags cohérents entre les glyphes liés (ex: si un problème est tagué `natural_language_processing`, une solution qui l'adresse devrait probablement aussi avoir ce tag).

7.  **Assignation des Propriétés Symboliques** : Inférer les propriétés `polarité`, `alignement`, `fréquence`, `poids`, `entropy_score` (voir section 3.3 pour des heuristiques et lignes directrices).
    *   `fréquence`: (60-120) Estimez la récurrence ou la nouveauté du concept. Un concept très nouveau/spécifique aura une fréquence plus élevée, un concept bien établi une fréquence plus basse.
    *   `poids`: (1-9) Estimez l'importance ou l'impact du glyphe dans le contexte du document. Un problème majeur ou une solution clé aura un poids élevé.
    *   `entropy_score`: (0.0-1.0) Estimez l'incertitude, la complexité ou le potentiel d'exploration du glyphe. Un concept bien défini et simple aura une entropie basse, un concept émergent ou complexe une entropie élevée.

8.  **Format de Sortie Strict** : La sortie DOIT être une liste JSON valide d'objets `GlyphData`. Assurez-vous que tous les guillemets sont correctement échappés dans les chaînes de caractères JSON.

**Texte Source à Analyser:**

```
{text_input}
```

**Structure `GlyphData` Attendue (Rappel):**

Chaque objet dans la liste JSON doit avoir les champs suivants :
`id`: (string, unique pour cet appel, généré par vous, format: `techglyph_{approx_timestamp_param}_{compteur_interne}` où `{approx_timestamp_param}` est un placeholder pour un timestamp simplifié fourni et `compteur_interne` est un compteur que vous gérez pour cet appel)
`timestamp`: (float, timestamp Unix UTC actuel, vous le générerez)
`source_document_id`: (string, utilisez la valeur de `{source_doc_id_param}` fournie)
`source_chunk_index`: (integer, utilisez la valeur de `{source_chunk_idx_param}` fournie)
`natural_prompt`: (string, une description concise en langage naturel du glyphe, ex: "Concept: Architecture d'agent BDI pour la planification adaptative")
`polarité`: (string, "+", "-", "0", "±")
`alignement`: (string, ex: "Void", "Elemental", "Chthonic", "Celestial", "Harmonic", "Expansion")
`fréquence`: (integer, 60-120)
`poids`: (integer, 1-9)
`tags`: (list of strings, incluant le `concept_type` assigné et les `domain_tags` générés)
`entropy_score`: (float, 0.0-1.0)
`status`: (string, initialement "generated_from_llm")
`details_json`: (string, un objet JSON sérialisé contenant les détails spécifiques au `concept_type`)
`llm_prompt_version`: (string, version actuelle du prompt, ex: "tech_v1.2")
`relationships`: (list of objects, chaque objet: `{"type": "RELATION_TYPE", "target_glyph_id": "id_autre_glyphe"}`)

(Note: Le champ `semantic_hash` sera calculé en post-traitement par le système appelant.)
(Note: Le champ `details_type` est omis car le `concept_type` est déjà inclus dans les `tags`.)

**Exemples de `details_json` par type de glyphe:**

**Pour `tags` contenant `Problem`:**
`details_json`: `"{\"problem_statement\": \"Description concise du problème en 30-50 mots.\", \"affected_components\": [\"composant1\", \"composant2\"]}"`

**Pour `tags` contenant `TechnicalConcept`:**
`details_json`: `"{\"concept_name\": \"Nom du concept\", \"definition\": \"Définition concise en 30-50 mots.\", \"key_properties\": [\"propriété1\", \"propriété2\"]}"`

**Pour `tags` contenant `ProposedSolution`:**
`details_json`: `"{\"solution_name\": \"Nom de la solution\", \"summary\": \"Résumé concis en 30-50 mots.\", \"key_mechanisms_or_components\": [\"mécanisme1\", \"mécanisme2\"], \"addresses_problem_ids\": [\"techglyph_{approx_timestamp_param}_1\"], \"novelty_or_improvement\": \"Description concise de la nouveauté.\"}"`

**Pour `tags` contenant `KeyContribution`:**
`details_json`: `"{\"contribution_summary\": \"Résumé concis en 30-50 mots.\", \"contribution_type\": \"empirical_result\", \"evidence_or_metric\": \"Description des preuves ou métriques.\", \"implications\": \"Implications de cette contribution.\"}"`

Commencez l'analyse du texte fourni et générez la liste JSON des objets `GlyphData`.
```

## 3. Structure `GlyphData` pour les Glyphes Techniques (Révisé V1.2)

### 3.1 Champs de Base (Ajustements)

*   `id`: Généré par le LLM avec un `compteur_interne` pour l'unicité au sein de l'appel. Un `approx_timestamp_param` (ex: YYYYMMDDHHMM) sera fourni au LLM pour l'aider à construire l'ID. L'unicité globale sera assurée en post-traitement par Synergesis en préfixant avec `source_document_id`.
*   `tags`: Doit inclure le `concept_type` assigné (ex: `Problem`) ainsi que les `domain_tags` (ex: `llm_reasoning`).
*   `details_type`: Ce champ est **supprimé** de la structure demandée au LLM, car le `concept_type` est déjà présent dans la liste des `tags`, ce qui est plus flexible pour les requêtes.
*   `semantic_hash`: Ce champ est **supprimé** de la structure demandée au LLM. Il sera calculé en post-traitement par Synergesis (Python) basé sur les champs sémantiques remplis par le LLM.
*   `source_document_id` et `source_chunk_index`: Le LLM sera instruit d'utiliser les valeurs `{source_doc_id_param}` et `{source_chunk_idx_param}` qui seront injectées dans le prompt.

### 3.2 Champs `details_json` par `concept_type` (Exemples)

*   **Pour `tags` contenant `Problem`**
    *   `problem_statement`: (string, 30-50 mots)
    *   `affected_components`: (list of strings)
    *   `context`: (string, optionnel, seulement si explicitement mentionné)
    *   `consequences`: (string, optionnel, seulement si explicitement mentionné)

*   **Pour `tags` contenant `TechnicalConcept`**
    *   `concept_name`: (string)
    *   `definition`: (string, 30-50 mots)
    *   `key_properties`: (list of strings)
    *   `category`: (string, optionnel)

*   **Pour `tags` contenant `ProposedSolution`**
    *   `solution_name`: (string)
    *   `summary`: (string, 30-50 mots)
    *   `key_mechanisms_or_components`: (list of strings)
    *   `addresses_problem_ids`: (list of strings) Liste des `id` des glyphes (tag `Problem`) que cette solution vise à résoudre.
    *   `novelty_or_improvement`: (string, optionnel)

*   **Pour `tags` contenant `KeyContribution`**
    *   `contribution_summary`: (string, 30-50 mots)
    *   `contribution_type`: (string, ex: "empirical_result", "methodology", "theoretical_advancement")
    *   `evidence_or_metric`: (string, optionnel)
    *   `implications`: (string, optionnel)

*   **Pour `tags` contenant `Methodology`**
    *   `methodology_name`: (string)
    *   `description`: (string, 30-50 mots)
    *   `key_steps`: (list of strings)
    *   `metrics_or_criteria`: (list of strings, optionnel)

*   **Pour `tags` contenant `Dataset`**
    *   `dataset_name`: (string)
    *   `description`: (string, 30-50 mots)
    *   `key_characteristics`: (list of strings)
    *   `size_or_scale`: (string, optionnel)

*   **Pour `tags` contenant `Metric`**
    *   `metric_name`: (string)
    *   `description`: (string, 30-50 mots)
    *   `formula_or_calculation`: (string, optionnel)
    *   `interpretation`: (string, optionnel)

*   **Pour `tags` contenant `ToolFramework`**
    *   `tool_name`: (string)
    *   `purpose`: (string, 30-50 mots)
    *   `key_features`: (list of strings)
    *   `version_info`: (string, optionnel)

*   **Pour `tags` contenant `TheoreticalPrinciple`**
    *   `principle_name`: (string)
    *   `description`: (string, 30-50 mots)
    *   `key_implications`: (list of strings)
    *   `related_theories`: (list of strings, optionnel)

*   **Pour `tags` contenant `ArchitecturalPattern`**
    *   `pattern_name`: (string)
    *   `description`: (string, 30-50 mots)
    *   `key_components`: (list of strings)
    *   `advantages`: (list of strings, optionnel)
    *   `limitations`: (list of strings, optionnel)

### 3.3 Relations Sémantiques (`relationships`)

La structure reste `{"type": "RELATION_TYPE", "target_glyph_id": "id_autre_glyphe"}`.
Le LLM doit s'assurer que `target_glyph_id` correspond à un `id` généré dans le même appel.

**Hiérarchie des Relations** : Le prompt V1.2 précise maintenant de privilégier les relations directes entre problèmes et solutions (`ADDRESSES_PROBLEM`), ou entre concepts et implémentations (`IMPLEMENTS_CONCEPT`). Les relations entre concepts techniques et problèmes (`ADDRESSES_PROBLEM`) ne doivent être établies que si le texte indique explicitement que le concept vise à résoudre le problème.

### 3.4 Inférence des Propriétés Symboliques de Base (Lignes Directrices Précisées)

*   **`polarité`** :
    *   Tag `Problem`: "-"
    *   Tag `ProposedSolution`, `KeyContribution` (positive) : "+"
    *   Autres tags (`TechnicalConcept`, `Methodology`, etc.): "0" (neutre) ou "±" si le concept a des aspects doubles ou est débattu.
*   **`alignement`** :
    *   Tag `Problem`, contraintes : "Chthonic"
    *   Tag `TechnicalConcept` (théorique), `TheoreticalPrinciple`: "Void"
    *   Tag `ProposedSolution`, `Methodology`, `ToolFramework` (mécanismes d'action) : "Elemental"
    *   Tag `KeyContribution` (nouvelle découverte, avancée) : "Expansion"
    *   Tag `ArchitecturalPattern`, nouvelles visions : "Celestial"
    *   Concepts équilibrés, `Dataset` : "Harmonic"
*   **`fréquence`** (60-120) : 
    *   Très nouveau/spécifique/rare : 100-120
    *   Modérément commun/spécialisé : 80-100
    *   Bien établi/général : 60-80
*   **`poids`** (1-9) :
    *   Impact majeur/central dans le document : 7-9
    *   Importance modérée : 4-6
    *   Détail/concept secondaire : 1-3
*   **`entropy_score`** (0.0-1.0) :
    *   Concept très nouveau, complexe, ouvrant de nombreuses questions : 0.7-1.0
    *   Concept avec une certaine complexité ou nouveauté : 0.4-0.7
    *   Concept bien défini, simple, bien compris : 0.0-0.4

## 4. Validation de la Sortie JSON

Le prompt insiste fortement sur la nécessité de produire une liste JSON valide. Des post-traitements côté client (Synergesis) valideront la structure et pourront effectuer des corrections mineures.

## 5. Justification des Modifications V1.1 → V1.2

### 5.1 Clarification sur la Granularité des Glyphes

**Modification** : Ajout de la section 2 "Granularité des Glyphes" avec des instructions précises sur quand créer des glyphes distincts et quand intégrer des éléments secondaires dans des glyphes existants.

**Justification** : L'analyse comparative a révélé des variations dans la granularité des glyphes générés, notamment pour les méthodologies d'évaluation. Cette clarification vise à standardiser l'approche et à éviter une fragmentation excessive des concepts.

**Impact attendu** : Une cohérence accrue dans le nombre et la nature des glyphes générés, facilitant la comparaison et l'intégration dans le graphe de connaissances.

### 5.2 Précision sur les Champs de Details_json

**Modification** : Restructuration de la section 4 "Extraction des Détails Spécifiques" avec des sous-points sur les champs obligatoires et la longueur des descriptions.

**Justification** : L'analyse a montré des variations dans les champs inclus et la verbosité des descriptions. Cette précision vise à standardiser la structure et la concision des informations extraites.

**Impact attendu** : Des descriptions plus uniformes et des structures de données plus cohérentes, facilitant le traitement automatisé et la comparaison des glyphes.

### 5.3 Guidance sur la Hiérarchie des Relations

**Modification** : Ajout de directives spécifiques dans la section 5 sur les types de relations à privilégier et les conditions pour établir certaines relations.

**Justification** : L'analyse a révélé des variations dans l'établissement des relations, notamment entre concepts techniques et problèmes. Cette guidance vise à clarifier la sémantique des relations et à éviter les connexions non justifiées.

**Impact attendu** : Un graphe de relations plus précis et sémantiquement cohérent, reflétant mieux les liens explicites mentionnés dans le texte source.

### 5.4 Standardisation des Tags

**Modification** : Restructuration de la section 6 avec des directives sur le niveau de spécificité des tags et la cohérence entre glyphes liés.

**Justification** : L'analyse a montré des variations dans la spécificité et la cohérence des tags. Cette standardisation vise à faciliter la recherche et le clustering des glyphes.

**Impact attendu** : Des tags plus cohérents et utiles pour la navigation dans le graphe de connaissances, avec un équilibre entre spécificité et généralité.

### 5.5 Exemples de Details_json

**Modification** : Ajout d'exemples concrets de `details_json` pour chaque type de glyphe, avec des indications sur la longueur attendue des descriptions.

**Justification** : L'analyse a révélé des variations dans la structure et le contenu des `details_json`. Ces exemples visent à clarifier les attentes et à standardiser les sorties.

**Impact attendu** : Des structures de `details_json` plus cohérentes et conformes aux attentes, facilitant le traitement automatisé et l'intégration dans le graphe.

## 6. Impact Global Attendu

La version V1.2 du GLYPH_PROMPT devrait produire des sorties :
- Plus cohérentes en termes de granularité (nombre de glyphes par abstract)
- Plus standardisées en termes de structure de données
- Plus précises en termes de relations sémantiques
- Plus uniformes en termes de tags et de descriptions

Ces améliorations devraient réduire la charge sur les modules de post-traitement (glyph_fixer.py, glyph_lint.py) et faciliter l'enrichissement sémantique ultérieur (glyph_enricher.py).

## 7. Prochaines Étapes

1.  Valider cette proposition révisée (V1.2) avec l'utilisateur.
2.  Tester le prompt V1.2 sur le golden set pour évaluer les améliorations.
3.  Développer les modules de post-traitement (glyph_fixer.py, glyph_lint.py, glyph_enricher.py).
4.  Intégrer ce prompt dans le pipeline de glyphisation complet.
