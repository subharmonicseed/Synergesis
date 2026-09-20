# Synergesis 479 — validation de portabilité

Base : Synergesis_integrated_479_green_2026-09-12.zip.
SHA-256 de la base : 3675c950fbc31bfd2afb736c713e5b1851439a9094d7ad9c8853376d096219f1.
L'archive de base a été vérifiée, ainsi que les 140 fichiers de son manifest.

## Changements

Deux fichiers de tests ont été corrigés. Tous les modules applicatifs Python sont identiques au snapshot 479 reçu, y compris Risk Budget, Provenance Transport, Perception Bus et Multisource Fusion.

- Le schéma Glyph est chargé relativement au fichier de test, sans dépendre de /mnt/data.
- Le test processus utilise le chemin résolu de l'exécutable et un marqueur UUID unique. Il exige l'absence du marqueur avant lancement, exactement un processus vivant correspondant, le bon exécutable, le refus d'une allowlist incompatible, puis la disparition du marqueur après arrêt et collecte du processus.
- Le PID observé reste contrôlé comme entier positif. Il n'est plus comparé au PID de Popen : ces identifiants peuvent appartenir à deux espaces de noms différents. Aucun changement des permissions ou du filtre du probe n'a été effectué.

Le test prouve une corrélation de cycle de vie avec un marqueur unique ; il ne certifie pas une traduction de PID entre namespaces. Une fonctionnalité future visant à agir sur un PID observé devra résoudre explicitement cette traduction.

## Validation exécutée

Commande : python3 -m pytest -q, depuis la racine de la nouvelle copie.
Résultat : 479 passed, aucun échec, aucun test ignoré ou marqué xfail.
Deux avertissements de dépréciation proviennent de Starlette/FastAPI et anyio.
Les versions principales de l'environnement sont enregistrées dans TEST_ENVIRONMENT.json ; ce fichier décrit l'environnement de test, ce n'est pas un lockfile complet.

## Synchronisation

Nouveau snapshot dérivé : Synergesis_portable_479_2026-09-12.zip.
Utiliser une extraction neuve de cette archive et vérifier MANIFEST_SHA256.json.
MANIFEST_UPSTREAM_SHA256.json conserve le manifest de la base, pas celui de la copie corrigée.
PORTABILITY.patch décrit les deux modifications de code de test.
Les anciennes validations historiques conservées dans le snapshot restent des comptes rendus des itérations précédentes.

Cette livraison corrige la portabilité de la validation ; elle n'ajoute pas de fonctionnalité cognitive. Elle ne constitue pas une synchronisation automatique entre conversations.
