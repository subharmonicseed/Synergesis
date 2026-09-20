# SYN-WORLD-REVISION — 12 septembre 2026

## Livré

`synergesis_world_revision.py` fournit WorldModelPredictionBridge, à la fois provider de prédictions et récepteur de leurs résultats. Il enveloppe l'estimateur empirique existant et utilise la mémoire sémantique et le Glyph Graph du cœur audité.

Avant chaque action, l'estimation probabiliste utilisée est enregistrée comme fait décrivant une estimation, avec une référence explicite dans la prédiction. Après règlement, le pont vérifie les identités, le verdict binaire, les liens de provenance et la présence du résultat dans le ledger de prédictions. Il recalcule l'estimation par action et stratégie et ajoute une révision traçable. Une répétition du même résultat après redémarrage ne crée pas une deuxième révision.

L'historique demeure append-only. `current_belief(action_type, strategy_key)` expose la dernière estimation ; les snapshots existants du World Model conservent toutes les versions. Les faits sans rapport et les autres stratégies ne sont pas révisés. Le prochain appel de prédiction reprend l'estimateur empirique sur le ledger enrichi, pas une règle causale inventée.

La confiance 1.0 du fait signifie que la valeur de l'estimation est enregistrée exactement ; elle ne signifie pas que l'action réussira avec certitude. La probabilité est stockée dans la valeur du fait.

## Portée

Il s'agit d'une attribution à la dépendance prédictive effectivement utilisée. Les traces portent `causal_responsibility: not_identified`. Ce module n'attribue pas une responsabilité causale entre plusieurs hypothèses, ne modifie pas les règles THALES et ne résout pas les facteurs confondants. Ce travail reste nécessaire pour une attribution causale générale.

L'estimateur conserve son comportement existant de repli par type d'action lorsqu'une stratégie n'a pas d'historique. La révision suivante utilise les observations de la stratégie concernée. La mémoire et ce pont supposent un seul écrivain ; aucune garantie transactionnelle entre plusieurs fichiers n'est ajoutée. L'historique des estimations peut augmenter le volume de faits vu par les sélecteurs existants : leur filtrage par version courante reste à intégrer avant utilisation prolongée.

## Vérification exécutée

Commande :

```bash
python3 -m pytest -q test_synergesis_world_revision.py test_synergesis_prediction.py test_synergesis_prediction_curiosity.py test_synergesis_cognitive_core.py test_synergesis_glyph_protocol.py
```

Résultat : **40 passed**, dont **8 nouveaux cas**. Ils couvrent mise à jour et prédiction suivante, historique, liens du graphe, absence de révision sans observation, rejeu après redémarrage, incohérences d'identité/résultat/probabilité/score et isolation des stratégies et faits étrangers.

Ces tests utilisent des verdicts contrôlés de test ; ce n'est pas un nouveau banc de 120 ou 430 actions réelles.

## Intégration préparée, validation complète bloquée

`synergesis_world_revision_integration.patch` raccorde le pont à la stack canonique existante, en conservant Agent Loop v5 et le moniteur Curiosity. La stack originale n'a pas été remplacée : appliquer ce patch attend un ensemble de sources cohérent.

Blocages observés sur les sources récupérées, indépendamment du nouveau module :

- `synergesis_glyph_agent_v2.py`, importé par la stack, n'a pas été retrouvé après deux recherches.
- Les tests Agent Loop v5 échouent avant exécution : `runtime_attested` est attendu par SYN-REALITY mais absent des classes d'origine acceptées dans AEGIS récupéré. Résultat de cette suite : cinq échecs et un succès. Aucune autorité de sécurité n'a été ajoutée pour contourner ce problème.
- La collecte globale a aussi signalé des dépendances Python manquantes. Les dépendances identifiées ont été installées avec succès, mais la suite globale n'a pas été validée, en raison des incompatibilités de sources ci-dessus.

Les anciens comptes rendus annonçant 312 tests réussis ne sont donc pas reproduits ici. La prochaine étape d'intégration exige de récupérer la version cohérente d'AEGIS et le module d'audit manquant, puis de tester la stack et le comportement réel de bout en bout.
