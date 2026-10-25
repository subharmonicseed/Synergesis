# Résultats exécutés — héritage récursif SYN, 25 octobre 2026

## Résultat central

Deux essais locaux terminés, sur **36 problèmes réservés**, donnent :

| Configuration | Essai 1 | Réplication | Total descriptif |
| --- | ---: | ---: | ---: |
| SYN₀ / reset | 4/12 | 7/24 | 11/36 |
| Journal textuel seul | 4/12 | 5/24 | 9/36 |
| SYN₁ : premier héritage | 12/12 | 22/24 | 34/36 |
| SYN₂ : héritage cumulatif | 12/12 | 24/24 | 36/36 |

SYN₂ répare 25 erreurs de SYN₀, sans régression observée sur ces tâches. Le gain
descriptif cumulé est de 69,4 points de précision exacte. La réplication a été
fixée pendant le premier essai, avant son résultat final, avec de nouvelles
graines et de nouvelles données. Les deux essais utilisent exactement la même
identité des trois sources expérimentales et le même modèle.

Ces problèmes sont **synthétiques**, dans trois familles connues : arithmétique,
calendrier grégorien et chemin dans un graphe dirigé. Ce résultat mesure l'utilité
d'une politique de choix parmi des outils préexistants. Il ne démontre ni AGI,
ni nouvelle compétence algorithmique synthétisée, ni adaptation des poids de
Mistral, ni transfert à une science nouvelle.

## Effet réellement transmis

La politique de SYN₀ choisit `llm` dans les trois domaines. Après vérification du
premier lot, SYN₁ choisit `exact` en arithmétique et calendrier, et conserve `llm`
pour les graphes encore sans observations. SYN₂ hérite du premier lot et des
essais de graphe ; il choisit `exact` dans les trois domaines. Six nouveaux
processus ont rechargé les états sauvegardés et émis les décisions utilisées.

Dans le premier essai, SYN₁ atteint déjà 12/12 ; le second héritage réduit le
recours au modèle sans gain de précision supplémentaire. Dans la réplication,
SYN₂ répare aussi deux erreurs de graphe de SYN₁ : **22/24 → 24/24**. Les tests
logiciels vérifient qu'un lot ultérieur de contre-exemples peut inverser le choix
appris, et que retirer l'expérience ramène au défaut.

## Coûts mesurés

| Mesure | Essai 1 | Réplication |
| --- | ---: | ---: |
| Appels physiques réels à Mistral, entraînement compris | 33 | 57 |
| Jetons physiques mesurés par Ollama | 8 225 | 14 617 |
| Jetons de l'entraînement seul | 1 621 | 1 633 |
| Jetons des réponses réservées de reset | 2 235 | 4 357 |
| Jetons des réponses réservées du journal | 4 369 | 8 627 |
| Jetons des réponses réservées de SYN₁ | 856 | 1 589 |
| Jetons des réponses réservées de SYN₂ | 0 | 0 |

Le zéro concerne l'inférence sur les problèmes réservés, **pas** le coût de
l'apprentissage : SYN₂ hérite de neuf essais de modèle et neuf essais d'outil par
étude. Les outils utilisent du calcul local dont la durée est conservée ; les
jetons ne mesurent pas tout le coût matériel.

Les requêtes strictement identiques partagent un reçu d'exécution entre les bras.
Les dépenses par bras sont les jetons qu'ils auraient consommés en exécution
séparée ; leurs sommes ne sont pas le nombre physique d'appels. Il ne s'agit pas
de quatre agents indépendants ni de quatre conditions à dépense effective égale.

## Vérifications et limites statistiques

- Les réponses et les politiques sont figées avant consultation des résultats
  réservés. Aucun résultat de test n'est transmis comme lot d'entraînement.
- L'auditeur hors ligne reconstruit les générations, les décisions, les réponses
  brutes, les scores, les coûts et les oracles. Il vérifie 144 règlements de
  prédiction, 288 événements de réservation/consommation et 3 897 événements de
  graphe. Les réservations restantes sont nulles.
