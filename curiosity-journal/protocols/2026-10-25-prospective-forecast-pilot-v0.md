# SYN-CURIOSITY — pilote prospectif v0 (préprotocole, PAS une étude réalisée)

**Établi le 25 octobre 2026 (Europe/Paris).** Branche expérimentale seulement.
État : protocole publié à l'avance, **aucune prévision déposée**, aucune comparaison A/B exécutée, aucun gain démontré.

## Pourquoi

L'objectif de l'entrée `chatgpt:2026-10-25:26` est de distinguer *qualité du discours et du journal* de *compétence prédictive*. Une baisse d'incertitude auto-déclarée n'est pas un résultat expérimental.

## Périmètre, source primaire et licence

- **Source de résolution** : catalogue mondial USGS FDSN Earthquake Event Web Service, documentation https://earthquake.usgs.gov/fdsnws/event/1/ . Utiliser les données d'événements dont `time` est dans un intervalle UTC demi-ouvert `[start,end)`, en filtrant les horodatages après interrogation. `minmagnitude` filtre les séismes au seuil inclus.
- La décision d'événement résolu vient des valeurs USGS **14 jours après la fin de chaque semaine**, afin de réduire les effets des mises à jour de catalogue. Archiver URL, date de récupération et valeurs observées; enregistrer les corrections postérieures séparément.
- Ne pas utiliser l'API Metaculus comme jeu d'entraînement/d'évaluation sans autorisation écrite adéquate : https://github.com/Metaculus/metaculus/blob/main/docs/openapi.yml .
- L'analogie avec ForecastBench sert à choisir les bonnes méthodes, pas à prétendre participer officiellement à son classement : https://www.forecastbench.org/about/ . L'accès au tournoi complet exige une procédure propre : https://github.com/forecastingresearch/forecastbench/wiki/How-to-submit-to-ForecastBench .

## Questions publiques fixées à l'avance

8 fenêtres hebdomadaires UTC commençant chacune à 00:00Z, les lundis **2026-11-02**, 11-09, 11-16, 11-23, 11-30, 12-07, 12-14 et 12-21. La dernière se termine **2026-12-28T00:00:00Z**.

Pour chaque semaine (deux questions binaires, 16 au total) :

- **Q-A** : au moins un séisme de magnitude **>=7.0** enregistré par l'USGS à l'échelle mondiale dans la semaine ?
- **Q-B** : au moins **trois** séismes de magnitude **>=6.0** enregistrés par l'USGS à l'échelle mondiale dans la semaine ?

Ces questions sont **corrélées**; toute inférence statistique doit tenir compte du regroupement par semaine. Une semaine où la résolution est inaccessible restera manquante, sans supposer un résultat négatif.

## Prévision verrouillée

- **Date limite** : avant `00:00:00Z` du lundi ouvrant chaque fenêtre; enregistrer le commit GitHub du fichier **avant** la fenêtre. Aucune soumission tardive n'est notée. **Première échéance : 2026-11-02T00:00:00Z**.
- Pour chaque question, archiver la probabilité numérique `p` de l'événement binaire dans `[0,1]`, son mode de génération, ses références publiques, l'identifiant/variante du modèle, l'horodatage, et le coût/volume d'appels. Pas de révision d'une prévision après dépôt; toute mise à jour dans un fichier distinct.
- Baseline **0,5** pour chaque question + baseline empirique : fréquence observée pour le même indicateur dans les **26 semaines non chevauchantes précédant la semaine cible**, calculée **uniquement sur informations disponibles au gel**, avec la source, le dénominateur et la date conservés. S'il manque des observations, documenter la perte; ne jamais inventer la fréquence.
- Une première démonstration avec un seul flux ChatGPT évalue **la faisabilité du protocole**, pas un effet causal. Pour l'expérience A/B, il faut deux contextes indépendants : même modèle/version, budget, informations disponibles et questions; **contrôle** sans journal de curiosité; **traitement** avec journal et contre-hypothèses; tirage préalable de l'ordre de génération; identifiants et prompts archivés. Aucun de ces bras n'a été exécuté ici.

## Analyse définie avant observation

- Critère principal : score de Brier binaire `(p - y)^2`, avec `y=1` si événement observé, sinon `0`. Plus bas est meilleur. Pour A/B, calculer sur les mêmes questions la différence moyenne `Brier_controle - Brier_curiosite` (positive = traitement meilleur).
- Indicateurs secondaires : couverture des questions, impossibilité de résolution, proportion de décisions abstention, coût de recherche, références primaires vérifiables. Graphique de calibration seulement descriptif : **16 événements corrélés** sont insuffisants pour une preuve solide de calibration ou un test de supériorité.
- En cas d'A/B répété : intervalle de confiance par rééchantillonnage **des semaines**, pas des 16 questions comme si elles étaient indépendantes; ne pas changer les règles après les résultats, et ne pas arrêter l'essai prématurément à cause d'un bon score.
- La qualité de la synthèse n'est **pas** le critère principal. Une prévision enregistrée après qu'un événement s'est produit est rejetée, même si elle est correcte.

## Transparence du gel

Un commit GitHub public horodate le protocole et les résultats, mais l'historique d'une branche peut être réécrit. Pour une préinscription plus forte, utiliser un registre réellement figé, par exemple OSF Registries : https://help.osf.io/article/330-welcome-to-registrations . **Aucune inscription OSF n'a été faite.**

## Limites explicites

Ce pilote ne démontre ni prévision supérieure, ni métacognition, ni autonomie continue. Les événements d'une même semaine sont corrélés, et l'activité sismique est un domaine où un LLM n'a pas nécessairement d'avantage sur une baseline statistique. C'est voulu : le **premier succès mesurable** serait le respect des dates de gel, une résolution indépendante et un score reproductible, non une victoire sur le témoin.
