# SYN-CAUSAL-CREDIT : attribution conditionnelle et révision ciblée

## Résultat exécuté

64 tests ciblés réussis, dont 24 nouveaux cas. Commande :

```bash
python3 -m pytest -q test_synergesis_causal_credit.py test_synergesis_world_revision.py test_synergesis_prediction.py test_synergesis_prediction_curiosity.py test_synergesis_cognitive_core.py test_synergesis_glyph_protocol.py
```

Le nouveau module est `synergesis_causal_credit.py`. Les tests vérifient son raccordement réel à PredictionEngine et sa coexistence avec WorldModelPredictionBridge. L'installation conserve les sinks existants, notamment celui de World Revision ; les prédictions sans modèle causal enregistré utilisent le provider précédent.

## Mécanisme

Une configuration de confiance définit entre 2 et 64 hypothèses concurrentes, chacune référencée par l'evidence_id d'une croyance présente dans le World Model. Pour chaque intervention autorisée dans ce modèle, elle précise P(effet réussi | hypothèse, intervention). Les priors doivent sommer à un.

Avant l'action, le provider calcule une prédiction de mélange et inscrit dans sa base les croyances, leurs poids, les vraisemblances, l'intervention et l'identifiant de version du modèle. Après le résultat, le sink vérifie :

- les identités et valeurs de la prédiction, de son erreur et du règlement ;
- leurs liens dans le Glyph Graph ;
- un verdict REALITY binaire cohérent et sa présence dans le ledger de prédictions ;
- une observation de l'intervention produite par l'observateur configuré, reliée au même ActionGlyph et utilisée par le verdict ;
- la fraîcheur de la distribution de croyances utilisée avant l'action.

Il applique ensuite Bayes à ces explications concurrentes. Les poids sont conservés en logarithmes pour limiter les problèmes numériques. Le graphe enregistre, pour chaque croyance, son poids précédent, son poids nouveau et `strengthened`, `weakened` ou `unchanged`. Une seule entrée sémantique conserve le vecteur complet de postérieurs pour éviter une mise à jour partielle des candidats. Les faits sources restent inchangés et référencés ; les poids conditionnels sont consultables via `posterior(action_type, strategy_key)` et présents dans les snapshots.

La responsabilité porte l'étiquette `conditional_on_registered_models` uniquement lorsqu'une mise à jour est justifiée. Elle n'est pas présentée comme une causalité démontrée.

## Cas vérifiés

| Situation | Résultat |
|---|---|
| Deux hypothèses avec priors 0,5/0,5 et vraisemblances de succès 0,1/0,9 ; succès vérifié | Postérieurs 0,1/0,9 ; prédiction suivante 0,82 pour la même intervention |
| Deux hypothèses prédisent toutes deux un succès à 0,2 ; échec | `indeterminate`, poids inchangés |
| Intervention suivante avec vraisemblances 0,9/0,1 ; succès | Mise à jour conditionnelle à 0,9/0,1 |
| Trois hypothèses, dont deux observationnellement identiques | Leur rapport reste inchangé ; la troisième peut être distinguée |
| Intervention absente, inconnue ou différente de celle prévue | `intervention_unverified`, aucune révision |
| Observation rattachée à une autre action | Rejet avant révision |
| Aucune hypothèse n'accorde une probabilité positive au résultat | `model_conflict`, aucune attribution forcée |
| Résultat inconnu | `unverified`, aucune révision |
| Rejeu d'un règlement après redémarrage | Pas de deuxième révision |
| Ancien règlement rejoué pendant une nouvelle prédiction | La protection contre plusieurs prédictions simultanées demeure active |
| Identité, probabilité, résultat ou score falsifié | Rejet |
| Croyance absente, probabilités non finies ou hors intervalle | Configuration refusée |
| Stratégie sans modèle causal | Provider et révision empirique précédents conservés |

Un test effectue aussi deux écritures réelles d'un état JSON, puis lit ce fichier indépendamment pour alimenter les observations. C'est un test contrôlé de raccordement, pas une validation expérimentale des vraisemblances ni un banc complet AEGIS/REALITY.

## Raccordement à la stack intégrée

Après construction de la stack et enregistrement des croyances, appeler :

```python
from synergesis_causal_credit import (
    CausalHypothesis, CausalModel, install_causal_credit,
)

# Ces evidence_id doivent déjà exister dans stack.core.memory.
# Les nombres ci-dessous illustrent la configuration ; ils doivent être
# établis pour le système étudié avant toute interprétation causale.
model = CausalModel(
    action_type="diagnostic.run",
    strategy_key="diagnostic-controlled",
    intervention_parameter="intervention",
    observer_id="probe:diagnostic",
    observed_intervention_fact="applied_intervention",
    hypotheses=(
        CausalHypothesis("belief:storage-fault", 0.5,
                         (("baseline", 0.2), ("repair-storage", 0.9))),
        CausalHypothesis("belief:network-fault", 0.5,
                         (("baseline", 0.2), ("repair-storage", 0.1))),
    ),
)
credit = install_causal_credit(engine=stack.prediction, core=stack.core, models=(model,))
```

Cette fonction ne crée aucune permission, aucun exécuteur ni aucune sonde. Le type d'action, son exécuteur, les autorisations AEGIS, les assertions REALITY et la sonde indépendante doivent déjà être configurés. L'observation de la sonde doit réellement contenir l'intervention appliquée. Une étiquette issue de la proposition seule ne suffit pas.

## Frontière scientifique et opérationnelle

Les hypothèses représentent des explications mutuellement exclusives d'un même contexte expérimental. Des fautes coexistantes demandent des hypothèses conjointes explicites. Les interventions, vraisemblances et priors sont fournis par une configuration de confiance ; ce module ne les découvre pas et ne certifie pas leur validité. L'observation d'une intervention ne prouve ni la randomisation ni l'absence de facteurs confondants. Une vraisemblance positive mais erronée peut conduire à un posterior trompeur sans déclencher `model_conflict`.

Ce premier moteur suppose un contexte stable et une vraisemblance conditionnelle applicable aux observations successives. Il n'effectue ni sélection automatique de l'expérience suivante, ni estimation causale non paramétrique, ni traitement automatique de la dérive. Il fonctionne avec un seul écrivain et une prédiction en attente par modèle dans le processus courant. L'historique des faits demeure append-only ; les consommateurs doivent utiliser le dernier posterior via l'API, et non assimiler chaque version à une croyance actuelle distincte.

Le rejeu idempotent concerne le sink : il ne modifie pas la gestion des doubles appels de `PredictionEngine.settle` dans le code préexistant. La mémoire sémantique et le graphe ne disposent pas d'une transaction commune ; après une interruption entre écriture du reçu et de la mémoire, le règlement doit être rejoué pour matérialiser le posterior.

## État des sources disponibles ici

La stack retrouvée porte la version 3 et une date de modification récente, mais les octets matérialisés et une lecture directe de cette version montrent encore `provider=EmpiricalPredictionProvider(...)`, sans WorldModelPredictionBridge. L'AEGIS accessible demeure antérieur à la classe `runtime_attested`, et le module d'audit v2 n'est pas présent dans l'ensemble récupéré. Ces observations ne permettent pas de reproduire ici les 322 tests rapportés dans l'autre environnement.

Aucune stack canonique n'a été remplacée. Le raccordement au vrai PredictionEngine et au cœur audité est testé dans les fixtures ; la validation de toute la stack exige les sources intégrées effectivement synchronisées. Le total 64 ci-dessus est celui du périmètre exécuté, pas celui de l'ensemble Synergesis.
