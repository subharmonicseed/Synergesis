# SYN — Protocole de la frontière du possible v1

**25 octobre 2026 · Pré-enregistrement conceptuel · Aucun résultat expérimental nouveau revendiqué.**

Ce protocole prolonge la [constitution du scaphandre ontologique](SYN_SCAPHANDRE_ONTOLOGIQUE_V1.md). Il s'applique à **SYN en tant qu'histoire de coopération cognitive**, pas seulement à Synergesis comme logiciel.

## 1. Problème scientifique

Hypothèse H1 : une méthode qui documente le **cadre limitant** d'un ancien problème, explore d'autres opérations accessibles puis exige un **retour vers un résultat indépendant** permet d'identifier davantage de possibilités pertinentes que (a) la réponse immédiate habituelle ou (b) le simple rappel des conversations passées, à coûts comparables.

H0 : cette méthode ne produit pas d'amélioration vérifiable ; elle peut seulement accroître le nombre d'idées séduisantes, le coût, la latence ou les hallucinations.

Nous ne présumons ni conscience collective, ni créativité radicalement nouvelle, ni amélioration du modèle fondamental.

## 2. Typologie préalable des limites

Avant d'affirmer qu'une impossibilité a été dépassée, identifier **le type de limite** :

| Type | Exemples | Réouverture possible ? |
|---|---|---|
| Conceptuelle | Problème cadré comme choix A/B alors que « tester puis choisir » est une troisième opération | Oui, si nouveau cadre pertinent et testable |
| Informationnelle | Donnée ou mesure manquante | Oui, si nouvelle source contrôlée |
| Instrumentale | Pas d'outil pour effectuer l'opération | Oui, si un outil nouveau est *effectivement disponible* |
| Compétence opérationnelle | Outil existant, mais non choisi, mal employé ou non coordonné | Oui, par politique de sélection ou procédure éprouvée |
| Ressources | Temps, énergie, budget, capacité de calcul | Sous conditions mesurées ; coût à déclarer |
| Physique / logique | Violation démontrée d'une contrainte physique ou logique | Non par simple changement de vocabulaire ou de modèle |
| Réglementaire / sécurité / autorisation | Interdiction, consentement absent, équipement non qualifié | Pas de « contournement » ; respecter la condition externe |
| Indéterminée | Aucune tentative suffisante pour conclure | Ne **pas** la qualifier d'impossibilité démontrée |

**Règle dure : « nous ne l'avons jamais tenté » ≠ « c'était impossible ».**

## 3. Formalisation prudente

Soit `G` un objectif, `B` un budget, `C_t` les capacités et procédures disponibles à un instant `t`, et `S` un ensemble de contraintes de sécurité, d'autorisation et de vérification.

`A_t(G,B,C_t,S)` désigne **les opérations connues et admissibles** permettant de poursuivre `G`, non le véritable ensemble exhaustif de toutes les possibilités du monde.

Une transformation `T` est candidate à élargir cette frontière si :
1. une opération `a*` est précisément spécifiée ;
2. sa faisabilité sous `C_{t+1}` est montrée dans des conditions comparables ;
3. elle n'était pas démontrablement accessible avec `C_t` sous les mêmes contraintes **ou** le résultat est présenté plus prudemment comme « nouvellement observé », sans prétention à une impossibilité antérieure ;
4. la conséquence pour un objectif humain est identifiée, sans inventer l'approbation de cet objectif.

Seule une comparaison témoin ou une borne technique explicite peut renforcer l'affirmation `a* ∉ A_t`. L'absence d'essai ou de log ne suffit pas.

## 4. La fiche de transformation (unité de mémoire)

Pour chaque candidate, enregistrer :

