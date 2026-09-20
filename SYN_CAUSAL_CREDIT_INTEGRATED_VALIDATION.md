# SYN-CAUSAL-CREDIT — intégration complète
Date : 12 septembre 2026

## Résumé

Les trois fichiers produits dans l'autre conversation ont été récupérés et testés contre l'état actuel disponible ici :

- `synergesis_causal_credit.py`
- `test_synergesis_causal_credit.py`
- `SYN_CAUSAL_CREDIT_VALIDATION.md`

Le périmètre ciblé annoncé a été reproduit exactement :

```bash
python -m pytest -q \
  test_synergesis_causal_credit.py \
  test_synergesis_world_revision.py \
  test_synergesis_prediction.py \
  test_synergesis_prediction_curiosity.py \
  test_synergesis_cognitive_core.py \
  test_synergesis_glyph_protocol.py
```

Résultat : **64 passed**.

## Problème de synchronisation découvert

La copie de `synergesis_secure_roam_stack_v2.py` effectivement accessible ici ne contenait pas encore `WorldModelPredictionBridge`, malgré le compte rendu précédent qui indiquait son intégration. Elle construisait encore directement `EmpiricalPredictionProvider` avant le Cognitive Core.

Cette divergence de fichiers explique pourquoi l'autre conversation refusait à juste titre de considérer l'intégration complète comme validée.

## Fusion réalisée

La composition canonique est maintenant :

```text
EmpiricalPredictionProvider
        ↓
WorldModelPredictionBridge
        ↓
CausalCreditBridge (uniquement pour les modèles enregistrés)
        ↓
PredictionEngine
        ↓
AEGIS / Executor
        ↓
SYN-REALITY
        ↓
Prediction settlement
        ├── World Model revision (prédictions empiriques)
        ├── Causal credit (modèles causaux enregistrés)
        └── Prediction curiosity / ROAM (si configuré)
```

`CausalCreditBridge` conserve `WorldModelPredictionBridge` comme fallback. Les couples action/stratégie sans modèle causal continuent donc d'utiliser la révision empirique du World Model.

La stack expose maintenant :

- `world_revision: WorldModelPredictionBridge | None`
- `causal_credit: CausalCreditBridge | None`

Le builder accepte :

- `causal_models: Sequence[CausalModel] = ()`

Les croyances référencées par ces modèles doivent déjà être présentes dans la mémoire sémantique persistante.

Un doublon de construction du `GlyphAuditGraph` a également été supprimé dans cette copie de stack.

## Validation bout-en-bout ajoutée

Nouveau test : `test_synergesis_causal_credit_stack.py`.

Il traverse réellement :

```text
Agent Loop v5
→ AEGIS
→ Executor
→ SYN-REALITY
→ PredictionEngine
→ CausalCreditBridge
→ World Model
```

Scénario :

1. Deux hypothèses concurrentes commencent à `0.5 / 0.5`.
2. Intervention `check` : les deux hypothèses prédisent la même probabilité (`0.2`) et l'effet vérifié est absent.
3. Résultat : `indeterminate`, responsabilité `not_identified`, poids inchangés `0.5 / 0.5`.
4. Intervention vérifiée `repair` : vraisemblances `0.9 / 0.1`, effet vérifié présent.
5. Résultat : `conditional_update`, postérieurs `0.9 / 0.1`.
6. La prédiction suivante sur `repair` utilise réellement ces poids :

```text
0.9 × 0.9 + 0.1 × 0.1 = 0.82
```

Les confidences des faits sources restent inchangées ; le moteur ajoute un posterior conditionnel append-only.

## Validation finale

Tests ciblés fusionnés : **72 passed** avant le test bout-en-bout additionnel.

Test stack causal bout-en-bout : **3 passed**.

Suite Synergesis complète exécutée ici :

```text
350 passed, 0 failed
0 failed
```

## Frontière scientifique conservée

Le système distingue explicitement :

- `not_identified` / `indeterminate` quand les observations ne départagent pas les candidats ;
- `conditional_on_registered_models` lorsqu'une intervention vérifiée justifie une mise à jour bayésienne conditionnelle au modèle fourni.

Cela ne constitue toujours pas une preuve de causalité réelle des hypothèses. Les priors, interventions et vraisemblances sont une configuration de confiance. Une famille de modèles erronée peut produire un posterior trompeur sans être automatiquement détectée.


## Renforcement de la vérification indépendante de l’intervention

Le test bout-en-bout ne reprend plus le nom de l’intervention directement depuis les paramètres demandés. L’exécuteur matérialise séparément un reçu runtime contenant l’intervention effectivement appliquée ; le probe indépendant lit ce reçu et l’injecte dans `runtime_reality_observation`.

Un cas négatif supplémentaire demande `repair` alors que le runtime applique réellement `check`. Le résultat attendu et vérifié est :

- `status = intervention_unverified` ;
- `causal_responsibility = not_identified` ;
- posterior inchangé à 50/50.

Après ce renforcement, la suite complète donne **350 passed, 0 failed**.
