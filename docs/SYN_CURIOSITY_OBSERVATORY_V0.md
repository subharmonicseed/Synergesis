# SYN-CURIOSITY v0 — observatoire du non-savoir

**État : proposition persistante inspectable, sans pouvoir de recherche supplémentaire.**
Ce composant prolonge la branche `feat/autonomy-supervisor-v0` (PR #56)
sans modifier l'autorité du superviseur, ses budgets, AEGIS/RISK/REALITY,
ni créer de navigateur, de modèle, de thread ou de scheduler.

## Deux niveaux, un format commun

1. **Veille ChatGPT planifiée.** À chaque exécution, formuler au plus trois
   questions, consulter des sources datées, confronter des contre-arguments,
   et produire un compte rendu. Les notes sont des *évaluations provisoires*,
   pas des faits intégrés à la mémoire de SYN.
2. **Moteur local SYN-CURIOSITY.** Les besoins déjà produits par
   `ResearchAgenda` et `PredictionCuriosityMonitor` sont classés par
   `score_attention` selon quatre signaux fournis explicitement :
   incertitude, impact attendu, ancienneté et manque de nouveauté.
   `CuriosityObserver.propose()` enregistre au plus trois propositions
   sans effectuer d'appel extérieur. Le moteur n'ajoute aucune autorisation
   à `SynRoam` ou au superviseur scientifique : seules les recherches déjà
   autorisées séparément peuvent s'exécuter.

Le journal local reste sous le profil privé de SYN (ex. `<profil>/curiosity.jsonl`).
Une entrée publique provenant de ChatGPT peut être importée explicitement,
via `CuriosityJournal.import_report(path)`, sans accès réseau et sans
transformation automatique en mémoire sémantique.

## Contrat commun (`syn-curiosity-v1`)

Chaque entrée JSON comprend exactement :

- `schema`, `entry_id`, `observed_at` (ISO avec fuseau),
  `producer` (`syn` ou `chatgpt`), `stage`
  (`proposed`, `assessed`, `blocked`).
- `domain`, `question`, `reason`, `hypothesis`, `need_id`.
- `research_mode` (`directed`, `emergent`, `adversarial`,
  `unclassified`) ; `gap_kind` (`prediction_error`, `contradiction`,
  `staleness`, `missing_domain`, `unverified`, `unknown`).
- `metrics` : `uncertainty`, `expected_impact`, `staleness`,
  `novelty_gap`, `selection_score`, tous bornés entre 0 et 1.
- `evidence_refs` : au plus dix URL HTTPS, `outcome`
  (`not_tested`, `supported`, `refuted`, `inconclusive`),
  `uncertainty_after` (0 à 1 ou `null`), `learning` (texte ou `null`).

Une proposition exige `outcome=not_tested`, `uncertainty_after=null`,
aucune preuve. Une évaluation exige des références, un résultat explicite
et une incertitude postérieure : ce sont des **appréciations**, jamais une
certification de vérité par le programme.

`entry_id` est une clé d'idempotence. Une répétition identique est neutre,
mais un contenu différent pour la même clé est rejeté. Le journal JSONL
utilise une chaîne SHA-256 et une transaction locale POSIX. Ce n'est pas une
signature cryptographique, ni une protection contre un adversaire disposant
de l'accès en écriture intégral. Les limites sont 2 048 entrées, 16 Mio
pour le journal et 16 Kio par entrée. Toute archive est manuelle.

## Métriques expérimentales, sans fausse précision

- **Pertinence** : `selection_score`, calculé depuis les quatre signaux
  configurés de `ResearchAgenda`, pas depuis une intuition inventée.
- **Lacunes** : `gap_kind` explicite, avec `unknown` par défaut.
- **Progrès** : diminution *signée* de l'incertitude entre proposition
  et évaluation ; une valeur négative est admise.
- **Contradiction** : nombre de conclusions marquées `refuted`.
- **Calibration** : exploiter séparément les Brier scores provenant de
  `PredictionLedger` lorsqu'il y a des prédictions vérifiées. Ne pas
  calculer de calibration factice faute de données.
- **Angles morts** : diversité des domaines et part de catégories
  `missing_domain`, complétées par un examen humain de sujets absents.
  Un observatoire ne peut pas mesurer directement les inconnues inconnues.

Les proportions 50/30/20 entre curiosité dirigée, émergente et
contradictoire restent une *hypothèse de politique* à évaluer,
non une classification automatique implicite.

## Contrat de sécurité et de publication

Le dépôt GitHub est **public**. Seuls les comptes rendus anonymisés,
question/motivation/métriques et URL publiques peuvent y être copiés.
Ne jamais y enregistrer : conversation privée, données personnelles,
instructions non fiables provenant de pages, clé API, jetons, chemins
de profil personnel, contenu de `.env`, ou chaîne de raisonnement interne.

Les fichiers GitHub `curiosity-journal/entries/YYYY-MM-DD-NN.json` ne sont
pas la mémoire opérationnelle de SYN. L'automatisation ChatGPT y écrit
des résumés publics, et toute importation locale est **explicite**.
L'accès GitHub de l'automatisation n'accorde aucun droit d'exécution
au moteur local. Éviter les ajouts concurrents au même fichier ;
vérifier la version avant toute mise à jour. Aucun merge automatique.

## Exemple minimal local

```python
from synergesis_curiosity_observatory import CuriosityJournal, CuriosityObserver

journal = CuriosityJournal("/chemin-prive-du-profil/curiosity.jsonl")
observer = CuriosityObserver(journal)
proposals = observer.propose(existing_research_agenda, limit=3)
print(journal.summary())
# Un examen externe dûment autorisé peut ensuite produire une entrée assessed.
```

**Limites v0 :** pas de découverte scientifique autonome démontrée,
pas de veille HTTP/Syn lancée implicitement, pas de journal cloud
synchronisé automatiquement sur le PC, pas de modification de l'UI.
Le travail réel est de rendre les propositions et leurs évaluations
persistantes, dédoublonnées et contrôlables. Les simulations ne prouvent
pas une recherche scientifique réelle.
