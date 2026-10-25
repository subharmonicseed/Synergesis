# SYN-CURIOSITY — Mémoire × compétences : plan factoriel exécutable v1
**Date : 25 octobre 2026.** Branche expérimentale; ne pas interpréter ce pilote comme une AGI ou un apprentissage autonome validé.

## Problème scientifique effectivement corrigé

L'ancien `syn_four_arm_trial_v0.py` comparait `research` (exemples + méthode fournie par humain) à `skills` (mêmes éléments + une consigne supplémentaire). **Il ne séparait pas l'effet de la mémoire de celui d'une compétence.**

Le nouveau `syn_factorial_ablation_v1.py` utilise deux facteurs indépendants : M = exposition à des exemples résolus et S = exposition à une carte de compétence candidate, fournie séparément.

| Nom historique du bras (pour compatibilité des reçus) | Mémoire M | Carte de compétence S |
|---|---:|---:|
| `baseline` | 0 | 0 |
| `journal` | 1 | 0 |
| `research` | 0 | 1 |
| `skills` | 1 | 1 |

ATTENTION : dans **ce protocole v1**, le nom historique `research` signifie **compétence seule**, PAS une recherche externe. Aucun des quatre bras n'active `ResearchAgenda`, la navigation Web ni une véritable instance indépendante de SYN.

## Première utilisation concrète, sans achat de crédits Work

Le protocole marche sur l'ordinateur où le dépôt est cloné, avec Python >=3.11; Ollama est facultatif pour seulement *préparer* les questions.

```bash
# Remplacer mistral:7b par le nom exact indiqué par "ollama list".
python curiosity-journal/tools/syn_holdout_pack_v0.py \
  --out syn-prive/pack-001 --model-id mistral:7b

# Les cartes de cet exemple sont rédigées par un humain.
python curiosity-journal/tools/syn_factorial_ablation_v1.py prepare \
  --manifest syn-prive/pack-001/release/manifest.json \
  --train syn-prive/pack-001/release/train_examples.jsonl \
  --test syn-prive/pack-001/holdout/test_prompts.jsonl \
  --cards curiosity-journal/tools/human_skill_cards_example.json \
  --out syn-prive/questions-factorial-001

# Si le modèle local tourne sur 127.0.0.1:11434 :
python curiosity-journal/tools/syn_factorial_ablation_v1.py run-ollama \
  --manifest syn-prive/pack-001/release/manifest.json \
  --train syn-prive/pack-001/release/train_examples.jsonl \
  --test syn-prive/pack-001/holdout/test_prompts.jsonl \
  --cards curiosity-journal/tools/human_skill_cards_example.json \
  --out syn-prive/resultats-factorial-001

# Si et seulement si les 96 réponses sont bien terminées :
python curiosity-journal/tools/syn_factorial_ablation_v1.py analyze \
  --manifest syn-prive/pack-001/release/manifest.json \
  --oracle syn-prive/pack-001/sealed/oracle.jsonl \
  --attempts syn-prive/resultats-factorial-001/attempts.jsonl \
  --out syn-prive/analyse-factorial-001.json
```

Les chemins `syn-prive` désignent des fichiers locaux à ne pas pousser sur GitHub : ils contiennent les réponses attendues, la graine et potentiellement des traces de recherche. Les sorties ne sont pas écrasées. `prepare` n'appelle aucun modèle; `run-ollama` utilise uniquement le serveur loopback local, sans abonnement API OpenAI.

## Mesures préalablement définies

Pour une proportion de succès `p00` sans les deux facteurs, `p10` avec mémoire seule, `p01` avec compétence seule, et `p11` avec les deux :

- Mémoire sans compétence = `p10 - p00`
- Mémoire avec compétence = `p11 - p01`
- Compétence sans mémoire = `p01 - p00`
- Compétence avec mémoire = `p11 - p10`
- **Interaction = `p11 - p10 - p01 + p00`**

Ces effets sont descriptifs, non des preuves de causalité en l'absence de répétitions indépendantes, de contrôles de contamination et de tâches suffisamment discriminantes.

Les 24 questions sont présentées dans un ordre pseudo-aléatoire reproductible; l'ordre des quatre bras est tourné de façon à répartir les positions entre conditions (six premières positions par bras sur 24 questions). Cela réduit le biais de position mais ne garantit pas des ressources ou des contextes parfaitement comparables.

Les cartes de compétences comportent une origine `human_authored` ou `syn_candidate`. Les candidates de SYN doivent citer des IDs d'exemples d'entraînement; cela établit une provenance **déclarative**, sans prouver qu'une compétence a été acquise. Le reçu de préparation inclut le SHA-256 du fichier de cartes; une véritable préinscription indépendante reste à réaliser.

## Validation et limites

- Correction de compatibilité dans `syn_skill_transfer_eval_v0.py` : des `skill_ids` peuvent être enregistrés sur les bras `research` (S=1, M=0) et `skills` (S=1, M=1); interdits sur `baseline` et `journal`.
- **9 tests ciblés du design factoriel exécutés dans la session de développement**, sur données synthétiques. Un **dixième test d'intégration** du jeu généré à l'évaluateur existant est publié; vérifier son exécution par CI, ne pas le déclarer réussi avant confirmation.
- Le programme peut préparer 96 requêtes ou solliciter Ollama local; **aucun accès direct au PC ni aucune exécution de ce modèle dans cette conversation**.
- L'ajout d'une carte humaine mesure un effet d'information procédurale dans un prompt, **pas un apprentissage d'AGI**.
- Le premier jeu (arithmétique, calendrier, graphes) est peu difficile et peut atteindre un plafond; le prochain protocole scientifique doit porter sur des tâches inédites difficiles, avec des cartes de compétences réellement créées et figées à partir de l'entraînement.

## Décision

Le prochain critère de progression sera **l'exécution avec un modèle réel** et la comparaison `S=1` contre `S=0` sur les mêmes questions, puis la comparaison de cartes `syn_candidate` avec des cartes humaines à coût égal. Tout gain qui disparaît sur une famille inconnue est une absence de transfert, même si les résumés de SYN sont convaincants.
