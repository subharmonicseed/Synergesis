# SYN — héritage exécutable et vérifié, v1

Cette version ajoute une boucle de **sélection de stratégies apprise sur des
résultats exécutés**, puis transmise à un nouveau processus. Elle ne modifie pas
les poids de Mistral et n'invente pas de nouveaux algorithmes. Les deux exécuteurs
sont fixés avant l'expérience : le modèle local installé et des outils exacts
bornés pour arithmétique, calendrier et accessibilité dans un graphe dirigé.

## Passage de SYN₀ à SYN₂

1. SYN₀ n'a aucune expérience : la stratégie par défaut est `llm` dans tous les
   domaines. Il possède déjà les mêmes outils que ses descendants.
2. Chaque stratégie est réellement exécutée sur les mêmes exercices
   d'entraînement. Les tentatives sont écrites et leur empreinte figée **avant**
   la comparaison à un oracle distinct. Le résultat déclaré par l'exécuteur
   n'est pas une preuve de réussite.
3. Les résultats sont vérifiés par SYN-REALITY et inscrits dans PredictionEngine.
   Un lot d'entraînement conserve tâches, réponses, usages mesurés et engagement
   sur les tentatives. Les succès sont recalculés depuis ces données.
4. SYN₁ hérite des observations d'arithmétique et de calendrier. SYN₂ conserve
   cet héritage et reçoit les observations de graphe. Les états sont chaînés par
   SHA-256, sans écrasement, avec statistiques et politique recalculables.
5. Trois **nouveaux processus** rechargent les trois états sauvegardés et décident
   sur les mêmes problèmes réservés. Leurs décisions, PID et empreintes d'état
   sont enregistrés. Le processus d'exécution reçoit seulement le problème, le
   nom de l'outil autorisé et, pour le bras mémoire, les exemples d'entraînement.
6. Toutes les politiques sont figées avant les essais réservés. Toutes les
   réponses de ces essais sont figées avant leur évaluation. Aucun résultat de
   test n'entre dans les générations apprises.

`synergesis_recursive.py` fournit le contrat, la vérification des lots, la
construction des générations, le chargement validé et `InheritedRouter.select`.
`synergesis_recursive_trial.py` réalise la boucle et les appels réels.
`synergesis_recursive_tasks.py` fournit les tâches exécutables et leur oracle.

## Ce qui est appris

Pour chaque couple domaine/stratégie, avec s succès sur n observations, la
probabilité estimée est `(s + 1) / (n + 2)`, issue d'un lissage Beta(1,1).
L'utilité est cette probabilité moins `0,01 × moyenne_des_jetons / 1000`.
L'outil exact consomme zéro jeton de modèle ; sa durée réelle est conservée dans
son reçu. Ce coût ne prétend pas mesurer l'énergie ou le coût matériel total.

La sélection exige au moins trois observations de **chaque** stratégie dans le
domaine. Elle maximise l'utilité, avec préférence pour la stratégie par défaut
en cas d'égalité exacte. Le coefficient et le seuil sont fixés par le contrat,
pas appris ou modifiés par l'état. Un domaine inconnu conserve le défaut.

Une égalité de précision peut donc conduire à préférer l'outil pour économiser
des jetons. Une amélioration de coût et une amélioration de précision doivent
être rapportées séparément. Trois observations ne constituent pas une garantie
statistique de fiabilité ni de non-régression.

## Comparaisons et coût

Les bras sont :

| Bras | Expérience disponible | Décision exécutée |
| --- | --- | --- |
| reset / SYN₀ | aucune | modèle par défaut |
| journal | exemples vérifiés des neuf exercices d'entraînement | modèle avec ces exemples dans le contexte |
| syn1 | état machine hérité du premier lot | choix par domaine de SYN₁ |
| syn2 | les deux lots, transmis et revérifiés | choix par domaine de SYN₂ |

Les outils, le modèle, sa quantification, le maximum de contexte et le maximum
de sortie sont identiques et figés. Les générations peuvent consommer moins de
ressources. Les conditions ne sont donc pas à dépense effective égale.

**Une requête strictement identique partage son exécution physique entre les
bras.** Le reçu source est référencé dans chaque tentative. Cette mutualisation
évite de répéter artificiellement le même appel déterministe ; elle ne représente
pas quatre agents indépendants. `physical_model_calls` et `physical_tokens`
mesurent les appels effectivement effectués. `tokens_if_run_alone` attribue à
chaque bras les jetons de ses requêtes, comme s'il était exécuté seul.

Le score primaire est la différence appariée de précision exacte syn2 − reset.
Le rapport fournit aussi les régressions, les réparations, les domaines, les
intervalles descriptifs de Wilson à 95 % et un test exact de McNemar exploratoire,
sans correction de multiplicité. Les essais restent petits et issus de trois
familles de problèmes connues. Aucun transfert à un domaine scientifique nouveau
n'est établi par ce protocole.

