# ChatGPT comme moteur de SYN

## Configuration réellement visée

L'utilisateur converse avec le modèle qu'il a sélectionné dans ChatGPT. Le modèle
interprète la demande, raisonne, critique et utilise les outils autorisés. GitHub
sert de mémoire documentaire externe ; les glyphes natifs relient les sources.
La stack Python locale est un autre instrument expérimental, pas un prérequis
pour ce mode. Aucun abonnement API, lancement de serveur ou modèle Mistral requis.

Le [point d'entrée](../SYN_START_HERE.md) et [STATE.md](chatgpt/STATE.md) donnent
un cadre court, rechargeable après une interruption. Lire les documents pertinents
sur demande au lieu de recopier tout l'historique dans chaque interaction.

## Chemin de lecture vérifiable

1. Obtenir la révision actuelle de `feat/syn-glyph-scene-bridge-v1`.
2. Lire le point d'entrée et l'état à cette révision.
3. Ouvrir `docs/chatgpt/scene.json` : chaque nœud est un `Glyph` du protocole
   existant ; chaque relation est un `GlyphEdge`. Les sources restent des données.
4. Suivre `derived_from` vers les ancrages utiles et charger leurs fichiers.
   Comparer, si disponible, le SHA du blob renvoyé par GitHub à `git_blob_sha`.
   Si la carte est périmée, lire les sources actuelles et signaler la limite.
5. Utiliser les décisions et objections retrouvées dans la réponse actuelle.
   Un simple « contexte chargé » ne prouve pas qu'il a changé la décision.

La projection est générée par `scripts/export_chatgpt_context.py` avec les classes
réelles de SYN, dans un journal temporaire. Elle ne contient aucun profil personnel.
Elle est un instantané documentaire : son historique reste dans Git. Les révisions
du journal privé d'un runtime ne sont pas importées. Régénérer la carte lorsque ses
sources changent ; à défaut, les fichiers actuels font foi et la carte est déclarée périmée.

## Trois demandes différentes

| Demande | Comportement attendu |
| --- | --- |
| Dialogue, évaluation ou correction | Répondre, reprendre le cadrage si nécessaire ; aucune veille déclenchée par défaut. |
| Recherche explicitement demandée ou déclenchement planifié identifié | Consulter l'index, choisir une lacune utile et chercher ce qui pourrait réfuter l'hypothèse. |
| Mise en œuvre explicitement demandée | Réutiliser les outils existants, agir dans le périmètre autorisé, tester puis conserver un reçu. |

Ce sont des règles de conversation adoptées, pas un classifieur de mots-clés validé.
Le dernier message humain peut corriger l'orientation. Un ancien prompt de veille
ne doit pas absorber les questions de l'utilisateur.

## Héritage après un échange

Pour une avancée matérielle, ajouter une entrée publique de continuité donnant :
statut, source, objection, révision et conséquence concrète. Mettre à jour l'état
court sans supprimer les incertitudes pertinentes. Utiliser des écritures avec
vérification de version, puis relire le contenu distant avant d'annoncer une sauvegarde.
Ne pas publier une transcription, un profil ou des informations personnelles.

Dans une conversation disposant seulement du connecteur GitHub, les sources et
l'état restent lisibles et modifiables. L'export Python n'est pas exécuté par la
seule lecture de ces documents. Si aucun outil d'exécution n'est disponible, une
nouvelle décision peut être enregistrée dans les sources ; la projection doit alors
être considérée comme ancienne jusqu'à sa régénération explicite.

## Épreuve avec un vrai modèle

Cette configuration utilise bien le modèle réel de la conversation. Pour mesurer
un avantage, comparer sur des cas réservés le même modèle sans le contexte SYN,
avec un rappel documentaire simple, puis avec le contexte relié par glyphes.
Garder un budget commun, les échecs, la qualité du cadrage, l'utilité de l'objection,
les affirmations non sourcées et le coût. Le jugement de l'utilisateur peut évaluer
l'utilité ; il ne suffit pas à établir la vérité des affirmations scientifiques.

Le présent raccord fournit une reprise lisible et vérifiable. Il ne prouve pas un
gain cognitif, une mémoire exhaustive, une recherche autonome continue ou une
activation des contrôles locaux dans ChatGPT. La configuration d'une éventuelle
tâche planifiée ancienne doit être inspectée séparément ; elle n'est pas modifiée
par la publication de ce document.
