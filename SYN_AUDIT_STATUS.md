# Audit consolidé — 28 septembre 2026

Base : PR 44 / `9294815aca399682aee16021b690421c8fa407c9`.
Cinq lots confiés à des sous-agents légers, avec revue et corrections centrales.
Trois lots ont nécessité une seconde revue ciblée. **703 tests passent localement**
(CPython 3.12.14, dépendances existantes, 2 avertissements, 16,66 secondes).
La CI est contrôlée séparément ; ce nombre ne prouve pas une autonomie complète.

« Traité » signifie le périmètre ci-dessous, pas une garantie universelle.

| ID | État | Résultat / limite vérifiable |
|---|---|---|
| SEC-01 | Traité | En-têtes et sessions d'authentification protégés lors des redirections ; tests HTTP. |
| SEC-02 | Traité | Réponses lues avec limite de taille ; tests HTTP. |
| SEC-03 | Traité, coopératif | Retry-After et budgets bornés ; pas de garantie de délai dur contre tout blocage OS/transport. |
| SEC-04 | Traité | Modes exact/path signés ; préfixe lexical historique conservé et explicite. |
| SEC-05 | Traité | Réservations de budget sérialisées ; tests multiprocessus existants. |
| SEC-06 | Partiel | ProcessMarkerProbe prouve une présence ; il ne prouve pas que l'action a créé le processus. |
| SEC-07 | Traité | Deadline SQLite via progress handler ; timeout renvoyé comme inconnu. |
| SEC-08 | Traité sous POSIX | Ouverture par descripteurs sans suivi de liens ; ancêtres de la racine de confiance hors menace. |
| SEC-09 | Traité | Même event_id/corps différent refusé ; contrôle/création dans la transaction du journal. |
| COG-01 | Traité, borné | Settlement idempotent ; transmission incertaine bloquée, pas de promesse exactly-once externe. |
| COG-02 | Traité | Prédictions en attente récupérables avec leurs références d'action. |
| COG-03 | Traité | Identité et cohérence du verdict vérifiées avant apprentissage. |
| COG-04 | Traité | Réparation agenda/graphe après interruption ; traces ambiguës signalées. |
| COG-05 | Traité, borné | Reçu terminé réconcilié ; recherche de résultat inconnu bloquée pour examen. |
| COG-06 | Traité, borné | Contrat d'origine conservé et liens réparés ; ancien contrat inconnu non inventé. |
| COG-07 | Traité, opt-in | Horloge explicite, détection futur/périmé ; relecture historique sans horloge inchangée. |
| COG-08 | Traité | Expiration inclusive ; un conflit simultané suspendu reste suspendu. |
| COG-09 | Traité pour nouveaux reçus | Empreintes de configuration fusion/ROAM ; pas d'empreinte de toute implémentation externe. |
| OPS-01 | Traité | Paquet, dépendances cœur/test ; extras runners pour les tracés. |
| OPS-02 | Conversation préparée | Démonstration hors réseau et adaptateur de conversation texte ; essai API réel restant. |
| OPS-03 | Traité | CI 3.11/3.12, manifest vérifié et reçus de tests/environnement archivés par commit. |
| OPS-04 | Traité | Prototype retiré de l'API installée et téléchargement implicite supprimé. |
| OPS-05 | Traité | Scripts sans suppression automatique, dossier neuf, corpus explicite, imports sans exécution. |
| OPS-06 | Partiel | Session gérée mono-écrivain pendant toute sa durée ; les API bas niveau et stockages externes peuvent la contourner. |
| OPS-07 | Partiel | Glyph : 1 Mio/événement et 64 Mio/journal par défaut, refus sans troncature ; diagnostic borné. Pas de quota universel sur chaque ancien journal. |
| OPS-08 | Partiel | Diagnostic structurel sans contenu sensible et références existantes ; pas encore de console globale de corrélation. |
| OPS-09 | Revue préparée | Inventaire exact des chemins absents, archive legacy conservée ; remplacement de main non effectué. |
| OPS-10 | Traité | Identités de fusion v2/configuration explicites ; historique v1 non réécrit et conséquences de rejeu documentées. |
| OPS-11 | Préparé, non exercé en ligne | Commande arXiv bornée et optionnelle ; aucune validation Internet réelle revendiquée. |

## Base historique

`main` reste au commit `99a9b959036524552be2fd796f9a8f927ac91549`.
L'archive `archive/legacy-main-2025` conserve cette référence. L'inventaire
`LEGACY_RESTORATION_INVENTORY.json` décrit les 1407 chemins de ce main absents de
la base PR44 ; les 1629 éléments d'arbre incluent aussi des répertoires, ce n'est
pas un compte de fichiers. Les anciens modules/applications ne sont pas tous
certifiés équivalents aux modules modernes. Les archives conservent également
les éventuels secrets de l'histoire : archiver n'est pas assainir.

## Blocages de livraison autonome

Les secrets signalés dans l'ancien dépôt doivent être révoqués dans leurs
services ; ni une suppression de fichier ni un force-push ne révoquent une clé.
Aucune purge d'historique ou utilisation de ces identifiants n'est effectuée ici.
La nouvelle règle .gitignore est préventive uniquement.

Le dialogue texte dispose maintenant d'un adaptateur API et d'un lancement
décrits dans `PREMIERE_CONVERSATION.md`. Il reste à valider avec une clé
neuve fournie par l'opérateur hors dépôt. Les imports partiels incertains
requièrent encore une revue opérateur. Le remplacement de main et la parité des
applications legacy restent une décision de livraison distincte.

Le ModelContextBridge v0 est livré dans la PR #46 et décrit dans
`SYN_MODEL_CONTEXT_BRIDGE.md` ; son comptage par défaut reste estimatif.
