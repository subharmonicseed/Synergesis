# Synergesis — validation intégrée 463-green

Date : 12 septembre 2026

Point de départ : snapshot canonique 447-green.

## Nouvelle jonction : Perception -> Evidence -> World Model -> Context -> ROAM

Le nouveau module `synergesis_perception_knowledge.py` raccorde le Universal
Perception Bus aux couches cognitives sans transformer automatiquement une
observation en vérité.

### Admission staged

Chaque percept normalisé devient d'abord une Evidence auditable.

Une règle `PerceptionKnowledgeRule` doit explicitement définir :

- `observation_kind`
- `domain`
- champ sujet
- prédicat du World Model
- champ objet
- caractère versionné ou non
- autorisation ou non d'admission en mémoire
- seuil minimal de confiance
- sémantique du changement (`state_update` ou `contradiction`)
- éventuelle question ROAM et mesures d'attention explicites

Une confiance absente reste absente :

`confidence = None -> no World Model commit`

Une confiance sous le seuil reste Evidence seulement.

### Temporalité des états versionnés

Pour un prédicat versionné :

- un percept plus récent peut devenir le nouveau head ;
- un changement `state_update` supersède sans inventer une contradiction ;
- un changement `contradiction` crée explicitement un CritiqueGlyph ;
- un percept plus ancien devient `stale_observation` et ne remplace jamais le
  head courant ;
- deux valeurs incompatibles au même timestamp deviennent
  `simultaneous_conflict` et aucune des deux n'est choisie silencieusement
  comme nouvelle tête.

Les nouvelles versions sont reliées aux anciennes par `supersedes`.

### Provenance

Chaîne :

`RawPercept -> NormalizedPerception -> Evidence -> Fact`

Les EvidenceGlyphs sont `derived_from` le percept normalisé et `support` le
FactGlyph admis.

Une contradiction conserve les Glyphs anciens et nouveaux et utilise la relation
`contradicts` vers les faits antérieurs.

### Current World Model + contexte

Les prédicats versionnés déclarés par les règles de perception sont ajoutés à
`VersionedBeliefView`.

Le même `LexicalContextSelector` borné est partagé par l'Agent Loop et le pont
perceptif.

Le contexte peut donc récupérer :

- uniquement le head courant pour les prédicats versionnés ;
- les autres faits non versionnés selon leur sémantique historique ;
- les Evidence issues de la perception et de la recherche ;

sans injecter tout l'historique dans le contexte.

### Contradiction -> ROAM

Une contradiction ne lance aucune recherche par elle-même.

Si la policy l'autorise, elle crée un `ResearchNeed` avec :

- domaine explicite ;
- template de question explicite ;
- `AttentionMeasurements` explicitement configurées ;
- provenance vers le CritiqueGlyph et l'EvidenceGlyph.

Un tick explicite de `SynRoamService` peut ensuite lancer au maximum la session
bornée prévue par les limites existantes.

Cas d'intégration validé :

`Perception`
`-> contradiction`
`-> pending ResearchNeed`
`-> explicit service.tick_once()`
`-> one bounded ROAM session`
`-> new Evidence`

## Invariants ajoutés

`Percept != Fact`

`ConfidenceUnavailable != 0.5 != 1.0`

`TemporalChange != Contradiction unless policy says so`

`StalePercept != CurrentWorldHead`

`SimultaneousConflict -> No silent head selection`

`Contradiction -> ResearchNeed, not automatic research execution`

`PerceptionResearchNeed -> bounded explicit ROAM tick`

`Context uses current versioned heads, not stale history`

## Validation

Tests ciblés perception / stack :

`34 passed`

Suite top-level Synergesis :

`463 passed, 0 failed`

Nombre de fichiers de tests top-level :

`54`

Le seul warning pytest observé concerne le cache `/mnt/data/.pytest_cache`
non-écrivable et n'affecte pas les tests.

Aucun TODO/FIXME/NotImplemented/placeholder/dummy exécutable détecté dans les
modules modifiés.

## Limites restantes

- Aucun adapter matériel réel n'est fourni : caméra, microphone et capteurs
  restent des dépendances externes.
- `PerceptionKnowledgeRule` est une policy statique de gouvernance ; Syn ne peut
  pas modifier seule les seuils ou la sémantique de contradiction.
- La validation d'une contradiction dépend encore du schéma de faits fourni
  par l'adapter et de la policy.
- Le contexte reste lexical BM25-style, pas vectoriel/embedding.
- Les ledgers principaux supposent encore un modèle single-writer.
- Il n'existe toujours pas de transaction atomique globale multi-ledger.
