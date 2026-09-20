# SYN-WORLD-REVISION — intégration complète
Date : 12 septembre 2026

## Statut

Le blocage d’intégration signalé précédemment n’est plus présent dans l’état actuel du projet :

- `synergesis_glyph_agent_v2.py` est disponible.
- `SYN-AEGIS` reconnaît `runtime_attested` dans ses classes d’autorité d’origine.
- `synergesis_world_revision.py` passe ses tests ciblés.
- `WorldModelPredictionBridge` est désormais raccordé à `synergesis_secure_roam_stack_v2.py`.

## Raccordement réalisé

La stack crée maintenant le `GlyphAuditedCognitiveCore` avant le moteur de prédiction afin que le pont World Model puisse référencer la mémoire sémantique et le Glyph Graph.

Quand la prédiction est activée :

1. `PredictionLedger` est construit.
2. `EmpiricalPredictionProvider` reste l’estimateur probabiliste empirique.
3. `WorldModelPredictionBridge` enveloppe cet estimateur.
4. `PredictionEngine.provider` devient le bridge.
5. Le bridge est enregistré comme `PredictionSettlementSink`.
6. Les erreurs de prédiction vérifiées par SYN-REALITY peuvent donc réviser la croyance probabiliste correspondante dans le World Model.
7. `PredictionCuriosityMonitor`, lorsqu’il est configuré, reste un sink indépendant ; la révision du World Model et la création de besoins ROAM ne sont pas confondues.

Le nouvel objet de stack expose aussi :

`world_revision: WorldModelPredictionBridge | None`

## Propriété obtenue

Avant l’action :

`World Model belief -> prediction`

Après un verdict binaire vérifié par SYN-REALITY :

`Reality verdict -> Prediction settlement -> World Model revision`

Le prochain appel de prédiction reprend ensuite l’estimation empirique révisée.

L’historique reste append-only : une révision ne détruit pas les croyances antérieures.

## Vérification supplémentaire d’intégration

Deux tests de stack ont été ajoutés :

- le bridge enveloppe réellement l’estimateur empirique utilisé par `PredictionEngine`;
- un résultat vérifié révise la croyance, puis la prédiction suivante reprend cette probabilité révisée.

Tests ciblés après raccordement :

`42 passed`

Suite Synergesis complète :

`322 passed, 0 failed`

## Limites conservées volontairement

Cette intégration attribue l’erreur à la croyance probabiliste effectivement utilisée pour la prédiction. Elle ne démontre pas encore une responsabilité causale.

Les traces conservent donc :

`causal_responsibility = not_identified`

Restent notamment à traiter dans une étape ultérieure :

- attribution causale entre plusieurs croyances/hypothèses concurrentes ;
- facteurs confondants ;
- filtrage explicite des anciennes versions de croyances dans les sélecteurs de contexte lors d’un fonctionnement très prolongé ;
- garanties transactionnelles multi-fichiers / multi-processus.

Aucune de ces limites n’empêche le raccordement actuel : le premier pont `PredictionError -> WorldModelRevision` est maintenant actif dans la stack canonique.
