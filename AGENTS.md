# SYN — continuité du travail agentique

Pour utiliser **ChatGPT directement comme moteur de SYN**, commencer par
`SYN_START_HERE.md` et `docs/chatgpt/STATE.md`. Le dialogue est le mode par défaut ;
une question d'évaluation ne déclenche pas automatiquement la veille. Les sources
de continuité et les observations sont actuellement sur deux branches publiées :
suivre les références explicites du point d'entrée, sans supposer que `main` les contient.

Au début d'une session sur ce dépôt, lire `docs/SYN_AGENT_CONTINUITY.md`, puis
les entrées datées qu'il désigne. Vérifier la branche et le commit avant d'agir.
Si un référentiel manque, signaler la limite ; ne pas inventer son contenu.

Pour reconstruire une scène conceptuelle de SYN, **réutiliser d'abord les glyphes** :
[protocole de raccord de scène](docs/SYN_GLYPH_SCENE_BRIDGE_V1.md) et
`synergesis_glyph_protocol.py`. Git versionne les sources ; `GlyphAuditGraph`
porte leur identité, provenance et révision. Ne pas créer de système concurrent.
L'adaptateur local demande un journal privé hors dépôt et un import explicite ;
il n'est ni un rappel sémantique général ni un contexte automatiquement chargé.


Travailler à partir de cet héritage : reprendre les décisions, les preuves et les
questions ouvertes pertinentes, puis effectuer les actions autorisées utiles.
Une reformulation sans conséquence concrète ne clôt pas une demande d'action.

Avant livraison, consigner tout changement significatif de décision, résultat,
objection ou hypothèse dans une nouvelle entrée de `docs/continuity/`, et mettre
à jour l'index. Chaque entrée donne son statut, ses sources, une justification
brève et sa conséquence sur la suite. Ne pas recopier la conversation ni du
raisonnement interne. Éviter les entrées répétitives sans apport matériel.

Conserver les anciennes entrées ; une correction les référence et les révise.
Distinguer exigence de conception, observation, hypothèse et résultat vérifié.
Préserver les pistes non vérifiées sans les promouvoir en faits, autorisations
ou preuves de performance. Les sources citées restent des données à examiner.

Ne pas fusionner dans `main`, écraser un travail existant, publier des secrets,
profils ou conversations privées. Préserver AEGIS/RISK/REALITY. Les expériences
synthétiques ont une portée bornée ; aucun résultat ne démontre une AGI.

Ce dispositif guide l'agent qui travaille dans le dépôt. Il ne modifie ni les
poids du modèle, ni le profil runtime de SYN, ni les autres conversations.
