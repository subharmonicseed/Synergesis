# SYN-CURIOSITY — quatre conditions exécutables (préprotocole v0)
**25 octobre 2026 — Europe/Paris.** Le lanceur est implémenté et testé; **aucune exécution réelle de SYN ou de modèle Ollama n'a été faite dans ce cycle ChatGPT**.

## Pourquoi ce composant

Le scoreur `syn_skill_transfer_eval_v0.py` ne recevait que des réponses. Le nouveau `syn_four_arm_trial_v0.py` prépare un paquet sans oracle et peut interroger, à la demande explicite de l'utilisateur, un **modèle Ollama installé localement**. Il produit alors des tentatives JSONL contenant les réponses réellement générées, l'identifiant du modèle et les jetons comptés par Ollama.

Les **quatre bras sont des conditions de prompt**, pas quatre processus SYN complets :

| Bras | Contexte présenté |
|---|---|
| `baseline` | Question du jeu tenu à l'écart uniquement |
| `journal` | Question + exemples résolus de l'entraînement |
| `research` | Journal + méthode générique **écrite par l'humain**, et non une vraie recherche internet |
| `skills` | Research + consigne de réemploi de la même méthode, identifiée comme compétence **candidate non validée** |

**Ne jamais interpréter une différence `skills - research` comme un gain causal d'une compétence créée par SYN** : le dispositif ne forme ni ne promeut encore les compétences. Il sert à tester les connexions techniques, et à révéler éventuellement des écarts provoqués par les conditions de prompt.

## Chaîne exacte à exécuter sur le PC (Python ≥3.11, Ollama local facultatif)

Depuis la racine du dépôt, après avoir créé un dossier d'essai **privé et absent** :

```bash
# 1. Créer 12 exemples d'entraînement + 24 tâches d'évaluation + oracle privé
python curiosity-journal/tools/syn_holdout_pack_v0.py \
  --out mon-essai-prive/pack-001 --model-id mistral:7b

# 2. Vérifier les 29 tests logiciels existants (11 + 6 + 12)
python -m unittest discover -s curiosity-journal/tools -p 'test_syn_*_v0.py' -v

# 3a. Sans frais d'API : préparer des prompts à recopier dans quatre chats ChatGPT
python curiosity-journal/tools/syn_four_arm_trial_v0.py prepare \
  --manifest mon-essai-prive/pack-001/release/manifest.json \
  --train mon-essai-prive/pack-001/release/train_examples.jsonl \
  --test mon-essai-prive/pack-001/holdout/test_prompts.jsonl \
  --out mon-essai-prive/questions-001

# 3b. OU, si Ollama tourne sur l'ordinateur et que mistral:7b est disponible :
python curiosity-journal/tools/syn_four_arm_trial_v0.py run-ollama \
  --manifest mon-essai-prive/pack-001/release/manifest.json \
  --train mon-essai-prive/pack-001/release/train_examples.jsonl \
  --test mon-essai-prive/pack-001/holdout/test_prompts.jsonl \
  --out mon-essai-prive/run-001

# 4. Si et seulement si les 96 réponses Ollama réelles sont présentes :
python curiosity-journal/tools/syn_skill_transfer_eval_v0.py \
  --manifest mon-essai-prive/pack-001/release/manifest.json \
  --oracle mon-essai-prive/pack-001/sealed/oracle.jsonl \
  --attempts mon-essai-prive/run-001/attempts.jsonl
```

**Ne pas exécuter `3a` et `3b` simultanément dans le même répertoire de sortie.** Le lanceur refuse l'écrasement et ouvre une connexion **uniquement** vers `127.0.0.1:11434` (port configurable); aucun jeton API n'est requis. Il ne télécharge aucun modèle automatiquement et ne reçoit aucun secret.

## Test logiciel effectué dans ChatGPT

- Le scoreur antérieur : **11/11 tests** sur données artificielles.
- Le générateur de défis : **6/6 tests**.
- Le nouveau lanceur : **12/12 tests** (contrôle oracle, contamination exacte, identifiant du modèle, sorties non écrasées, jetons réels et reçus après interruption).
- Le parcours de bout en bout a préparé **24 questions × 4 bras = 96 requêtes**, sans réponse de l'oracle dans les prompts. Le flux de 96 retours a été testé avec un **faux backend uniquement** : il ne représente ni Mistral ni ChatGPT.

## Hypothèses et limitations

- **ChatGPT abonnement ≠ accès API ChatGPT**. Les prompts sont utilisables manuellement dans des chats indépendants, mais un script ne peut pas lancer automatiquement 96 requêtes payées par l'abonnement ChatGPT.
- Un flux Ollama local est possible sur le PC où le service est installé, mais il **n'a pas tourné ici**. Le modèle nommé `mistral:7b` est un exemple : relever le véritable identifiant local avant l'essai.
- Le générateur arithmétique/calendrier/graphe est volontairement élémentaire, avec risque de plafond de performance; aucune généralisation open-world ne peut en être déduite.
- Le lanceur **n'appelle pas** les modules `ResearchAgenda`, `AEGIS`, `Executor` ni `SYN-REALITY` : il produit des requêtes de test, pas une boucle d'agent autonome.
- Le générateur connaît l'oracle local mais le lanceur ne le charge pas. C'est une séparation **de fichiers**, non une isolation de sécurité contre un agent autorisé à lire tout le disque.
- Le programme conserve les réponses déjà reçues si un essai échoue, mais **ne sait pas reprendre automatiquement** une session interrompue. Le scoreur refuse l'analyse incomplète.
- L'ordre des bras est fixe, les prompts sont de longueur différente, les procédures sont humaines : conditions comparables sur tâches/modèle, pas sur information ou coût exact. Un protocole causal robuste exigera de randomiser l'ordre et de mieux isoler les conditions.
- Ne jamais publier le dossier `sealed/` ni des secrets locaux dans le dépôt public. Les expériences réelles ne sont pas préinscrites OSF et n'ont pas été exécutées.

## Prochain vrai critère de succès

Lancer au moins une fois le parcours `3b` sur un modèle réel, vérifier 96 reçus et les coûts, et conserver les résultats vérifiables de manière privée. Ensuite seulement, ablation factorielle **contexte M0/M1 × compétences S0/S1**, et tests cachés de transfert. **Aucun progrès de SYN ni indice d'AGI ne peut être inféré de ces tests logiciels seuls.**
