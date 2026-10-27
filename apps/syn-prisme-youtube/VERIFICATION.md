# Vérification du prototype — 27 octobre 2026

## Réalisé

- Syntaxe JavaScript vérifiée pour les cinq scripts de l’extension.
- 10 tests Node passent : réglage des thèmes et du classement, correction réversible, bonus de nouvelles chaînes, identification des URL, limites de conservation, dénominateur des statistiques, concurrence des observations entre onglets, refus des origines étrangères, confidentialité du code de raccordement, pause, cache et effacement.
- 4 tests Python passent : bornes des entrées, rejet d’une réponse IA malformée, séparation instructions/données dans le format OpenAI et option store=false, authentification/origines/limite horaire avec un vrai serveur HTTP local et une inférence simulée.
- Aucun appel facturé, aucune clé réelle utilisée.

## Non vérifié

- Rendu et activation dans un vrai Chrome : le navigateur de test n’était pas disponible et son téléchargement a échoué dans cet environnement.
- Extraction sur une vraie session YouTube, y compris les variantes de mise en page et les transcriptions.
- Réponse effective d’Ollama ou d’OpenAI, disponibilité d’un modèle et qualité de ses analyses. Les réponses IA sont simulées dans les tests.
- Résistance réelle du modèle aux instructions malveillantes : la séparation des champs est testée, pas l’obéissance d’un modèle réel.
- Instagram, télévision, mobile, Firefox, temps de visionnage : hors périmètre.

## Reproduire les tests

Depuis le dossier du paquet :

```sh
node --test tests/*.cjs
python -m unittest discover -s tests -v
```

## Premier essai sur le vrai navigateur

1. Charger extension/ puis ouvrir YouTube : présence d’un seul panneau SYN.
2. Changer un mot-clé, vérifier le nouveau classement et les raisons sous les titres.
3. Utiliser Pour moi, Moins puis Annuler ; vérifier que chaque action modifie la sélection.
4. Faire défiler et changer de vidéo sans recharger : vérifier les cartes et le titre courant.
5. Mettre en pause : absence de nouvelles observations et d’appels IA.
6. Tester un relais sans modèle disponible : message d’erreur explicite, tri local conservé.
7. Avec un moteur configuré, ouvrir une vidéo et vérifier que le résultat décrit bien la base lue. Sans transcription, il doit le dire.
8. Exporter puis effacer les traces, en mettant en pause avant l’effacement si l’on veut conserver un historique vide.

Le lanceur Windows a été relu mais non exécuté dans cet environnement Linux. Aucun poste utilisateur n’a été modifié. Les thèmes par défaut du module public sont vides.
