# SYN-CURIOSITY — reçu de contrôle négatif, 25 octobre 2026

**Type : essai logiciel exécuté localement, sans LLM et sans SYN.** Il ne constitue ni une mesure de généralisation, ni une victoire d'un agent, ni une preuve d'AGI.

## Procédure vérifiable

Depuis la racine du dépôt :

```bash
python curiosity-journal/tools/run_negative_control_v0.py \
  --out dossier-fixture-prive-n-existant-pas
```

Le script génère **12 exercices d'entraînement**, **24 exercices de test** (8 chacun : calcul, calendrier, graphes dirigés) et leurs réponses dans des fichiers séparés. Il construit quatre bras `baseline`, `journal`, `research`, `skills` et produit les **96 tentatives** grâce à `smoke_rule_solver_v0.py`, programme déterministe indépendant de l'oracle. Il ouvre le fichier `sealed/oracle.jsonl` **uniquement après** avoir enregistré les 96 réponses.

Seed **publique et synthétique** de la démonstration : 20261025. N'utiliser jamais cette seed publique pour prétendre que ces tâches constituent un benchmark réellement inconnu.

## Résultat effectivement obtenu dans l'environnement d'essai

| Bras | Tâches réussies | Taux |
|---|---:|---:|
| baseline | 24/24 | 100 % |
| journal | 24/24 | 100 % |
| research | 24/24 | 100 % |
| skills | 24/24 | 100 % |

Différence appariée `skills - journal` : **0,00**.
Tâches dégradées : **0**, tâches réparées : **0**.
Appels du faux agent : **0**. Réponses produites par le solveur algorithmique indépendant : **96**. Jetons LLM : **0**, car **aucun modèle de langage n'a été appelé**.

Les scripts de référence sont `syn_holdout_pack_v0.py`, `syn_four_arm_trial_v0.py`, `syn_skill_transfer_eval_v0.py`, `smoke_rule_solver_v0.py` et `run_negative_control_v0.py`; tous situés dans `curiosity-journal/tools/`.

### Interprétation correcte

Ce contrôle négatif montre que, **pour un solveur spécialement adapté à ces trois familles de problèmes**, le benchmark est au plafond et ne possède aucun pouvoir discriminant entre bras. Il ne montre **pas** que les versions réelles de SYN sont équivalentes; elles n'ont pas été lancées. Il ne montre pas non plus que les conditions sont causalement isolées : `research` utilise une procédure humaine et `skills` une consigne de réutilisation, non des modules SYN autonomes. La différence de longueur des prompts est un facteur confondant.

Tests unitaires réellement effectués dans cet environnement :
- `test_syn_skill_transfer_eval_v0.py` : 11/11;
- `test_syn_holdout_pack_v0.py` : 6/6;
- `test_syn_four_arm_trial_v0.py` : 12/12.

**29/29 tests passés dans ces trois modules**. Cela ne constitue pas un test intégral de Synergesis et ne garantit pas le passage de CI GitHub.

## Prochaine expérience qui pourrait avancer la connaissance

Utiliser un véritable backend local ou, manuellement, des chats indépendants avec le même modèle, **avec horodatage, reçus des réponses, coûts effectifs et questionnements plus difficiles**, puis mesurer les performances séparées. Sur une génération dont le témoin réussit 100 % des tests, augmenter la difficulté plutôt que d'inventer un gain. Ensuite seulement, remplacer les procédures humaines par des compétences réellement compilées par SYN et préalablement gelées.

Tous les artefacts de l'essai réexécuté sont **locaux à l'environnement de travail**, pas écrits dans ce dépôt public : seules la recette et les conclusions publiques non sensibles y figurent.
