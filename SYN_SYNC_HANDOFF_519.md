# Point de reprise — Synergesis 519

Reprendre depuis Synergesis_integrated_519_green_2026-09-12.zip et vérifier son checksum et MANIFEST_SHA256.json avant de modifier le code.
Parent : 503-green, SHA-256 2bc6ef2b3014ee56829809ed70de56944eb49310c520f786844213e7d790d1a2.

Nouveau module : synergesis_belief_research.py.
Activation explicite : belief_research_policy au builder, avec provisional_belief_policy configurée.
scan_once remplit un agenda borné ; le service tick explicite peut lancer une recherche après vérification de fraîcheur. Déduplication, cooldown, annulation et reprise après interruption sont persistants.
ROAM produit des Evidence, jamais une promotion automatique des croyances en faits.

Suite complète : 519 tests réussis. Lire SYN_BELIEF_RESEARCH_VALIDATION.md pour la portée et les limites.
Les anciens rapports et handoffs conservés sont historiques. La synchronisation entre conversations reste explicite par snapshots cohérents.