- Une analyse secondaire, ajoutée après le premier essai, accepte aussi les
  entiers JSON comme réponses numériques. Les quatre scores restent inchangés
  dans les deux études : le gain ne s'explique pas seulement par l'exigence d'une
  chaîne JSON. Le score primaire exact est conservé.
- Les intervalles de Wilson à 95 % sont inclus dans chaque `results.json`.
  Pour SYN₂ : [0,758 ; 1] sur 12 tâches, puis [0,862 ; 1] sur 24 tâches. Pour
  reset : [0,138 ; 0,609], puis [0,149 ; 0,492].
- Les tests exacts de McNemar exploratoires syn2/reset valent respectivement
  0,0078125 et 0,0000152587890625. Ils ne sont pas corrigés pour des comparaisons
  multiples et ne justifient aucune généralisation hors de ces familles.
- Les graines des tâches diffèrent entre études ; le modèle et sa graine
  d'inférence restent fixes. Il ne s'agit pas d'une étude de plusieurs modèles
  ni d'une estimation de variabilité entre générations de modèles.
- L'opérateur et le coordinateur ont accès à l'oracle. Le travailleur reçoit un
  problème sans réponse, mais n'est pas isolé du système contre du code hostile.
  Aucun tiers ne certifie l'antériorité des engagements locaux.

## Modèle, code et intégration

Modèle effectivement appelé : `syn-mistral-import:latest`, Mistral 7B Instruct
v0.3 Q4_K_M, digest
`6fb2c6e2bdc5ce5719719586b099710eb63942060cbb0be64a190f4c633b9d0c`.
Ollama 0.35.1, Docker Engine 29.8.1, Python WSL 3.12.3. Aucun téléchargement de
modèle, appel cloud ou clé d'API n'a été utilisé.

Identité des trois sources expérimentales communes aux deux études :
`2ff8bcfa21db83334c6722063d290f8b46cc719b4309943a5b2efce9b003d6c6`.

La copie de départ correspond exactement au commit GitHub
`df8ce871705f195975815db0de0bfb78fc777943` de
`feat/syn-curiosity-observatory-v0`. La proposition utilise une nouvelle branche
`feat/syn-recursive-inheritance-v1`, empilée sur cette branche expérimentale.

Le contrôle d'accès AEGIS, le budget RISK, le vérificateur REALITY et le moteur de
prédiction existants participent réellement aux essais. Les 18 résultats du premier
entraînement ont aussi été rejoués dans un nouveau MethodLedger de SYN-ROAM :
ce sélecteur choisit les outils exacts pour arithmétique/calendrier et le modèle
pour graphe, où son rendement brut est à égalité. Sa règle diffère explicitement
du routeur avec lissage et pénalité de coût.

L'installation habituelle WSL, à manifeste de 259 entrées, précède la branche
GitHub à 263 entrées. Elle ne contient pas cette boucle récursive. L'expérience
utilise ses propres fichiers et registres ; elle n'installe pas automatiquement
la politique dans le service de conversation de l'utilisateur.

## Recalcul

L'archive de preuves remise localement au fondateur contient deux dossiers d'étude,
les requêtes/réponses réelles, les états, les graines, les oracles, les journaux,
les reçus de vérification et la décision de réplication. Sa publication dans le
dépôt public est hors de cette proposition. Après extraction :

```bash
python -m synergesis_recursive_audit syn-recursive-real-001
python -m synergesis_recursive_audit syn-recursive-real-002
```

Ces commandes ne font aucun appel de modèle. Sous Windows natif, ajouter
`--skip-ledgers` pour les contrôles de contenu seuls ; les registres SYN exigent
POSIX/WSL. Le mode portable indique explicitement `ledgers: null`.

Les sources, les tests et le protocole exécutable sont détaillés dans
[SYN_RECURSIVE_INHERITANCE_V1.md](SYN_RECURSIVE_INHERITANCE_V1.md).
