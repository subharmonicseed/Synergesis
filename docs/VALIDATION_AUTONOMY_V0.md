# Validation du superviseur v0 sur le PC

Vérification du 11 octobre 2026, Ubuntu 24.04 / Python 3.12.3. Base : arbre de la PR #55, conservant le raccordement local et les corrections Mistral. Revue indépendante sans blocage restant après correction des relations du graphe.

## Tests contrôlés

**1 023 tests passent**, deux avertissements de dépréciation de dépendances, en 127,32 secondes. Les 50 nouveaux cas du cœur et 13 cas d’intégration UI utilisent des effets simulés. Ils couvrent notamment la réservation avant appel, les budgets après relance, les contrôles pendant une attente HTTP, le progrès fondé sur les sources, les frontières d’interruption, la reprise depuis les journaux existants et le refus de considérer des octets de transport comme une remise vérifiée. Les assets JavaScript et le diff passent leurs contrôles statiques.

Ces tests ne prouvent pas la qualité du modèle. Les preuves réelles ci-dessous sont distinctes.

## Mission réelle, sans clé API

Modèle déjà installé : `syn-mistral-import:latest`, Mistral 7B Instruct v0.3 Q4_K_M. Aucun modèle téléchargé et aucun fournisseur cloud utilisé. Profil de preuve distinct du profil personnel. Le navigateur de test utilise le moteur Edge existant ; le contrôle Ordinateur de l’onglet personnel était indisponible à cause d’un échec de son runtime sandbox.

Le panneau a autorisé les trois requêtes fixes `quantum gravity`, `loop quantum gravity` et `causal dynamical triangulations`. La mission a terminé **trois recherches arXiv et trois synthèses Mistral**, soit six étapes confirmées, en **428,92 secondes** depuis sa création. Neuf résumés ont été consultés ; le contexte fourni au modèle est borné et n’inclut pas nécessairement tous ces extraits.

L’onglet de test a été fermé à 19:50:46 UTC après le lancement. La pause, demandée ensuite depuis le panneau pendant le premier appel Mistral, a été enregistrée avant sa fin. La réponse de cet appel est arrivée après fermeture de l’onglet. Le serveur a ensuite été arrêté par son bouton et réellement redémarré : nouvel identifiant d’instance, même mission, pause, réservations, reçus et budgets. Après reprise explicite puis fermeture de l’onglet à 19:54:03 UTC, les deux recherches et synthèses restantes ont avancé jusqu’à la fin.

Le journal de transport comporte exactement trois réponses HTTP 200 achevées du modèle installé. Chacun des trois textes correspond exactement au texte de son reçu de remise. Les hashes des neuf extraits conservés ont été recalculés ; les trois cycles de synthèse ont été vérifiés contre les observations de boîte locale, les identifiants de tour et les hashes de texte. Le premier couple de reçus n’a pas été répété après relance.

Les états complets, réponses, URLs, hashes, captures et transport restent locaux sous `outputs/SynSupervisorProofs`. Ils ne sont pas publiés dans cette proposition GitHub. Le rapport local est `outputs/SYN_SUPERVISEUR_RESULTAT_PC.md`.

## Limites observées

La requête large `quantum gravity` a retourné des résumés de pertinence variable. Mistral a produit des synthèses en français parfois maladroites ; la livraison et les citations repérées n’attestent ni vérité scientifique ni amélioration du raisonnement. La preuve porte sur le raccordement, la continuité, les réservations et les résultats réellement obtenus.

L’échéance de dix minutes interdit de nouveaux effets après sa date persistée. Pause et arrêt sont coopératifs : un appel déjà engagé peut encore finir. La v0 ne garantit pas une échéance murale stricte, une exécution extérieure exactement une fois, ni un fonctionnement lorsque Windows/WSL/le serveur sont arrêtés. Un résultat inconnu bloque la mission pour inspection.
