# SYN — référentiel de continuité agentique

État révisable du travail, commencé le 25 octobre 2026 (Europe/Paris).
Point d'entrée : [AGENTS.md](../AGENTS.md). Historique :
[2026-10-27-005 — Prisme YouTube, prototype et limite de déploiement](continuity/2026-10-27-005.md).
[2026-10-26-004 — ChatGPT moteur et reprise entre branches](continuity/2026-10-26-004.md).
[2026-10-25-001 — transmission des décisions et incertitudes](continuity/2026-10-25-001.md).
[2026-10-25-002 — SYN au-delà du logiciel, frontière du possible](continuity/2026-10-25-002.md).
[2026-10-25-003 — retour à la colonne vertébrale glyphique](continuity/2026-10-25-003.md).

## Décisions actives

**D008 — mode ChatGPT adopté pour le prochain test** : utiliser directement le
modèle choisi dans la conversation, charger [l'état court](chatgpt/STATE.md) et
suivre [le point d'entrée](../SYN_START_HERE.md). Le mode ordinaire est le dialogue.
La veille est un déclenchement distinct. Ne pas imposer un modèle local pour ce mode.

| ID | Statut | Conséquence pour le travail |
| --- | --- | --- |
| D001 | Exigence de conception adoptée | Agir dans le périmètre autorisé, vérifier les effets et laisser un état réutilisable avant livraison. Une idée qui change la suite doit être enregistrée. |
| D002 | Décision de méthode | Conserver aussi les objections et incertitudes, avec leur statut. Une hypothèse héritée peut orienter un essai ; elle ne devient pas une preuve par répétition. |
| D003 | Décision d'intégration | Utiliser ce référentiel pour le travail de l'agent ; réutiliser les mécanismes scientifiques existants lorsqu'un besoin répond réellement à leur contrat. |
| H001 | Hypothèse ouverte, non testée | Transmettre une objection structurée pourrait changer utilement la prochaine expérience choisie. Aucun gain n'est encore mesuré pour cet effet. |
| C001 | Correction de portée | SYN possède déjà mémoire explicite et questions persistantes. La nouveauté ici est le point d'entrée du travail agentique, pas l'invention de toute continuité dans SYN. |
| D004 | Cadrage conceptuel adopté | **SYN = ensemble de la coopération cognitive ; Synergesis = instrument**. Ne pas réduire une demande conceptuelle à une tâche de codage. Voir [constitution](SYN_SCAPHANDRE_ONTOLOGIQUE_V1.md). |
| D005 | Exigence épistémique | Préserver intention, altérité et réalité sans confondre beauté, nouveauté et preuve. |
| D006 | Protection de la vie privée | Ne pas publier dans GitHub de profils, conversations ni informations personnelles non autorisées. |
| H002 | Hypothèse non testée | La curiosité transformationnelle pourrait identifier des actions rendues nouvellement possibles. Pré-enregistrement dans [frontière du possible](SYN_FRONTIERE_DU_POSSIBLE_V1.md). Aucun gain encore démontré. |
| D007 | Correction d'architecture | La mémoire de transformation repose sur les **glyphes déjà existants** ; Git conserve les sources versionnées. Voir [raccord de scène](SYN_GLYPH_SCENE_BRIDGE_V1.md). Code présent, tests non exécutés ici. |

## État expérimental à conserver

Sur la base de code `20f7bfd0da4b1e5bb5285cc03b6e9d59682afcf4` :

- [Essai historique à quatre variations de prompts](SYN_FOUR_ARM_PC_TRIAL_2026-10-25.md) :
  24 appels locaux réels, six tâches synthétiques réservées ; chaque bras 2/6.
  Aucun gain observé dans cet essai.
- [Deux essais de routage récursif](SYN_RECURSIVE_RESULTS_2026-10-25.md) :
  11/36 pour reset, 9/36 pour journal, 34/36 pour SYN1, 36/36 pour SYN2.
  Les choix parmi des outils fixés évoluent ; les poids du modèle restent fixes.
- Ces résultats distincts ne sont ni une mesure générale de SYN ni une preuve
  d'intelligence générale. Leurs limites et résultats négatifs restent attachés.
- Les preuves détaillées ont été conservées localement lors de ces essais.
  Leur présence dans une autre session doit être vérifiée ; les résumés publics
  ne remplacent pas les reçus absents.

## Reprendre efficacement

1. Lire cet index et les entrées pertinentes ; vérifier l'état Git courant.
2. Identifier ce que l'héritage change dans l'action envisagée. Pour H001,
   examiner d'abord les mémoires et agendas existants, avant de créer un module.
3. Accomplir le travail autorisé, avec des contrôles proportionnés.
4. Enregistrer l'apport matériel et les preuves ; conserver la question ouverte
   si la vérification ne permet pas de conclure. Mettre à jour cet index.

Pour poursuivre H001, l'essai envisagé comparerait un héritage de résultats seul
au même héritage accompagné d'une objection non résolue, avec budget commun et
critère annoncé avant exécution : changement justifié de l'expérience choisie,
puis utilité constatée. C'est une piste à préciser, pas un essai exécuté ni une
mission permanente ou un nouveau budget autorisé.

## Rappel glyphique de scène (premier raccord)

Un adaptateur borné réutilise le `GlyphLedger`/`GlyphAuditGraph` existant : `synergesis_scene_glyph_bridge.py`. Lire [la procédure](SYN_GLYPH_SCENE_BRIDGE_V1.md) avant toute proposition de « nouvelle mémoire ». Les ancêtres du glyphe `frontier` ramènent à `scaphandre`, puis `scope`; les révisions conservent leurs liens `supersedes`.

**Ce raccord n'est pas un index sémantique exhaustif, n'injecte pas automatiquement la mémoire dans le chat et n'est pas revendiqué comme testé sur le runtime local.** Le ledger privé reste hors dépôt.

## Réouverture conceptuelle prioritaire

Avant d'ajouter un nouveau module de curiosité, examiner D004/H002 et le [protocole](SYN_FRONTIERE_DU_POSSIBLE_V1.md) : distinguer possibilités seulement imaginées et nouvelles opérations vérifiées. Conserver les essais négatifs, traiter « feu » selon le travail en cours et vérifier les autorisations. La présence de ces directives dans un fichier ne garantit pas leur chargement dans toutes les sessions ni l'amélioration du modèle.

## Portée de la persistance

Les fichiers Git sont la mémoire externe vérifiable. `AGENTS.md` demande leur
lecture au démarrage d'un agent qui charge ce dépôt. Le chargement des instructions
dépend de l'application et du dossier de travail ; ailleurs, fournir explicitement
ce référentiel. La [documentation officielle sur AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
décrit ce mécanisme. Les fichiers référencés ne sont pas tous injectés automatiquement.

Aucun nouveau branchement vers le profil personnel, CuriosityJournal,
ResearchAgenda ou le ModelContextBridge n'est revendiqué ici. Ce dernier extrait
des symboles Python ; il ne charge pas ce Markdown comme mémoire runtime.

Pour une nouvelle entrée, noter : identifiant et date ; type et statut ; contenu
utile ; source publique ou fichier de code ; justification résumée ; effet sur le
travail ; résultat de vérification ou question ouverte ; entrée révisée éventuelle.
Garder ce registre public impersonnel. Les nouvelles informations privées restent
locales tant que leur publication n'est pas explicitement autorisée.
