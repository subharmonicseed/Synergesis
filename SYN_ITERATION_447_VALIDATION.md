# Synergesis — validation intégrée 447-green

Date : 12 septembre 2026

Point de départ : snapshot canonique 393-green.

## Itérations intégrées

### 1. SYN-RISK-BUDGET

Un budget cumulatif empêche une séquence d'expériences individuellement
acceptables de contourner une limite globale.

Protocole :
- réservation immédiatement avant Planner/AEGIS ;
- libération si aucune action d'exécuteur n'a lieu ;
- consommation dès qu'un exécuteur a réellement été appelé, indépendamment du
  succès fonctionnel ;
- en cas d'exception ambiguë après réservation, aucune libération automatique
  (fail-closed).

Le budget est append-only et hash-chainé.

Important : les montants additionnés sont des **unités de gouvernance de risque**,
pas une probabilité mathématique de dommage cumulée.

### 2. Époques de budget explicites

`RiskBudgetPolicy.epoch_id` sépare les périodes de budget.

- redémarrer avec le même `epoch_id` conserve la consommation ;
- fournir un nouvel `epoch_id` par configuration ouvre un nouveau budget ;
- l'historique des époques précédentes reste intact.

Aucun apprentissage ne peut ouvrir une nouvelle époque.

### 3. Revalidation just-in-time des expériences

Un directive causal préparé est revalidé juste avant exécution.

Si le posterior, le risque appris ou la policy ont changé et que l'intervention
n'est plus approuvée, le directive devient `stale` et est rejeté avant toute
nouvelle action.

### 4. Current World Belief View

`VersionedBeliefView` sépare explicitement :
- historique append-only ;
- tête courante des prédicats versionnés.

Prédicats activés dans la stack :
- `estimated_effect_success_probability`
- `conditional_causal_posterior`

Les prédicats non versionnés conservent leur sémantique multivaluée.

`current` signifie "dernière version enregistrée", pas "vérité".

### 5. SYN-PROVENANCE-TRANSPORT

Transport inter-agent signé avec :
- signature Ed25519 du sender ;
- expiration et skew futur bornés ;
- sender allowlist ;
- chaîne de receipts vérifiée en staging avant persistance ;
- origin authority allowlist ;
- replay ledger append-only et hash-chainé ;
- révocation d'identité prise en compte.

Les claims distants sont toujours matérialisés comme :

`kind = remote_signed_claim`
`channel = remote_transport`
`runtime_local = false`

Même un origin receipt `runtime_attested` explicitement autorisé ne devient
jamais un `runtime_reality_observation` local.

### 6. Universal Perception Bus

Le bus normalise de vrais percepts fournis par des adapters externes sans
prétendre disposer de caméra, microphone ou capteur.

Invariants :
- l'autorité provient uniquement de `PerceptionSourcePolicy` ;
- le payload ne peut jamais choisir/élever son autorité ;
- confiance absente => `None` ;
- déduplication exacte ;
- collision d'external_id avec payload différent => rejet ;
- sources/modalités/adapters absents ou désactivés => rejet ;
- taint configurable à l'ingress.

## Validation

Suite top-level Synergesis :

`447 passed, 0 failed`

Nombre de fichiers de tests top-level :

`53`

Les warnings observés concernent uniquement l'impossibilité d'écrire le cache
pytest dans `/mnt/data`; ils n'affectent pas les résultats.

Aucun TODO/FIXME/NotImplemented/placeholder/dummy exécutable détecté dans les
nouveaux modules ou les fichiers de composition modifiés.

## Invariants consolidés

`Learning != PrivilegeEscalation`

`InformationGain != ExperimentValue != Authority`

`ActionSuccess != NoHarm`

`Learning cannot lower configured safety floors`

`RepeatedSmallRisk cannot bypass cumulative budget`

`BudgetReset requires external epoch configuration`

`PreparedExperiment != EternallyValidExperiment`

`CurrentBelief != HistoricalBelief != Truth`

`RemoteClaim != LocalRuntimeFact`

`PerceptPayload != Authority`

## Limites restantes

- Le budget de risque est un mécanisme de gouvernance additif ; ses unités
  doivent être calibrées par politique, elles ne constituent pas une probabilité
  cumulée universelle.
- Single-writer toujours supposé pour plusieurs ledgers.
- Pas de transaction atomique globale entre Glyph ledger, semantic memory,
  prediction ledger, risk ledger et receipt stores.
- Le Perception Bus ne fournit aucun hardware adapter réel.
- Le transport inter-agent ne remplace ni AEGIS ni les règles locales
  d'autorisation.
- La sélection expérimentale reste conditionnelle aux modèles causaux fournis.
