# SYN-BELIEF-RESEARCH — 519 tests

Base : Synergesis_integrated_503_green_2026-09-12.zip.
SHA-256 de la base : 2bc6ef2b3014ee56829809ed70de56944eb49310c520f786844213e7d790d1a2.

## Trajet ajouté

Croyance provisoire suspendue ou expirée → scan explicite → ResearchNeed audité → tick ROAM explicite → session bornée → nouvelles Evidence.

Le nouveau module synergesis_belief_research.py est raccordé à la stack par `belief_research_policy`. Cette option exige que les croyances provisoires soient elles-mêmes configurées. La policy fournit le domaine de recherche, les mesures de priorité, un cooldown par sujet, un nombre maximal de nouvelles demandes par scan et une limite de demandes en attente produites par ce module.

`stack.belief_research.scan_once()` peut remplir l'agenda, mais ne lance aucune recherche. Si l'option est activée, `stack.service.tick_once()` appelle le scan avant de sélectionner au plus un besoin. Une garde revérifie ensuite que la révision visée existe toujours et demeure suspendue ou expirée, juste avant de lancer la recherche. Aucun scheduler, réseau ou processus de fond n'est créé par cette livraison.

## Boucles bornées et persistance

- Une seule demande par révision de croyance, y compris après recherche ou redémarrage.
- Un cooldown persistant par sujet s'applique aux révisions successives.
- Le nombre de nouvelles demandes par scan est borné ; la limite de demandes en attente concerne celles que ce module possède, sans annuler les demandes des autres producteurs.
- Une enquête de fusion déjà en attente et liée à la même inférence évite une nouvelle demande. Ce module ne prend pas possession de cette enquête existante.
- Une intention est d'abord enregistrée dans le Glyph Graph, puis ajoutée à ResearchAgenda. Après interruption entre ces deux écritures, un nouveau scan matérialise cette intention sans duplication.
- Si une croyance redevient active, ou si sa révision est remplacée, la demande encore en attente créée par ce module est annulée. Les demandes déjà exécutées restent dans l'historique.
- La garde de fraîcheur protège aussi un appel au contrôleur qui aurait lieu sans nouveau scan.

Les questions demandent des preuves indépendantes et des contre-preuves, avec `hypothesis=None`. Les mesures de priorité sont des paramètres explicites, pas des probabilités de vérité déduites de l'expiration.

## Limites conservées

ROAM rapporte des Evidence ; son résultat ne promeut pas automatiquement une croyance en Fact et ne réactive pas la croyance expirée. Les autres mécanismes de fusion et d'admission restent nécessaires. Le module ne crée aucune autorité, permission, capacité ou nouvelle sonde.

Le système suppose un seul écrivain et une horloge UTC de confiance. La vérification juste avant recherche réduit l'obsolescence en fonctionnement synchrone ; ce n'est pas un verrou transactionnel entre plusieurs processus concurrents.

Les limites bornent les créations, la file du module et les sessions. La lecture de l'historique utilise encore les projections existantes du graphe et de l'agenda ; le coût du scan n'est pas constant et une indexation sera utile pour de longs historiques. Une erreur de recherche conserve le comportement du service ROAM existant ; cette livraison n'ajoute pas de stratégie de retry ou de backoff.

## API

```python
from synergesis_belief_research import BeliefResearchPolicy
from synergesis_roam_attention import AttentionMeasurements

# Fournir au builder avec provisional_belief_policy et la fusion déjà configurées.
belief_research_policy = BeliefResearchPolicy(
    domain="science",
    measurements=AttentionMeasurements(
        uncertainty=0.8, expected_impact=0.5, staleness=0.8, novelty_gap=0.5,
    ),
    cooldown_seconds=300,
    max_new_per_scan=2,
    max_pending=8,
)
```

Les valeurs d'attention ci-dessus sont un exemple de configuration, à adapter au domaine. `scan_once()` retourne seulement les besoins nouvellement créés, et non les intentions anciennes réparées lors de la reprise.

## Vérification exécutée

Commande : `python3 -m pytest -q` à la racine de cette version.
Résultat : **519 passed**, aucun échec ni test ignoré ; deux avertissements de dépréciation des dépendances.

16 nouveaux cas vérifient : provenance de la demande, absence d'exécution pendant le scan, déduplication après redémarrage et après recherche, annulation d'une demande redevenue inutile, garde avant départ, cooldown entre révisions, coexistence avec les besoins de fusion, absence de besoin issu d'une perception isolée rejetée, reprise d'une intention après interruption, validation de la policy, limites de scan et de file, absence de recherche pour une croyance active et intégration complète à la stack.

Le test de stack parcourt les vrais objets Perception Bus, Fusion, World Model, ResearchAgenda, service ROAM et AURA. Après expiration, un tick produit une session et des Evidence ; le tick suivant reste idle et la croyance reste expirée. Les sources de ce test sont des adapters contrôlés : aucun résultat de recherche Internet réel n'est revendiqué.
