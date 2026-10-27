# SYN — Surprise mesurée, pas supposée (v0)

**25 octobre 2026, Europe/Paris.** Cet instrument est expérimental et **ne confère aucune autonomie nouvelle** à SYN.

## Hypothèse testable

Une découverte qui paraît extraordinaire n'est pas automatiquement une observation inattendue pour SYN. Pour mesurer la *surprise réalisée*, il faut une prédiction binaire chiffrée **figée avant l'intervalle de l'événement**, puis une observation vérifiable indépendante. Notre outil calcule le **Shannon surprisal réalisé**, soit `-log2(P(résultat observé))` bits.

Ceci diffère de :
- La **nouveauté** (étude jamais lue, contenu inhabituel);
- L'**erreur Brier** `(p-y)^2` (mauvaise prévision);
- Le **gain d'information bayésien**, qui exige la distribution avant/après sur des hypothèses explicites et ne se réduit pas au simple `-log2` de l'événement;
- Le **progrès d'apprentissage**, qui nécessite une amélioration de performance sur des prédictions nouvelles comparées à des baselines.

Un événement très surprenant peut être un tirage aléatoire, un artefact d'observation ou une prévision trop confiante. **Ne jamais promouvoir cette surprise directement en connaissance.**

## Code et contrôles

- `curiosity-journal/tools/syn_prediction_surprise_v0.py` : lit séparément prévisions et issues binaires, vérifie les timestamps et l'ordre des fenêtres UTC, exige une vérification externe *déclarée* avant de scorer, mesure Shannon surprisal et Brier, et sélectionne des pistes hautement surprenantes en imposant une limite de domaines.
- `curiosity-journal/tools/test_syn_prediction_surprise_v0.py` : **17 tests** sur jeux artificiels, pour postdiction, issues anticipées, doublons, probabilités incohérentes, informations manquantes, URL et détection d'une erreur de prévision.
- Les métadonnées `externally_verified` et `verifier_id` proviennent du fichier fourni. **Le programme hors ligne ne peut ni confirmer l'identité du vérificateur, ni certifier le timestamp GitHub, ni vérifier les données USGS par lui-même.** Il ne fait que refuser de scorer lorsqu'une vérification n'est pas déclarée.

Commande à exécuter **uniquement après la résolution** :

```bash
python curiosity-journal/tools/syn_prediction_surprise_v0.py \
  --forecasts curiosity-journal/forecast-pilot/2026-11-02-usgs-forecast-input-v0.jsonl \
  --outcomes /chemin-prive/observations-usgs-validees.jsonl \
  --output /chemin-prive/rapport-surprises.json
```

Un événement non résolu ou marqué non vérifié reste **non scoré**. Il n'est jamais interprété comme faux par défaut. Le programme n'écrase pas les fichiers et n'appelle pas de modèle ni d'API.

## Première vraie prévision déposée avant résultat

- **Fichier horodaté, lien immuable par commit SHA** : https://github.com/subharmonicseed/Synergesis/blob/b409e84520013b6c2717f911a7e208b26b1788e1/curiosity-journal/forecast-pilot/2026-11-02-usgs-prospective-v0.json
- Prévisions lisibles par l'outil : `curiosity-journal/forecast-pilot/2026-11-02-usgs-forecast-input-v0.jsonl`.
- **Création enregistrée : 2026-10-25T13:19:00.771Z**.
- **Fenêtre : [2026-11-02T00:00:00Z, 2026-11-09T00:00:00Z)**.
- P(au moins un séisme mondial USGS M≥7) = **0,232**.
- P(au moins trois séismes mondiaux USGS M≥6) = **0,425**.
- **Méthode :** modèle de Poisson de fréquence de base, *non appris par SYN* :
  * USGS estime pour 2015–2025 environ 13 M7–7,9, 0,7 M8+, 110 M6–6,9 séismes par an : https://www.usgs.gov/programs/earthquake-hazards/science/earthquake-sequence-product
  * Intensité hebdomadaire `lambda7=(13+0.7)/52`, `lambda6=(110+13+0.7)/52`.
  * `P(N7>=1)=1-exp(-lambda7)≈0.232`; `P(N6>=3)=1-exp(-lambda6)*(1+lambda6+lambda6²/2)≈0.425`.
- **Source future d'arbitrage :** https://earthquake.usgs.gov/fdsnws/event/1/ ; interroger les magnitudes et timestamps UTC avec borne supérieure stricte et dédoublonnage des événements, archiver les preuves, puis vérifier **après le 23 novembre 2026**, soit 14 jours après la fin de la fenêtre (voir le protocole antérieur).
- Ce modèle Poisson suppose les événements indépendants et une fréquence stationnaire; les répliques, séquences, effets de catalogue et dépendances entre les deux questions rendent ces hypothèses approximatives. **Ce n'est ni un système d'alerte ni une capacité de prédiction individuelle des séismes.**
- **Aucune issue encore connue, aucun score encore calculé et aucune amélioration de SYN démontrée**.

## Critères qui réfuteraient le moteur de curiosité

Une future expérience comparera le budget de recherche alloué (A) aux thèmes éditorialement nouveaux, (B) aux prédictions les plus surprenantes, et (C) aux prédictions erronées pour lesquelles une expérience indépendante paraît susceptible de réduire l'incertitude. Mesurer sur des tâches futures tenues à l'écart le score Brier, le coût, les hypothèses nouvellement réfutées et le taux d'erreurs de provenance. 

Si (B) sélectionne surtout du bruit irréductible et n'améliore pas le Brier contre (A) ou un témoin de taux de base, la « chasse à la surprise » n'a pas établi son utilité. Une règle de forte surprise ne prouve aucune AGI.

## Sources méthodologiques

- Curiosity and the dynamics of optimal exploration (Trends in Cognitive Sciences, 2024) : https://doi.org/10.1016/j.tics.2024.02.001
- Novelty as a drive of human exploration in complex stochastic environments (2025) : https://pmc.ncbi.nlm.nih.gov/articles/PMC12501151/
- Rethinking Aleatoric and Epistemic Uncertainty (ICML 2025) : https://proceedings.mlr.press/v267/bickford-smith25a.html
- USGS Earthquake Event service: https://earthquake.usgs.gov/fdsnws/event/1/

**État final :** outil de vérification hors ligne ajouté; deux vraies prévisions de référence déposées; évaluation de connaissances, boucle autonome et apprentissage actif non implémentés.
