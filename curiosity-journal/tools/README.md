# SYN-CURIOSITY — banc d'essai du transfert de compétences (v0)

**Extension exécutable v1 :** voir [la boucle d'héritage vérifié](../../docs/SYN_RECURSIVE_INHERITANCE_V1.md)
et `python -m synergesis_recursive_trial`. Elle exécute les stratégies, vérifie
leurs résultats puis transmet une politique à un nouveau processus. Les limites
et la distinction entre mémoire, sélection d'outils et apprentissage du modèle
sont décrites séparément. Les évaluateurs v0 ci-dessous restent inchangés.

**Essai PC des quatre variations de prompts :** [résultats exécutés et lanceur
avec reçus](../../docs/SYN_FOUR_ARM_PC_TRIAL_2026-10-25.md). Le modèle local a
réellement répondu à 24 requêtes : chacun des quatre bras obtient 2/6 sur ces
exercices synthétiques, sans gain observé. Le texte v0 ci-dessous décrit l'état
historique de l'évaluateur ; il ne remplace pas ce reçu d'exécution plus récent.

**État réel (25 octobre 2026) : évaluateur implémenté et testé sur données entièrement SYNTHÉTIQUES. Aucun bras de SYN n'a encore été exécuté. Aucune AGI démontrée.**

Ce répertoire contient un évaluateur hors ligne, sans appel au réseau, LLM ni exécution de code de compétence. Il mesure sur les **mêmes tâches** l'effet descriptif de quatre configurations : `baseline`, `journal`, `research`, `skills`. L'évaluateur vérifie les identifiants de tâche et modèle, l'absence de chevauchement explicite entraînement/test, la présence de chaque bras, les doublons, les budgets de jetons déclarés et les régressions. Il compare par égalité stricte les réponses produites à un oracle distinct.

## Utilisation

Depuis la racine du dépôt :

```bash
python -m unittest discover -s curiosity-journal/tools -p 'test_syn_skill_transfer_eval_v0.py' -v
python curiosity-journal/tools/syn_skill_transfer_eval_v0.py \
  --manifest manifest.json \
  --oracle oracle.jsonl \
  --attempts attempts.jsonl
```

**N'exécuter la seconde commande qu'avec ses propres fichiers d'expérience pré-enregistrée**. Aucun `manifest.json`, `oracle.jsonl` ou `attempts.jsonl` réel n'est fourni dans ce dépôt.

`manifest.json` (exemple de *structure*, pas une expérience) :

```json
{
  "schema": "syn-skill-transfer-eval-v0",
  "study_id": "pilot-preregistered-001",
  "model_id": "same-model-and-version-in-all-arms",
  "arms": ["baseline", "journal", "research", "skills"],
  "train_task_ids": ["train-01"],
  "test_tasks": [
    {"task_id": "a1", "domain": "domain-a"},
    {"task_id": "b1", "domain": "domain-b"}
  ],
  "token_budget_per_arm": 10000
}
```

`oracle.jsonl` (conservé **hors accès de l'agent**, à publier seulement après le gel des réponses) :

```jsonl
{"task_id":"a1","answer":"TRUE"}
{"task_id":"b1","answer":"FALSE"}
```

`attempts.jsonl` : 4 lignes par tâche, une par bras, exactement le même `model_id` et le même budget maximum pour chacun.

```jsonl
{"task_id":"a1","arm":"baseline","model_id":"same-model-and-version-in-all-arms","answer":"FALSE","tokens_used":120,"skill_ids":[]}
{"task_id":"a1","arm":"journal","model_id":"same-model-and-version-in-all-arms","answer":"TRUE","tokens_used":160,"skill_ids":[]}
{"task_id":"a1","arm":"research","model_id":"same-model-and-version-in-all-arms","answer":"TRUE","tokens_used":190,"skill_ids":[]}
{"task_id":"a1","arm":"skills","model_id":"same-model-and-version-in-all-arms","answer":"TRUE","tokens_used":140,"skill_ids":["skill-general-v1"]}
```

Les exemples ci-dessus ne constituent **pas** un jeu d'essai complet (il manque les lignes de `b1`) et n'ont aucun résultat scientifique.

## Mesures calculées

- Taux de réussite exact par bras et par domaine.
- Gain apparié `skills - baseline` et `skills - journal`, en proportion des mêmes tâches.
- Tâches **réparées** par les compétences et tâches présentant une **régression** par rapport au témoin.
- Nombre de jetons déclarés par bras et domaines dans lesquels les identifiants de compétences ont été rapportés.

## Limites importantes

- Le code **ne crée pas** de questions, n'appelle aucun modèle et **n'exécute aucune expérience** : il score uniquement des réponses et des vérités que d'autres lui fournissent.
- L'oracle est un fichier *supposé* indépendant. L'évaluateur ne peut vérifier ni son origine, ni son indépendance, ni sa fiabilité, ni le gel préalable des données. Les responsables de l'expérience doivent produire des preuves externes et préserver les jeux cachés.
- Les déclarations de `model_id`, `tokens_used` et `skill_ids` peuvent être falsifiées par l'opérateur; le programme ne mesure pas lui-même le coût. Des limites égales ne prouvent pas une dépense égale.
- Le programme ne garantit ni confidentialité d'un jeu caché, ni absence de contamination sémantique, ni randomisation, ni équivalence des prompts et permissions.
- Les scores sont descriptifs, sans p-value ni intervalle de confiance : une amélioration numérique sur deux domaines ne démontre pas un transfert généralisé.
- Tester en dehors de ce script les effets des agents sur le monde réel, la sécurité, la fiabilité des preuves et les décisions humaines. Les bras n'ont pas le droit d'éditer leur oracle ni leur évaluateur.

## Justification scientifique

- Piao et al. (révision 7 oct. 2026), *Do Self-Evolving Skills Generalize to Held-Out Tasks?* : https://arxiv.org/abs/2609.39148
- SkillsBench (fév. 2026), essais appariés avec et sans compétences et effets négatifs : https://www.skillsbench.ai/skillsbench.pdf
- SkillLearnBench, COLM 2026, qualité, trajectoire et résultat : https://cxcscmu.github.io/SkillLearnBench/
- ContinualSkillBench (août 2026), apprentissage en contexte contre compétences : https://arxiv.org/abs/2608.03874

La première étape utile est un **test complet sur des tâches inédites** préparées par un tiers, en séparant traitement, témoin, oracle et dépôt des résultats. Les 11 tests unitaires vérifient uniquement la mécanique logicielle.
