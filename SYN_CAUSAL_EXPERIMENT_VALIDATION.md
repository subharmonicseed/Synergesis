# SYN-CAUSAL-EXPERIMENT — validation intégrée

Date : 12 septembre 2026

## Objet

`synergesis_causal_experiment.py` ajoute une sélection d'intervention fondée sur le gain d'information attendu, au-dessus de `SYN-CAUSAL-CREDIT`.

Pour une distribution courante d'hypothèses H et un résultat binaire Y :

`IG(a) = H(H) - E[H(H | Y, a)]`

L'entropie est mesurée en bits.

Le module ne crée aucune permission, capability, sonde ou exécuteur. Il recommande uniquement une intervention déjà déclarée dans un `CausalModel` de confiance et inscrit cette recommandation dans le Glyph Graph avec `authorization_effect = none`.

## Comportement vérifié

Dans le modèle d'intégration :

- priors : stockage 0,5 / réseau 0,5 ;
- `check` : P(succès)=0,2 sous les deux hypothèses ;
- `repair` : P(succès)=0,9 si stockage, 0,1 si réseau.

Résultats :

- `IG(check) = 0 bit` ;
- `IG(repair) = 0,5310044064 bit` ;
- le sélecteur recommande `repair` ;
- après posterior 0,9 / 0,1, `IG(repair)` descend à `0,2110814521 bit`, ce qui reflète la réduction d'incertitude déjà obtenue.

Le module sait également retourner :

- `uninformative` si aucune intervention ne dépasse le seuil minimal ;
- `ambiguous_best` si plusieurs interventions informatives sont ex aequo ;
- aucune intervention sélectionnée dans ces deux cas.

Il refuse de recommander une nouvelle expérience tant qu'une prédiction causale du même modèle est encore en attente de règlement.

## Intégration stack

`SynSecureRoamRealityStack` expose désormais :

- `causal_credit`
- `causal_experiment`

La chaîne canonique devient :

`EmpiricalEstimator -> WorldModelPredictionBridge -> CausalCreditBridge -> CausalExperimentSelector`

pour la connaissance, puis :

`PredictionEngine -> AEGIS -> Executor -> SYN-REALITY -> settlement -> causal update`

La recommandation d'expérience ne modifie pas la proposition du reasoner et ne déclenche pas automatiquement une action.

## Vérification

Suite complète Synergesis après intégration :

`361 passed, 0 failed`

Les nouveaux tests couvrent notamment :

- sélection de l'intervention qui sépare les hypothèses ;
- refus d'un choix arbitraire lorsque l'information attendue est nulle ;
- ambiguïté explicite en cas d'ex aequo informatif ;
- baisse du gain d'information après concentration du posterior ;
- audit Glyph sans effet d'autorisation ;
- refus si aucun modèle causal n'est enregistré ;
- refus pendant une prédiction causale en attente ;
- seuil minimal de gain d'information ;
- raccordement réel à la stack complète ;
- absence d'auto-exécution de la recommandation.

## Frontière scientifique

Le gain d'information est calculé **conditionnellement aux hypothèses et vraisemblances enregistrées**. Une intervention très informative sous un modèle faux reste une mauvaise expérience. Ce module optimise la discrimination à l'intérieur du modèle déclaré ; il ne prouve ni la validité causale des hypothèses, ni la randomisation, ni l'absence de facteurs confondants.
