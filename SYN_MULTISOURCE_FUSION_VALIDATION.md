# Synergesis — validation intégrée 479-green

Date : 12 septembre 2026

Point de départ : snapshot canonique 463-green.

## Nouvelle couche : SYN-MULTISOURCE-FUSION

Le module `synergesis_multisource_fusion.py` ajoute une fusion perceptive
multisource qui sépare explicitement cinq notions :

1. nombre de sources ;
2. indépendance des sources ;
3. autorité/provenance ;
4. fiabilité empirique ;
5. vérité.

Aucune de ces notions n'est assimilée à une autre.

## Indépendance

Chaque source appartient à un `independence_group` fourni par configuration de
confiance.

Plusieurs sources du même groupe ne sont jamais additionnées comme des témoins
indépendants.

Si elles soutiennent toutes la même valeur, le groupe contribue seulement le
maximum de leurs fiabilités.

Si elles se contredisent à l'intérieur du même groupe, le groupe devient
`internal_conflict` et contribue zéro support.

Invariant :

`SourceCount != IndependentEvidenceCount`

## Autorité

L'autorité AEGIS de la racine perceptive sert uniquement de filtre
d'éligibilité :

`origin_rank >= minimum_origin_rank`

Elle ne multiplie jamais le poids de vérité.

Invariant :

`Authority != Reliability != Truth`

## Fiabilité

Chaque `FusionSourceProfile` fournit une fiabilité configurée initiale.

Après un nombre minimal d'adjudications de référence, la source peut passer à
une fiabilité empirique Beta-Bernoulli.

Une adjudication est acceptée seulement si :

- elle est un Glyph `perception_reference_adjudication` ;
- elle référence exactement le percept normalisé concerné ;
- elle est reliée par `evaluates` au percept ;
- sa propre origine est liée dans AEGIS ;
- son rang d'origine atteint `minimum_adjudication_origin_rank`.

Une source ne peut donc pas améliorer sa fiabilité par auto-affirmation.

Le ledger de fiabilité est append-only et hash-chainé.

## Support, pas probabilité de vérité

La fusion calcule un support pondéré par groupe indépendant.

Le résultat Glyph porte explicitement :

`authority_semantics = eligibility_only`

`support_semantics = weighted_independent_support_not_truth_probability`

`source_count_is_not_independence = true`

Le moteur peut produire :

- `resolved`
- `unresolved`

Un résultat non résolu conserve :

`selected_claim = None`

Les raisons auditées incluent notamment :

- `support_tie`
- `insufficient_independent_groups`
- `insufficient_support`
- `insufficient_support_margin`
- `no_eligible_independent_support`
- `time_span_exceeds_policy`

## AURA / contexte

Quand AURA est disponible, toute fusion crée une Evidence
`source_type = perception_fusion` reliée au Glyph d'inférence.

Cette Evidence est récupérable par le même contexte borné que l'Agent Loop.

Une fusion résolue ne devient toutefois pas automatiquement un Fact du World
Model :

`ResolvedSupport != CertifiedTruth`

C'est volontaire.

## Fusion non résolue -> ROAM

Si la policy l'autorise, une fusion non résolue crée un `ResearchNeed` avec :

- domaine explicite ;
- template explicite ;
- `AttentionMeasurements` explicitement configurées ;
- provenance vers le Glyph de fusion.

Aucune recherche ne démarre automatiquement.

Un `service.tick_once()` explicite lance ensuite au maximum la session ROAM
bornée prévue par les limites existantes.

## Cas vérifiés

1. Deux sources corrélées du même groupe ne comptent pas comme deux témoins.
2. Deux groupes réellement indépendants et concordants peuvent résoudre une
   fusion.
3. Plusieurs sources faibles ne battent pas automatiquement une source
   indépendante plus fiable.
4. Une source très fiable mais sous le rang d'autorité minimal est inéligible.
5. Une égalité de support reste non résolue.
6. Un conflit interne à un groupe indépendant annule le support du groupe.
7. La fiabilité empirique ne s'apprend qu'après adjudications de référence
   suffisamment autorisées.
8. Une adjudication faible ou non reliée ne peut pas entraîner le modèle.
9. La fiabilité empirique peut modifier le résultat de fusion sans modifier
   l'autorité de la source.
10. Des percepts trop éloignés temporellement ne sont pas fusionnés comme une
    même scène.
11. Le ledger de fiabilité détecte l'altération.
12. Les paramètres numériques ambigus/invalides sont rejetés.
13. La stack complète crée une Evidence de fusion utilisable par le contexte.
14. Une fusion non résolue crée un ResearchNeed puis un tick ROAM borné.
15. Une configuration de fusion partielle est refusée au démarrage.

## Validation

Suite top-level Synergesis :

`479 passed, 0 failed`

Nombre de fichiers de tests top-level :

`55`

Le warning pytest observé concerne uniquement le cache `/mnt/data/.pytest_cache`
non-écrivable et n'affecte pas les tests.

## Invariants consolidés

`Percept != Fact`

`SourceCount != IndependentEvidenceCount`

`Authority != Reliability != Truth`

`ConfiguredReliability != EmpiricalReliability`

`Support != ProbabilityTrue`

`ResolvedFusion != CertifiedTruth`

`UnresolvedFusion -> NoForcedClaim`

`UnresolvedFusion -> ResearchNeed, not automatic research`

`LearningReliability -> NoAuthorityElevation`

## Limites restantes

- Les groupes d'indépendance sont configurés statiquement ; Syn ne déduit pas
  encore elle-même les dépendances entre capteurs.
- Le modèle de fiabilité suppose des adjudications binaires correct/incorrect ;
  il ne modélise pas encore les erreurs continues ou dépendantes du régime.
- Le support pondéré n'est pas un modèle probabiliste de vérité.
- Une fusion résolue reste Evidence ; son admission comme croyance du World
  Model devra conserver explicitement cette distinction.
- Les adapters matériels réels restent externes.
- Les ledgers restent single-writer et sans transaction atomique globale.
