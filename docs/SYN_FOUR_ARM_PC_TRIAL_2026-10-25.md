# Banc historique à quatre variations de prompts — essai PC réel

Le 25 octobre 2026, le banc `syn_four_arm_trial_v0.py` a été exécuté avec le
modèle Ollama local installé, sur six nouveaux exercices réservés, dans trois
familles : arithmétique, calendrier et graphe dirigé. Les données sont
**synthétiques** ; les appels au modèle sont **réels**. Les quatre conditions
restent des variations de prompts, sans déploiement de quatre systèmes SYN.

| Condition historique | Réponses exactes | Jetons mesurés |
| --- | ---: | ---: |
| baseline | 2/6 | 1 211 |
| journal : exemples d'entraînement | 2/6 | 1 845 |
| research : exemples et procédure fournie | 2/6 | 2 149 |
| skills : exemples, procédure et consigne de réutilisation | 2/6 | 2 346 |

**Aucun gain observé**, aucune réparation ni régression appariée. Les quatre
conditions réussissent les mêmes deux questions. L'ajout de contexte augmente
les jetons sans amélioration sur cet échantillon. Ce pilote minuscule ne démontre
ni absence universelle d'utilité des compétences, ni transfert, ni performance
générale de SYN, ni AGI. La procédure du bras research est fournie par le banc ;
aucune recherche indépendante n'est exécutée dans ce bras.

Il y a eu **24 appels physiques**, sans mutualisation entre les bras ni relance
automatique, pour **7 551 jetons** mesurés. Les réponses ont été figées avant
l'appel séparé à `syn_skill_transfer_eval_v0.py`. Les six oracles ont ensuite été
recalculés avec les algorithmes indépendants du banc récursif ; les 24 couples
requête/réponse et leurs empreintes concordent avec les tentatives évaluées.

## Amélioration concrète du lanceur

`curiosity-journal/tools/syn_four_arm_recorded_v1.py` réutilise les prompts, le
parseur et le format de tentatives existants. Il ajoute :

- Les corps HTTP effectivement envoyés et reçus, le statut, les durées, les
  empreintes et les jetons, conservés avant la validation du format de réponse.
- La vérification du digest du modèle installé avant et après chaque inférence.
- Un ordre randomisé et enregistré avant l'essai, avec graine 26.
- Une limite de contexte de 4 096 jetons, une sortie de 128, une température de
  zéro et la même graine d'inférence dans les quatre conditions.
- Une vérification du budget de chaque bras avant l'appel en réservant le
  maximum contexte+sortie ; un maximum de 120 appels et une échéance de 30 minutes.
- Le refus d'écraser une expérience, et l'arrêt explicite avec reçus conservés
  si une réponse, son coût ou l'identité du modèle est invalide. Une expérience
  interrompue n'est pas notée comme terminée et n'est pas rejouée automatiquement.

Les six tests ajoutés utilisent des doubles de transport clairement signalés.
Ils vérifient les corps envoyés, les empreintes, le contexte, la limite de budget,
les appels supplémentaires, les formats invalides et les coûts manquants. Ils ne
sont pas des données de performance expérimentale.

## Exécution et oracle

```bash
python curiosity-journal/tools/syn_holdout_pack_v0.py \
  --out results/four-arm-pack-NEW --train-per-domain 2 --test-per-domain 2 \
  --model-id syn-mistral-import:latest

python curiosity-journal/tools/syn_four_arm_recorded_v1.py \
  --manifest results/four-arm-pack-NEW/release/manifest.json \
  --train results/four-arm-pack-NEW/release/train_examples.jsonl \
  --test results/four-arm-pack-NEW/holdout/test_prompts.jsonl \
  --out results/four-arm-run-NEW

# Uniquement après le gel de toutes les réponses :
python curiosity-journal/tools/syn_skill_transfer_eval_v0.py \
  --manifest results/four-arm-pack-NEW/release/manifest.json \
  --oracle results/four-arm-pack-NEW/sealed/oracle.jsonl \
  --attempts results/four-arm-run-NEW/run/attempts.jsonl
```

Le lanceur n'a aucun argument d'oracle et ne reçoit ni réponses réservées ni
graine de génération des questions. Il reçoit les exemples d'entraînement
autorisés. L'opérateur peut accéder aux fichiers : **ce n'est pas une évaluation
aveugle de l'opérateur ni une isolation du système contre du code hostile**.

Le modèle est `syn-mistral-import:latest`, Mistral 7B Instruct v0.3 Q4_K_M,
digest `6fb2c6e2bdc5ce5719719586b099710eb63942060cbb0be64a190f4c633b9d0c`.
Aucun modèle téléchargé, aucune clé ou API de modèle cloud, aucun profil privé
fourni. Les appels restent sur l'interface de bouclage.

Ce banc est un pilote de prompts, à côté de la boucle expérimentale intégrant
AEGIS/RISK/REALITY décrite dans [le rapport récursif](SYN_RECURSIVE_RESULTS_2026-10-25.md).
Il n'étend aucune permission de ce système et ne prétend pas bénéficier lui-même
de toute la pile d'exécution SYN. Le résultat négatif est conservé séparément des
36 tâches du routeur ; les deux expériences ne doivent pas être fusionnées en
un score de performance du produit SYN.

Les scores agrégés sont publiés dans le dépôt. Le jeu, l'oracle, les requêtes,
réponses et reçus détaillés sont livrés localement au fondateur ; leur archive
complète n'est pas incluse dans cette publication publique.
