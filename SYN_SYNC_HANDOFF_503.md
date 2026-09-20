# Point de reprise — Synergesis 503

Reprendre depuis Synergesis_integrated_503_green_2026-09-12.zip, extrait dans un dossier neuf.
Cette archive descend du snapshot portable479 dont le SHA-256 est 2e19622fc571a7177a3df3a942f3b2854ff28c97017af5c68bf8fd192a944b13.

Nouveau module : synergesis_provisional_beliefs.py.
Lire SYN_PROVISIONAL_BELIEFS_VALIDATION.md pour la policy et les limites.
La stack accepte provisional_belief_policy. Les croyances actives sont exposées par core.world.snapshot().provisional_beliefs, séparément des facts ; confidence reste None.
Les observations contradictoires suspendent les croyances, la TTL exclut les états expirés, et le graphe conserve l'historique.

503 tests passent dans l'environnement de cette livraison. Les corrections de portabilité de portable479 sont conservées.
Vérifier le checksum de l'archive et MANIFEST_SHA256.json avant modification. Les anciennes validations présentes dans le snapshot sont historiques.
La synchronisation entre conversations reste explicite par snapshot ; elle n'est pas automatique.
