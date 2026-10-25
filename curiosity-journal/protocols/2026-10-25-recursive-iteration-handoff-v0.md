# SYN — « devenir la version suivante » : passage d'état vérifiable (v0)

**25 octobre 2026.** Hypothèse d'architecture **récursive**, pas modification du modèle de langage ni autonomie du PC.

## Définition opérationnelle

Si SYNₙ produit une hypothèse ou rencontre un contre-exemple, **SYNₙ₊₁ doit en hériter et prendre au moins une décision différente quand cela est justifié**, plutôt que répéter le même récit ou un journal chronologique non lu. Cette transformation doit être observable, reproductible et susceptible de réfutation.

Le programme `curiosity-journal/tools/syn_iteration_handoff_v0.py` consomme uniquement des **entrées explicites** au format `syn-curiosity-v1` et un éventuel passage d'état antérieur. Il produit un fichier `syn-iteration-handoff-v0` avec :
- Un compteur `iteration`, le SHA-256 du contenu précédent et le SHA-256 du nouveau contenu (canonisé).
- Un registre des entrées héritées avec leurs empreintes, leur état et leur domaine.
- Une liste de **prochaines actions proposées**, triée par une priorité **heuristique non calibrée**, selon le résultat déclaré de la recherche.
- Les refutations prioritaires dirigent vers `investigate_refutation`; les hypothèses non testées vers `run_preregistered_test`; les résultats inconclusifs vers `seek_discriminating_evidence`; les conclusions étayées vers `independent_replication`.
- **Aucune action exécutée, aucun modèle appelé, aucune auto-modification, aucune écriture dans le journal local de SYN.** Les décisions émises sont des propositions pour revue humaine et ne contournent aucun budget, AEGIS, RISK ou REALITY.

## Expérience reproductible sur les entrées GitHub existantes

Dans un clone de la branche `feat/syn-curiosity-observatory-v0`, depuis la racine du dépôt :

```bash
mkdir -p syn-private/iteration-states

# Version N : une question encore non testée, déjà présente dans le journal
python curiosity-journal/tools/syn_iteration_handoff_v0.py \
  --entry curiosity-journal/entries/2026-10-25-46.json \
  --out syn-private/iteration-states/001.json

# Version N+1 : la même mémoire + nouveau constat contradictoire déjà enregistré.
# C'est une démonstration de recalcul, et NON un replay chronologique fidèle
# (l'entrée 44 précède effectivement la 46 dans le journal public).
python curiosity-journal/tools/syn_iteration_handoff_v0.py \
  --previous syn-private/iteration-states/001.json \
  --entry curiosity-journal/entries/2026-10-25-44.json \
  --out syn-private/iteration-states/002.json

# Vérifier que le registre a maintenant deux items, que previous_digest
# relie l'itération 002 à la 001, et que la file d'actions a changé.
python -m unittest discover -s curiosity-journal/tools \
  -p 'test_syn_iteration_handoff_v0.py' -v
```

Ces fichiers `syn-private/...` sont des exemples de destination locale, **pas** des secrets à déposer sur un dépôt public. Pour les expériences réelles, préserver la provenance des entrées et utiliser un registre indépendant si la protection contre une réécriture malveillante est nécessaire.

## Limites explicites

1. Les priorités sont calculées à partir des `selection_score` déjà présents et de petits ajustements fixes selon le résultat; les métriques du journal étaient auto-évaluées et **ne mesurent pas un gain d'intelligence**.
2. La chaîne SHA-256 détecte des altérations accidentelles du passage d'état précédent mais n'est **pas une signature ou une preuve externe d'antériorité**. Une personne pouvant réécrire tous les états peut recalculer toutes les empreintes.
3. La validation intégrée contrôle les champs utilisés et les incohérences évidentes; elle **n'authentifie ni l'étude scientifique, ni une conclusion, ni l'honnêteté du producteur**. Une revue indépendante reste nécessaire.
4. Les textes reçus de sources extérieures ne deviennent jamais des commandes exécutables. Le passage d'état ne transporte même pas le contenu des preuves ni le texte d'instruction libre, mais seulement les statuts normalisés, IDs et empreintes.
5. Les entrées déjà vues ne sont ni supprimées ni réimportées silencieusement : un identifiant dupliqué est rejeté. L'état conserve une trace de provenance mais **ne clôture pas une tâche**; prochaine version nécessaire pour liens question→évaluation et mécanisme explicite de fermeture.
6. Les sorties ne deviennent pas automatiquement les véritables objectifs de `ResearchAgenda` : ce dernier possède ses propres règles, sa provenance et ses permissions. L'intégration au superviseur ne doit intervenir qu'après revue, tests d'ablation et approbation.
7. Ceci prouve la **continuité déterministe d'un artefact logiciel**, et non la transformation spontanée de l'intelligence du LLM sous-jacent.

## Critère expérimental à venir

Même modèle et même corpus public, mêmes budgets et permissions, problèmes tenus à l'écart :
- Groupe A : chaque cycle recommence sans état hérité.
- Groupe B : hérite seulement du journal textuel.
- Groupe C : reçoit une file de recherche **conditionnée sur résultats et réfutations** provenant du mécanisme actuel.
- Groupe D : idem C avec révisions de compétences candidates évaluées indépendamment.

Mesurer la précision des prévisions prospectives, la réduction effective des erreurs, le nombre de nouvelles hypothèses testables, les régressions et le coût. L'effet propre du *passage d'état* n'est démontré que si C ou D dépasse A/B sur des tâches nouvelles à budgets comparables. Les prévisions USGS déjà déposées sont un début de données prospectives, pas encore cette évaluation.

**Principe : SYNₙ₊₁ ≠ SYNₙ + un journal. SYNₙ₊₁ doit dériver de l'expérience de SYNₙ, et l'utilité de cette transformation doit rester falsifiable.**