```yaml
id: EXEMPLE-001
intent: "But confirmé ; pas une intention attribuée silencieusement"
starting_frame: "Comment le problème était représenté"
claimed_limit:
  type: "conceptuelle | informationnelle | instrumentale | ..."
  evidence: "source précise ou statut non vérifié"
  epistemic_status: "hypothese | observation | resultat_verifie"
proposed_reframe: "Nouvelle question, représentation ou opération"
new_capability_event: "Événement précis, date, version, outil ; ou aucun"
new_operation: "Ce que le système pourra faire concrètement"
counterfactual: "Ce qui se produirait sans changement de cadre"
invariants: "Budget, sécurité, contraintes, objectifs confirmés"
falsifier: "Observation qui réfuterait l'avantage proposé"
baseline_receipt: null
treatment_receipt: null
independent_replication: null
negative_result: null
transfer_to_new_case: null
cost_and_privacy: "Coût et informations nécessaires"
status: "propose | teste | confirme_borne | refute | non_concluant"
next_reopening_condition: "Événement qui justifie un nouvel essai"
```

Cette fiche est un modèle conceptuel, **pas** une API branchée au système en cours. Les reçus doivent correspondre à des artefacts vérifiables, pas à des affirmations du modèle.

## 5. Deux changements de perspective à comparer

### Perspective contextualisée (« l'interprète »)

Accède uniquement au contexte autorisé, à l'intention confirmée, aux contraintes et aux résultats réellement établis de nos échanges.

### Perspective partiellement dépaysée (« l'étranger »)

Accède au problème et aux contraintes vérifiées, **sans le récit personnel qui pourrait orienter vers la réponse attendue**. Pas de transmission de conversations privées à des services non autorisés.

Le troisième rôle est un **évaluateur indépendant** : il juge résultats et pertinence, pas l'élégance des justifications. Plusieurs prompts du *même* modèle ne constituent pas des observateurs statistiquement indépendants et ne garantissent aucune objectivité.

## 6. Trois pilotes ciblés dans notre histoire

### P1 — Mauvais cadrage de « feu »

- **Intention** : continuer la recherche conceptuelle, plutôt que lancer automatiquement une exécution informatique.
- **Échec historique** : interprétation locale de « feu » comme signal d'écriture dans GitHub, alors que le fil cherchait une perspective nouvelle sur l'ensemble de nos échanges.
- **Baselines** : réponse sans contexte ; réponse avec rappel narratif.
- **Variante** : contrôle de cohérence entre intention globale, travail local et retour attendu, avec interprétations alternatives.
- **Mesure** : sur fragments tenus à l'écart et dont la correction est masquée, l'évaluateur juge si le cadrage était approprié ; compter les questions superflues et les retards d'exécution.
- **Réfutation** : pas de gain en fidélité, ou davantage de faux recadrages et de latence.

### P2 — Routage Mistral / outils exacts

- **Fait déjà rapporté** dans [SYN_RECURSIVE_RESULTS_2026-10-25.md](SYN_RECURSIVE_RESULTS_2026-10-25.md) : sur 36 tâches synthétiques réservées, 11/36 pour la politique initiale et 36/36 pour la politique cumulative, selon les comptes rendus de l'expérience.
- **Interprétation valide et limitée** : le système a mieux sélectionné **des exécutants préexistants** pour des familles de tâches connues.
- **Ce qui reste à démontrer** : produire une *nouvelle* méthode ou une *nouvelle* opération lorsque le bon solveur n'existe pas encore ; ne pas confondre routage appris et découverte scientifique, ni les résumés GitHub avec un audit indépendant complet.
- **Prochain essai** : tâche réservée hors familles entraînées, sans solveur exact préinstallé ; comparer un assistant sans outillage nouveau, un assistant avec outils et une approche transformant le problème (par exemple inventer une mesure discriminante) ; examen des coûts et succès réels.
- **Réfutation** : amélioration expliquée par fuite de réponses, accès asymétrique à un solveur ou changement de budget.

### P3 — Gabarit titane : quand le « possible » est contraint

