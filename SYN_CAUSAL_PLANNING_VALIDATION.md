# SYN-CAUSAL-PLANNING — validation intégrée

Date : 12 septembre 2026

## Objet

Cette itération raccorde la recommandation d'expérience de
`SYN-CAUSAL-EXPERIMENT` au Planner existant sans convertir la valeur
informationnelle d'une expérience en permission d'exécution.

Chaîne :

`Ambiguity -> ExperimentRecommendation -> PreparedDirective -> Planner -> Agent Loop -> AEGIS -> Executor -> SYN-REALITY -> SYN-CAUSAL-CREDIT`

## Invariants

- Une recommandation ne crée aucune permission ni capability.
- La préparation d'une expérience ne déclenche aucune action.
- Le directive est single-use et auditable.
- Le reasoner doit proposer exactement le type d'action, la stratégie et la
  valeur d'intervention enregistrés dans le directive.
- Une proposition différente est supprimée avant AEGIS.
- Une proposition correcte passe encore par PermissionPolicy et SYN-AEGIS.
- Le Planner ne considère l'expérience terminée qu'après un settlement
  SYN-REALITY et un reçu SYN-CAUSAL-CREDIT vérifié.
- `intervention_unverified` et `unverified` bloquent la mission.
- Un effet négatif peut être une expérience valide : `indeterminate`,
  `conditional_update` et `model_conflict` sont des résultats scientifiques
  recevables lorsque l'intervention elle-même est vérifiée.
- Un directive consommé ne peut pas être rejoué.

## Tests ajoutés

Le test de stack vérifie notamment :

1. préparer l'expérience ne crée aucun ActionGlyph ;
2. l'exécution explicite du directive recommandé traverse Planner -> AEGIS ->
   REALITY -> Causal Credit et produit le posterior attendu 90/10 ;
3. une tentative du reasoner de remplacer `repair` par `check` est bloquée avant
   AEGIS et ne modifie pas le posterior ;
4. AEGIS peut refuser une proposition parfaitement conforme au directive si la
   capability requise manque ;
5. le directive est durablement relié au plan par une relation Glyph canonique
   `derived_from` et porte `authorization_effect = none`.

## Validation

Tests ciblés causal / stack :

`52 passed`

Suite top-level Synergesis complète :

`366 passed, 0 failed`

Le faux total temporaire `372` provenait d'une copie de travail du fichier de
tests présente dans `/mnt/data`. Cette copie a été supprimée avant la validation
canonique.

## Frontière

Ce module prépare et orchestre une expérience explicitement demandée par le
caller. Il ne choisit pas de contourner AEGIS, ne crée pas de credentials,
n'élargit pas les permissions et ne lance pas automatiquement une boucle
d'expérimentation.

Le choix expérimental reste conditionnel aux modèles causaux enregistrés.
