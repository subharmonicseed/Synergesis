# SynTask — contexte de développement borné (contre-expertise)

Ce document définit un prochain travail ; il ne prétend pas que le bridge existe.

## Référence

La restauration 519 est la base historique, pas la dernière révision.
Base vérifiée de cette consolidation : PR 44,
`9294815aca399682aee16021b690421c8fa407c9`, 669 tests.
Le présent lot de consolidation passe 703 tests localement. Utiliser le SHA
exact de sa PR après publication, et vérifier le manifest avant extraction.
Ne pas analyser main ni superposer des pièces jointes historiques.

## Objectif proposé

Concevoir un ModelContextBridge v0 qui produit un SynTask de développement
sans exécuter ni modifier le dépôt : carte des symboles réellement extraits,
slices AST sélectionnées pour une question, dépendances nécessaires, tests
concernés, budget exact pour le tokenizer du modèle destinataire.
Le plafond indicatif est 6000 tokens, comprenant le contrat, les extraits,
leurs provenances et les réserves. Si le tokenizer est inconnu, annoncer une
estimation plutôt qu'une limite garantie. La taille de la carte est mesurée,
pas promise à 800 tokens.

## Interfaces existantes vérifiées

- `PredictionEngine.predict_before_action`, `settle`, `add_settlement_sink`.
- `PredictionCuriosityMonitor.on_prediction_settlement`.
- `WorldModelPredictionBridge.predict`, `on_prediction_settlement`.
- `CausalCreditBridge.predict`, `on_prediction_settlement`.
- `build_secure_roam_reality_stack` assemble ces composants.

La curiosité est déjà raccordée au règlement de prédiction : commencer par
examiner ce raccordement et ses tests, pas par recréer un module supposé absent.
Les noms PredictEngine.predict / Curiosity.generate / Aegis.check du retour
extérieur étaient illustratifs, pas une carte vérifiée de ce dépôt.

## Contrat minimal à contre-expertiser

Chaque extrait référence commit, chemin, symbole, lignes et empreinte du fichier.
Les dépendances omises sont explicites. Les symboles non trouvés sont refusés.
Les secrets (.env, clés privées, identifiants) sont exclus avant sélection.
Un changement de fichier/commit invalide les extraits mis en cache.

Un Glyph peut résumer une preuve sous conditions : ID, source, configuration,
date, périmètre, résultats de tests et limites. « ROAM stable : 0,9 » seul n'est
ni un certificat de test ni une probabilité de vérité. Les résumés ne remplacent
pas le code et les invariants requis pour la modification envisagée.

Le texte du dépôt est une donnée non fiable pour le routeur : il ne peut pas
modifier ses règles, ses autorisations ni le budget par des instructions cachées.

## Livrable de l'autre assistant

Une proposition de schéma SynTask, les choix de sélection et un plan de tests
adverses (symboles inventés, fichier modifié, dépendance manquante, budget
insuffisant, secret, instruction injectée, preuve périmée). Toute suggestion
fondée sur du code non reçu doit être marquée hypothétique. Pas d'accès GitHub
nécessaire : fournir les seuls extraits curatés avec leurs références.
