# SYN — test prospectif d'ablation d'architecture (v0)
**25 octobre 2026, Europe/Paris.** Préprotocole; aucun essai de SYN à 4 bras n'a été exécuté.

## Question causale
À modèle et ressources fixés, les gains de réussite sur des tâches inédites résultent-ils de la **continuité de contexte**, de la **récupération de compétences**, ou de leur interaction ?

Les résultats ARC-AGI-3 montrent qu'un même modèle peut varier considérablement selon le harness; il faut des comparaisons appariées, et ne pas confondre le score sur un jeu public avec une preuve d'intelligence générale.

### Résultats externes à ne pas confondre
- ARC Prize (3 sept. 2026), GPT-6 Astra, jeu semi-privé : sous l'effort **high**, standard 54,8 % pour 40 705 $, Provider Adapter 99,9 % pour 18 817 $. Le Provider Adapter conserve l'état opaque de raisonnement et compacte le contexte : l'effet exact de chaque fonctionnalité *n'est pas isolé*. https://arcprize.org/blog/astra
- OpenAI (29 juillet 2026), GPT-5.6 Sol, jeu public : standard 13,3 % et harness avec contexte conservé + compaction 38,3 %, tokens de sortie divisés environ par 6. Cela reste une comparaison de configurations et non une preuve de capacité générale. https://openai.com/index/how-two-settings-tripled-our-arc-agi-3-scores/
- NVIDIA (21 août 2026), AVO et Claude Opus 5 : 100,00 RHAE sur les 25 environnements publics, 183 niveaux, vs baseline modèle annoncé à environ 30 %; performances auto-rapportées et évaluées sur **jeu public**. https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/
- Le problème du transfert sur compétences inédites reste posé : https://arxiv.org/abs/2609.39148

## Deux expériences distinctes

**A. Diagnostic local léger**, un premier générateur déterministe en trois domaines : calcul, calendrier, graphes.
- Générer le pack avec `python curiosity-journal/tools/syn_holdout_pack_v0.py --out /chemin/local/prive/pack-01 --model-id VERSION-GELEE` (utiliser un répertoire n'existant pas).
- **Release** : `release/train_examples.jsonl` (exemples visibles au concepteur de compétences), `release/manifest.json` (liste des 24 IDs de test et conditions); **holdout** : `holdout/test_prompts.jsonl` (ne rendre visible qu'après gel des compétences); **sealed** : `sealed/oracle.jsonl`, `sealed/seed.txt` (réservés à l'évaluateur; **ne jamais mettre dans le dépôt public**).
- Trois domaines, 4 exemples d'entraînement et 8 problèmes inédits par domaine par défaut. Les problèmes sont des exercices **jouets**, faciles, avec schémas connus; la séparation des questions ne garantit pas de généralisation scientifique.
- Utiliser ensuite le scoreur `curiosity-journal/tools/syn_skill_transfer_eval_v0.py` avec un fichier de tentatives produit par de **vraies exécutions** de modèles ou agents. Ne jamais fabriquer les tentatives à partir de l'oracle.
- Critère de succès de l'étape A : aucune fuite de réponse et exactitude du classement de fichiers/scoreur; le score d'un agent n'est **pas** encore observé.

**B. Essai causal exigeant**, avec environnement interactif inconnu et traces de chaque action.
- Établir, avant exécution, deux facteurs indépendants avec le même modèle et effort :
  * **M0/S0** : contexte réinitialisé, aucune compétence récupérée;
  * **M1/S0** : historique utile conservé/compacté, sans récupération de compétences;
  * **M0/S1** : contexte réinitialisé, compétences autorisées mais aucune continuité d'épisode;
  * **M1/S1** : contexte conservé et compétences récupérées.
- Pour isoler **compaction** de **rétention**, idéalement ajouter une deuxième ablation au sein de M1; ne pas interpréter l'effet combiné comme l'effet pur de la mémoire.
- Mêmes domaines, distribution de niveaux, règles d'accès, outils, budget de tokens et coût plafonné. Randomiser ordre, séparer tests d'entraînement et essais; verrouiller l'identifiant exact du modèle et la version des outils.
- Score principal : succès sur tâches inconnues + efficacité en actions (pré-enregistré), pondération fixée par domaine avant tout essai. Secondaires : durée, coût, erreurs récupérées, transfert vers nouvelle famille, régressions et répétabilité sur plusieurs seeds.
- Oracle, niveaux cachés, données d'arbitrage, sécurité et limites de ressources doivent être **hors du contrôle de l'agent**. Ne jamais prétendre une évaluation sur échantillon privé quand l'agent a vu les questions ou la graine.
- Un score élevé **ne prouve pas** une AGI. Inversement, un score faible sur des exercices jouets ne réfute pas toutes les architectures d'intelligence générale.

## État d'implémentation
- Instrument existant vérifié localement : 11 tests du scoreur `syn_skill_transfer_eval_v0.py` réussis.
- Générateur `syn_holdout_pack_v0.py` vérifié localement : 6 tests, 24 tâches test réparties sur trois domaines, exécution bout-en-bout sur **96 tentatives fictives** permettant de confirmer la détection des régressions.
- **Aucune mesure de performance réelle de SYN**, aucun essai ARC-AGI-3, aucun appel de modèle supplémentaire et aucun pouvoir d'auto-modification créé.
- Le scoreur actuel compare `baseline/journal/research/skills` : ceci est un diagnostic **multicomposants**, **pas** l'ablation factorielle M×S décrite en B. Ne pas attribuer un effet causal à un seul composant à partir de ce diagnostic.
