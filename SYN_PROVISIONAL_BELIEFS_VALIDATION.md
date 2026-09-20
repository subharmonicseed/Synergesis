# SYN-PROVISIONAL-BELIEFS — 503 tests

## Base et modification

Base : Synergesis_portable_479_2026-09-12.zip.
SHA-256 de la base : 2e19622fc571a7177a3df3a942f3b2854ff28c97017af5c68bf8fd192a944b13.

Cette itération ajoute une projection durable de croyances provisoires au World Model, dérivée des fusions de perceptions existantes. Elle n'apprend pas les dépendances entre sources et ne transforme pas le support de fusion en probabilité de vérité.

Fichiers applicatifs : nouveau synergesis_provisional_beliefs.py ; raccordements dans synergesis_multisource_fusion.py, synergesis_cognitive_core.py et synergesis_secure_roam_stack_v2.py.

## Comportement

La policy est fournie explicitement au builder via `provisional_belief_policy`. Sans cette policy, aucun sink de croyances provisoires n'est activé. Elle doit viser le même observation_kind que la fusion et définir une durée de vie positive ainsi que des seuils de support, de marge et d'indépendance. Au moins deux groupes indépendants éligibles sont requis.

Une fusion auditée et liée à son Evidence AURA peut produire un HypothesisGlyph de statut `provisional`. Chaque révision conserve sujet, type d'observation, claim, support, timestamps de capture, expiration, référence à la fusion, à l'Evidence et à la révision remplacée. Elle expose `confidence=None`, `authorization_effect=none`, `runtime_local=false`. L'origine de ses perceptions demeure accessible par les liens ; une croyance inférée n'est pas elle-même une observation locale attestée.

Le graphe append-only est la source durable. Aucun Fact n'est inséré dans SemanticMemory. Les faits établis restent dans `WorldState.facts`, les croyances provisoires actives dans `WorldState.provisional_beliefs`. Les consommateurs existants qui ne lisent que les faits ne reçoivent donc pas silencieusement ces hypothèses. Les Evidence de fusion demeurent disponibles pour le Context Builder/AURA et le trajet ROAM existant.

API de lecture :

```python
stack.provisional_beliefs.current(subject)  # état actuel : provisional, suspended ou expired
stack.provisional_beliefs.history(subject) # révisions et rejets audités
stack.core.world.snapshot().provisional_beliefs  # seulement les croyances provisoires actives
```

Exemple de configuration, à transmettre avec les paramètres de fusion existants :

```python
from synergesis_provisional_beliefs import ProvisionalBeliefPolicy

provisional_belief_policy = ProvisionalBeliefPolicy(
    observation_kind="temperature_reading",
    ttl_seconds=60,
    minimum_independent_groups=2,
    minimum_support=1.0,
    minimum_margin=0.2,
)
```

## Temporalité et contradiction

- L'expiration est calculée à partir de la plus ancienne perception incluse, pas de l'heure d'importation. Une vieille preuve ne devient pas fraîche parce qu'elle est relue.
- Les observations futures ou déjà expirées sont rejetées sans remplacer la croyance courante.
- Une fenêtre d'observations plus ancienne ou chevauchant la fenêtre courante est conservativement rejetée.
- Une nouvelle fusion résolue qui contredit une croyance active la suspend. La claim active devient absente. Une observation ultérieure, entièrement plus récente et satisfaisant les seuils, peut établir une nouvelle croyance provisoire.
- Des fusions incompatibles au même instant suspendent la croyance ; l'ordre d'arrivée ne permet pas de choisir une vérité.
- Une nouvelle fusion indécise avec suffisamment de groupes éligibles suspend la croyance précédente. Une source isolée ou un nombre insuffisant de groupes éligibles ne peut pas la suspendre.
- Un rejeu de la même fusion ne renouvelle ni l'expiration ni l'état courant.
- L'expiration est une projection à la lecture : elle ne produit pas d'écriture automatique ni de boucle de fond.

Le moteur suppose une horloge UTC de confiance et un seul écrivain. Le comportement face à un recul de l'horloge système n'est pas durci ici. Les groupes d'indépendance restent configurés. Une répétition provenant des mêmes groupes n'accumule pas un surcroît de confiance : confidence demeure None. Ces croyances ne sont pas des vérités certifiées et ne confèrent aucune autorisation.

## Vérification exécutée

Commande : `python3 -m pytest -q` depuis la racine du projet.
Résultat : **503 passed**, aucun échec, aucun test ignoré ; deux avertissements de dépréciation de dépendances.

24 nouveaux cas couvrent admission, World Model séparé, provenance, expiration exacte, rejeu, redémarrage, invalidation et rétablissement, conflits simultanés, événements anciens/futurs, falsification de décisions, seuils supplémentaires, TTL invalides, expiration basée sur la perception la plus ancienne, protection contre une source isolée, absence d'accumulation artificielle et deux cas de vraie construction de stack.

Le test de stack parcourt Perception Bus → Fusion → Evidence AURA → sink provisoire → snapshot du World Model, avec trois sources dont deux corrélées. Le support vaut 1,7 et la confiance reste None. Il vérifie également que la mémoire de faits n'est pas augmentée et que la croyance disparaît de la vue active à expiration.

Les stimuli sont contrôlés dans les tests ; aucune caméra ni aucun périphérique audio réel n'a été ajouté. Le module ne lance aucune recherche ou action automatiquement.