## Contrôles réellement utilisés

- AEGIS contrôle `recursive.solve` avant chaque nouvelle exécution physique.
  Cette action est explicitement autorisée par la configuration de l'expérience
  isolée, sans capacité réseau générale ni exécution de texte reçu du modèle.
- RISK-BUDGET réserve puis consomme une unité par exécution. Il s'agit ici d'une
  limite d'exposition expérimentale, **pas d'une estimation calibrée de risque**.
  La limite de 256, le nombre maximal d'appels, le plafond de jetons et l'échéance
  sont externes aux états hérités et ne peuvent être étendus par ceux-ci.
- Le transport est limité à `127.0.0.1`, sans proxy ni redirection. Aucun modèle
  n'est téléchargé. Le digest du modèle installé est vérifié avant et après
  chaque appel ; la température, la graine, le contexte et la sortie sont fixés.
- SYN-REALITY relit le reçu d'exécution et compare la réponse à l'oracle engagé.
  PredictionEngine enregistre les prévisions avant l'action et les erreurs après
  vérification. Le contrôle démontre une correspondance à cet oracle synthétique,
  pas la vérité scientifique d'une affirmation sur le monde.
- Une erreur de transport, un coût non mesurable ou un dépassement arrête l'essai
  sans reprise automatique. Une réservation ambiguë reste réservée. Les fichiers
  partiels sont conservés ; ils ne constituent pas un essai terminé.

`replay_into_roam` permet en outre de reconstruire le **ResearchMethodLearner
existant** dans un nouveau registre expérimental à partir des mêmes résultats
revérifiés. Ce registre utilise le rendement vérifié brut de ROAM ; sa règle de
sélection diffère de celle du routeur avec lissage et coût. L'adaptateur n'importe
rien dans le profil, ResearchAgenda, CuriosityJournal ou superviseur de l'utilisateur.

## Exécution

Sous le Python POSIX/WSL déjà équipé des dépendances du dépôt, Ollama étant actif :

```bash
python -m pytest -q test_synergesis_recursive.py
python -m synergesis_recursive_trial run \
  --model syn-mistral-import:latest \
  --out results/recursive-study-NEW \
  --train-per-domain 3 --test-per-domain 4 \
  --max-calls 48 --max-tokens 100000 --deadline-seconds 3600
python -m synergesis_recursive_audit results/recursive-study-NEW
```

Le répertoire doit être nouveau. Les sources, le profil et les journaux habituels
restent inchangés. Les registres historiques SYN exigent POSIX ; le contrat,
les états et le routeur seuls fonctionnent aussi sous Windows natif.

Les sorties comprennent le contrat engagé avant exécution, les graines de
reproduction, les lots d'entraînement, les états, les décisions après redémarrage,
les requêtes et réponses réelles, les tentatives réservées figées, les registres
AEGIS/RISK/REALITY/prédictions et `results.json`. Elles ne contiennent que les
problèmes synthétiques générés pour cet essai. Les réponses réservées et graines
peuvent être publiées **après** le gel ; elles ne sont alors plus secrètes pour
une expérience future utilisant les mêmes données.

L'auditeur hors ligne reconstruit les trois états et toutes les décisions, relit
les réponses brutes du fournisseur, recalcule les coûts, les scores et les oracles,
vérifie les engagements et les registres. Il propose aussi une analyse secondaire
annoncée comme postérieure au premier essai : accepter un entier JSON dans le
champ réponse en le convertissant en chaîne. Cette analyse de sensibilité ne
remplace pas la précision exacte préenregistrée.

## Limites de confiance

L'oracle et l'outil utilisent des algorithmes distincts : Decimal contre calcul
entier, calendrier jour par jour contre `datetime`, fermeture transitive de
Warshall contre parcours de graphe. Les tests vérifient leur accord sur 900
entrées et sur des limites calendaires. Ces deux programmes restent écrits dans
le même projet et peuvent partager une erreur de spécification.

Le travailleur ne reçoit aucune réponse réservée ni chemin d'oracle. La séparation
en processus concerne le flux normal d'information de code fixe et fiable ;
**ce n'est pas une isolation système contre du code hostile**. L'opérateur a accès
aux fichiers, et le processus coordinateur crée l'oracle. L'essai n'est donc pas
une évaluation aveugle de l'opérateur par un tiers.

Les empreintes détectent une altération et l'état est recalculé depuis les lots
fournis. Une personne capable de réécrire tous les lots et les états peut fabriquer
un autre historique cohérent. Aucun horodatage extérieur ni signature indépendante
ne certifie l'antériorité. Le journal public de curiosité n'est pas accepté comme
preuve de réussite sur la seule base d'un statut `supported`.

Ce lot établit une continuité **opérationnelle** d'expérience vers décision dans
un banc d'essai. Il ne démontre ni AGI, ni apprentissage des poids, ni synthèse
autonome de compétences, ni déploiement de cette politique dans le service utilisateur.
