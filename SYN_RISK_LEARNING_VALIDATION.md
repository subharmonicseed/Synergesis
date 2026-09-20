# SYN-RISK-LEARNING — validation intégrée

Date : 12 septembre 2026

## Objet

Cette itération ajoute un modèle empirique de risque fondé sur des conséquences
réellement observées par SYN-REALITY.

La réussite d'une action et son caractère adverse sont volontairement séparés.

Une action peut donc être :

- techniquement réussie et adverse ;
- techniquement réussie et non adverse ;
- techniquement échouée et non adverse ;
- techniquement échouée et adverse.

Le moteur n'infère jamais automatiquement `adverse_event` depuis le champ
`success`.

## Observation

Chaque couple action/stratégie peut recevoir un `RiskObservationContract`
configuré hors du modèle :

- `observer_id`
- `adverse_event_fact`

Le settlement PREDICT doit être scoré et le fait adverse doit provenir d'une
`runtime_reality_observation` reliée au même ActionGlyph et au verdict
SYN-REALITY.

Une observation absente, non booléenne ou conflictuelle n'entraîne aucun
apprentissage de risque.

## Estimation

Les événements adverses vérifiés sont stockés dans un `RiskLedger` append-only
et hash-chainé.

Le moteur calcule une estimation Beta-Bernoulli pondérée par récence :

- `posterior_mean`
- `conservative_risk`

Le terme conservateur ajoute une marge explicite qui n'est pas présentée comme
un intervalle statistique formel.

## Invariant de sécurité

Le risque appris ne peut jamais abaisser le plancher de gouvernance :

`effective_risk = max(configured_risk_floor, learned_conservative_risk)`

Conséquences :

- une observation adverse peut rendre une intervention plus restrictive ;
- des observations sûres peuvent améliorer la calibration affichée ;
- elles ne peuvent jamais rendre le gate moins restrictif que la configuration
  de confiance.

Les seuils `maximum_risk`, les poids de politique, les capabilities et AEGIS
restent externes à l'apprentissage.

## Intégration avec SYN-EXPERIMENT-UTILITY

`ExperimentUtilityCandidate` expose maintenant :

- `configured_risk_floor`
- `learned_conservative_risk`
- `risk` = risque effectif réellement utilisé pour la décision.

Le risque effectif est utilisé dans :

`U(a) = IG(a) - λr·Risk_effective(a) - λc·Cost(a) - λi·Irreversibility(a)`

Un risque appris supérieur au plafond peut produire `no_safe_candidate`, ce qui
empêche la création d'un nouveau directive, plan ou action.

## Cas vérifiés

1. Un échec d'action sans dommage donne `adverse_event=False`.
2. Une action réussie accompagnée d'un dommage réel donne
   `adverse_event=True`.
3. Après un événement adverse vérifié, le risque appris peut dépasser le seuil
   de sécurité et bloquer l'expérience suivante.
4. Après plusieurs observations sûres, l'estimation apprise peut descendre sous
   le risque configuré, mais le risque utilisé par le gate reste exactement au
   plancher configuré.
5. Une observation adverse manquante n'entraîne aucun record.
6. Deux observations de risque contradictoires n'entraînent aucun record.
7. Un settlement non scoré n'entraîne aucun apprentissage de risque.
8. Le rejeu d'un settlement est idempotent.
9. Le ledger détecte une altération de son historique.
10. Une observation reliée à une autre action est rejetée.
11. Une configuration partielle du risk learning est refusée au démarrage.
12. Aucun événement de risk learning ne porte d'effet d'autorisation.

## Validation

Tests ciblés risk / causal / utility :

`38 passed`

Suite top-level Synergesis complète :

`393 passed, 0 failed`

Aucun TODO/FIXME/NotImplemented/placeholder/dummy exécutable détecté dans les
nouveaux modules ou les fichiers de composition modifiés.

## Frontière

`SYN-RISK-LEARNING` apprend une fréquence empirique d'événements adverses
observés sous une intervention donnée. Cela ne transforme pas cette fréquence en
preuve causale du dommage, ni en certification de sécurité.

Le moteur ne peut pas :

- modifier `maximum_risk` ;
- modifier le risque configuré ;
- créer une permission ;
- créer une capability ;
- contourner AEGIS ;
- déclarer lui-même qu'une conséquence est adverse.

Le sens du fait `adverse_event` et le choix de l'observateur restent des éléments
de confiance fournis par la configuration.
