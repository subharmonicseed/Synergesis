# ModelContextBridge v0

Le bridge prépare un dossier JSON de développement : objectif, extraits Python,
provenance et avertissements. Deux assistants peuvent recevoir exactement le même
dossier pour comparer leurs propositions. Il ne lance ni le code extrait, ni un
modèle, ni les tests cités. Il ne modifie pas le dépôt source.

## Contrat livré

`build_context_pack` reçoit une racine de dépôt de confiance, un commit explicite,
l'empreinte SHA-256 attendue du manifest et des `SliceRequest(path, symbol, role)`.
Les noms sont qualifiés (`AegisGuard._grant_valid_for`, par exemple). Les rôles sont
`focus`, `interface` et `test`. Les extraits focus/test gardent leurs lignes et
leurs décorateurs ; les interfaces exposent les signatures, avec corps omis.
Le contexte des classes et les dépendances non résolues sont signalés.

Le manifest peut contenir tous les types de fichiers du dépôt. Seuls les fichiers
Python explicitement demandés sont lus pour extraction, vérifiés contre le
manifest puis analysés par AST sans import. Plusieurs méthodes du même fichier
sont possibles. Les symboles inconnus ou ambigus et les fichiers altérés sont
refusés. Les lectures sont bornées et refusent les liens symboliques sous la racine
sur les plateformes POSIX compatibles ; une plateforme sans ces garanties échoue.

Le manifest est vérifié contre une empreinte fournie par l'appelant. L'appelant
reste responsable de l'association entre commit et manifest : écrire un SHA de
commit dans la requête n'est pas une attestation Git. Obtenir cette association
par un canal de confiance avant de produire un dossier.

## Budget et limites

Plafond par défaut : 6000 unités, dont une réserve de 512. Le dossier JSON complet
est mesuré avant toute sortie. Si le plafond est dépassé, aucune version tronquée
n'est produite : réduire explicitement la tâche. Maximum 32 sélections, dont
4 extraits focus. Les tailles de sources, du manifest et de l'objectif sont bornées.

Sans tokenizer injecté, le compteur est une **estimation caractères / 4**, annoncée
dans le dossier lui-même. Ce n'est pas une garantie de 6000 tokens du modèle.
L'API accepte `counter` et `counter_identity` pour fournir un compteur versionné
adapté au modèle. Le comptage concerne le texte retourné ; les messages système,
les enveloppes du fournisseur et les réponses doivent être budgétés séparément.
Le compteur injecté est une dépendance de confiance.

Les tests sont marqués `referenced_not_run`. Aucune preuve d'exécution n'est
inventée. Les imports sont indiqués sans résolution transitive. La sélection de
pertinence reste à la charge du préparateur : cette v0 ne construit pas une carte
globale automatique, ne remplace pas les dépendances par des Glyphs et ne garantit
pas que les extraits suffisent à une modification donnée.

Le filtrage des secrets est heuristique : noms de fichiers sensibles, marqueurs
de clés et affectations littérales sensibles dans les sources sélectionnées.
Ce filtre n'est pas une certification d'absence de secrets. Relire le dossier
avant de le transmettre. Le code extrait est une donnée non fiable ; le bridge
n'empêche pas à lui seul les injections d'instructions dans un modèle destinataire.

## Exemple vérifiable sur AEGIS

L'exemple versionné `examples/model_context_aegis.json` provient de la base PR #45 :

- commit : `f2cd397e74ffffca9be6d6b0fff55ad56e70e4a7` ;
- manifest SHA-256 : `2cfd7faebe1f248c08202f846905ea20e38ca70bc33d36277d8ffd613c9c2125` ;
- deux extraits AEGIS et un test de frontières de chemins ;
- comptage estimatif séparé dans `examples/model_context_aegis_accounting.json`.

Avec le module de cette branche installé et une copie exacte de cette base dans
`/chemin/base-pr45`, créer une sortie neuve :

```bash
python -m synergesis_model_context_bridge \
  --root /chemin/base-pr45 \
  --commit f2cd397e74ffffca9be6d6b0fff55ad56e70e4a7 \
  --manifest-sha256 2cfd7faebe1f248c08202f846905ea20e38ca70bc33d36277d8ffd613c9c2125 \
  --objective 'Vérifier les frontières des permissions signées AEGIS' \
  --slice synergesis_aegis.py:_resource_matches \
  --slice synergesis_aegis.py:AegisGuard._grant_valid_for \
  --slice test_syn_resource_contract.py:test_path_contract_respects_component_boundaries_and_traversal:test \
  --budget 6000 --reserve 512 --output contexte-aegis.json
```

Pour une autre révision, fournir ses propres commit et empreinte vérifiés. Le
fichier de sortie existant n'est jamais écrasé. Le résultat n'est pas transmis
à un assistant automatiquement.

## Validation de ce lot

Sur CPython 3.12 : **734 tests passent**, dont 31 tests ciblés du bridge ;
deux avertissements de dépréciation déjà présents dans les dépendances.
L'exemple AEGIS utilise 1627 unités estimées, plus 512 de réserve (2139 / 6000).
Les 212 fichiers de la base de l'exemple ont été comparés aux blobs GitHub de
PR #45 ; toutes les empreintes correspondent. Les contrôles CI de la nouvelle
PR conservent leurs reçus pour Python 3.11 et 3.12.