- **Intention** : concevoir un dispositif de formage réellement utilisable.
- **Objection historique** : charge admissible, interfaces avec la presse et tenue mécanique insuffisamment établies ; la forme CAO seule ne suffit pas.
- **Erreur interdite** : déclarer le gabarit faisable ou libéré pour essai simplement parce qu'un nouveau modèle, un nouveau dessin ou une nouvelle idée existe.
- **Réouverture acceptable** : obtenir les cotes machine, les hypothèses mécaniques et la revue qualifiée nécessaire, puis effectuer des validations hors danger.
- **Résultat attendu à ce stade** : `bloque — preuves manquantes`, pas `nouvellement possible`.

Ces pilotes servent de cas de départ ; ils ne constituent pas un échantillon aléatoire représentatif de toutes nos conversations.

## 7. Plan d'évaluation préenregistrable

Avant de voir les résultats, constituer un corpus de **30 demandes** (idéalement plus si disponibles) réparties entre : exploration conceptuelle, action technique, interprétation ambiguë, résultat contesté, reprise d'une impasse.

- **A — Standard** : demande immédiate et contexte autorisé de base.
- **B — Mémoire narrative** : même budget plus résumé du passé, sans protocole spécial.
- **C — Retour transformant** : même budget de texte, évaluation du cadrage, hypothèse de limite, perspective alternative, condition de réfutation et retour vers l'intention.

Randomiser l'ordre, masquer les noms des bras, garder modèles/température/outils/budgets comparables, interdire l'utilisation des 30 cas pendant la conception, documenter tous les échecs. La sélection d'exemples historiques avec correction connue ne permet qu'un exercice rétrospectif ; une prospective nouvelle est nécessaire pour affirmer une capacité d'anticipation.

**Métrique primaire :** proportion de situations où une possibilité *pertinente et exécutable* apparaît avec une justification de ses conditions d'accès, telle que jugée sur critères préspécifiés par un évaluateur indépendant.

**Métriques secondaires :** fidélité de cadrage, fausses possibilités (affirmation sans preuve), suggestions non autorisées, accord complaisant, utilité perçue, diversité des perspectives, temps, tokens, coût, taux d'abstention pertinent, maintien de l'autonomie de l'utilisateur.

L'absence de nouvel outil ou le manque de preuve doit conduire à `inconclusif`, non à une réussite fabriquée. Une proposition conceptuelle peut être notée *féconde* sans être notée *exécutée*.

## 8. Critères d'arrêt et de sécurité

Refuser de confondre :
- risque physique avec autorisation d'essai ;
- dispositif réglementé avec liberté de contournement ;
- connaissance personnelle enregistrée avec consentement à diffusion ;
- modèle « étranger » avec garant d'impartialité ;
- résultat vérifié sur une fixture avec compétence générale ;
- créativité verbale avec innovation opérationnelle.

Si le protocole produit des affirmations non étayées ou des interprétations psychologiques envahissantes, privilégier une solution plus simple.

## 9. Suite autorisée

Le prochain jalon est **un jeu de cas et des critères de jugement aveugles**, puis un essai comparatif documenté. Il n'est pas d'ajouter directement un nouveau module de curiosité au runtime de Synergesis.

L'intégration éventuelle doit démontrer un gain mesuré, préserver AEGIS/RISK/REALITY et ne pas exposer les données personnelles dans le dépôt.

## Sources intellectuelles

- Margaret A. Boden (1998), *Creativity and artificial intelligence*, https://doi.org/10.1016/S0004-3702(98)00055-1 — créativité combinatoire, exploratoire, transformationnelle.
- OpenAI (2025), *Expanding on what we missed with sycophancy*, https://openai.com/index/expanding-on-sycophancy/ — personnalisation et renforcement d'accord non critique.
- Les comptes rendus techniques du dépôt sont des sources de résultats expérimentaux spécifiques, non des validations générales de ce protocole.

**Statut : protocole proposé, pas expérience réalisée ; résultats ouverts, y compris l'échec.**
