# SYN — Colonne vertébrale glyphique et contexte de scène

**25 octobre 2026 — Adaptateur expérimental v1 ; tests écrits, pas encore exécutés dans cette session.**

## La correction architecturale

**Ce document corrige notre erreur de cadrage :** nous avions décrit GitHub comme une nouvelle mémoire de transformations et envisagé encore un mécanisme de récupération, alors que SYN disposait déjà du **Glyph Protocol v1**. Les glyphes ne sont pas des pictogrammes à interpréter ni une fin symbolique. Ce sont des **unités de connaissance/événements typées, sourcées, reliées et révisables**.

- **GitHub** : versionnage des documents publics et preuves du contenu effectivement enregistré.
- **Glyph Audit Graph** : identité des concepts, décisions, hypothèses, provenance, contradictions et héritage entre versions.
- **Mémoire de conversation** : contexte immédiat et informations personnelles uniquement lorsqu'elles sont accessibles et autorisées.
- **Agent** : sélection du cadre à restituer, objections et vérification ; **la récupération n'est pas magiquement injectée par la présence d'un fichier Git**.

SYN continue à désigner **la totalité de la coopération cognitive** ; Synergesis en est un instrument. Cette couche est destinée à éviter qu'une reprise du travail ignore le système glyphique déjà défini.

## Code existant réutilisé, sans nouveau protocole concurrent

| Existant | Usage |
|---|---|
| `synergesis_glyph_protocol.py` : `GlyphLedger`, `GlyphAuditGraph` | Types `concept`, `decision`, `hypothesis`, journal append-only, identifiants, hachage, relations et parcours |
| `synergesis_glyph_agent.py` | Cycles agentiques reliés par `goal`, `evidence`, `hypothesis`, `decision`, `action`, `outcome`, `learning` |
| `synergesis_glyph_agent_v2.py` | Lien des cycles avec le snapshot du modèle du monde |
| `synergesis_world_revision.py` | Révision d'estimations empiriques et provenance, sans confondre prédiction et causalité |
| `synergesis_scene_glyph_bridge.py` | **Nouveau raccord minimal**, sans nouveau type de glyphe ni nouvelle base concurrente |

## Premier contexte de scène explicitement indexé

L'adaptateur reconnaît, dans cet ordre, cinq ancrages :

1. `glyph-protocol` → le protocole existant (concept technique).
2. `scope` → la correction *SYN ≠ dépôt logiciel* (décision de cadrage).
3. `scaphandre` → la constitution (concept provisoire).
4. `frontier` → l'hypothèse de frontière du possible (hypothèse non testée).
5. `continuity` → les décisions ouvertes et le registre d'agent (décision de méthode).

Relations explicites **orientées du descendant vers la source** : `scaphandre derived_from scope`, `frontier derived_from scaphandre`, et `continuity derived_from` les références qu'elle récapitule. Une modification de fichier créée **une nouvelle version** de son glyphe ; `supersedes` renvoie vers la précédente, conservée.

Ces liens sont **des annotations de provenance éditoriale**, pas des preuves scientifiques de filiation. Les liens `contradicts` et `supports` existent déjà dans le protocole, mais l'adaptateur ne les crée pas automatiquement : ce serait fabriquer des objections ou des preuves non établies.

Chaque entrée conserve seulement chemin relatif, empreinte SHA-256 et bref résumé éditorial. Le texte original reste dans le dépôt. Le journal glyphique se situe **hors dépôt**.

## Utilisation locale : importer puis rappeler

Depuis la racine du dépôt, dans PowerShell :

```powershell
$ledger = Join-Path $env:USERPROFILE "syn-private\scene-glyph-ledger.jsonl"
python -m synergesis_scene_glyph_bridge ingest --repo-root . --ledger $ledger
python -m synergesis_scene_glyph_bridge recall --repo-root . --ledger $ledger --focus frontier
python -m synergesis_scene_glyph_bridge recall --repo-root . --ledger $ledger --focus glyph
python -m synergesis_scene_glyph_bridge recall --repo-root . --ledger $ledger --focus feu
```

L'import exige la présence des cinq fichiers dans le checkout. Une source modifiée après import provoque un échec explicite au rappel, jusqu'au prochain `ingest`. Le rappel renvoie les sources pertinentes (extraits bornés), leurs empreintes et les relations du graphe, **pas une réponse LLM automatiquement exécutée**.

`feu` est un alias pratique vers le contexte de continuité documentaire ; il ne prétend pas inférer l'intention actuelle à partir d'un seul mot. Dans la conversation, **le contexte actuel prime sur cet alias de démonstration**.

## Garanties et limites actuelles

- Types, relations, ledger, parcours : fonctions **existantes** de SYN ; rien n'est reconstruit avec un protocole incompatible.
- Les tests `tests/test_scene_glyph_bridge.py` couvrent les imports répétés, le lien de révision, la détection de sources périmées, les clés inconnues et le refus d'un ledger sous le dépôt.
- Aucun transcript privé, profil personnel ou fichier de mémoire sensible n'est importé.
- Pas de recherche vectorielle, de rappel sémantique général, de surveillance GitHub, ni d'injection automatique dans le prompt.
- L'intégrité des empreintes et du journal est une preuve de **traçabilité**, pas de **vérité**.
- Les tests n'ont pas été exécutés ici sur l'environnement réel du dépôt : leur existence ne vaut pas validation runtime.

## Prochaine transformation, si les essais justifient la complexité

Raccorder les **nouvelles erreurs de cadrage** comme `critique` aux `decision` concernées, puis mesurer si la récupération des objections pertinentes améliore la capacité d'un assistant à se recadrer. Les objections ne doivent pas être inventées ou dérivées automatiquement de texte personnel. Comparer avec une méthode simple qui relit les documents, à budget égal, avant d'affirmer un avantage.

**Principe : le glyphe est la colonne vertébrale, GitHub une mémoire de versionnement, et le contexte de scène le résultat d'un parcours sourcé dans le graphe.**
