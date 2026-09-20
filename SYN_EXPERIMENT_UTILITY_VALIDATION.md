# SYN-EXPERIMENT-UTILITY — validation intégrée

Date : 12 septembre 2026

## Objet

Cette itération ajoute un filtre d'utilité explicite entre
`SYN-CAUSAL-EXPERIMENT` et `SYN-CAUSAL-PLANNING`.

La sélection purement informationnelle reste disponible, mais une expérience
n'est préparée pour le Planner que si sa valeur informationnelle justifie aussi
son risque, son coût et son irréversibilité selon une configuration de confiance.

## Fonction

Pour chaque intervention enregistrée :

`U(a) = IG(a) - λr·Risk(a) - λc·Cost(a) - λi·Irreversibility(a)`

avec :

- `IG(a)` calculé par SYN-CAUSAL-EXPERIMENT ;
- Risk, Cost et Irreversibility normalisés dans `[0,1]` ;
- valeurs d'impact fournies par configuration de confiance, jamais par le modèle ;
- coefficients et seuils fournis explicitement par `ExperimentUtilityPolicy`.

Des contraintes dures sont appliquées avant le classement par utilité :

- `risk <= maximum_risk`
- `irreversibility <= maximum_irreversibility`
- `information_gain >= minimum_information_gain_bits`
- un profil d'impact manquant rend le candidat inéligible.

Un impact absent n'est donc jamais assimilé à zéro.

## Statuts

- `approved`
- `uninformative`
- `no_safe_candidate`
- `below_minimum_utility`
- `ambiguous_best`

Seul `approved` peut produire un directive causal lorsque le gate est configuré.

## Propriétés vérifiées

1. Une intervention moins informative peut être préférée lorsqu'elle est
   suffisamment plus sûre.
2. Un seuil dur de risque l'emporte sur le gain informationnel.
3. Un profil d'impact manquant bloque le candidat au lieu de lui attribuer coût
   ou risque zéro.
4. Si aucun candidat n'est sûr, aucun directive, mission, plan ou action n'est
   créé.
5. Une expérience gratuite mais non informative n'est pas proposée.
6. Une égalité de gain informationnel peut être départagée par le coût.
7. Une égalité d'utilité totale reste `ambiguous_best` : aucune préférence
   artificielle n'est inventée.
8. Le décision Glyph porte `impact_source = trusted_configuration` et
   `authorization_effect = none`.
9. La provenance complète est conservée :
   `recommendation -> utility decision -> directive -> plan`.
10. AEGIS et SYN-REALITY restent inchangés en aval du filtre.

## Intégration

La stack expose maintenant :

`causal_experiment_utility: ExperimentUtilityGate | None`

La configuration d'utilité exige simultanément :

- des `ExperimentImpactProfile` ;
- une `ExperimentUtilityPolicy` explicite.

Une configuration partielle est refusée au démarrage.

## Validation exécutée

Périmètre ciblé utilité / causal / stack :

`62 passed`

Suite top-level Synergesis complète :

`379 passed, 0 failed`

Aucun TODO/FIXME/NotImplemented/placeholder/dummy exécutable détecté dans les
nouveaux modules ou les fichiers de composition modifiés.

## Frontière scientifique et opérationnelle

Les scores de risque, coût et irréversibilité ne sont pas appris ni estimés par
ce module. Ils sont des paramètres de gouvernance/configuration et leur qualité
conditionne la pertinence du classement.

La décision d'utilité ne constitue toujours pas une autorisation :

`ExperimentUtility != Authority`

Une expérience `approved` doit encore traverser le Planner, la PermissionPolicy,
SYN-AEGIS, l'Executor et SYN-REALITY avant de pouvoir produire une mise à jour
causale.
