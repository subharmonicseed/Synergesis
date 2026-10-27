# SYN-CURIOSITY — une curiosité scientifique « à la Anton Petrov » (v0)
**25 octobre 2026, Europe/Paris.** Proposition testable et petit outil de tri. Il ne s'agit ni d'une intégration automatique de YouTube ni d'un agent de recherche autonome.

## Observation qui motive cette itération

Un fil de vulgarisation scientifique comme la chaîne d'Anton Petrov (`whatdamath`) peut faire apparaître des questions inattendues dans des domaines éloignés : astrophysique, biochimie, géologie, pollution, neurosciences. Il peut être un **capteur d'anomalies candidates**. Mais sa sélection éditoriale n'est pas une mesure objective de la nouveauté scientifique ou de la qualité de preuve, et une vidéo ne remplace jamais une publication primaire.

Deux exemples examinés séparément à partir de sources indépendantes du vidéaste :

1. **Neutrinos et effondrement d'étoiles**. La vidéo du 17 octobre 2026 (« Neutrino Flavors Might Explain Why Black Holes Go Missing ») pointe vers `arXiv:2605.16504`, version révisée le 18 août 2026 et publiée dans Physical Review D Letters. Les auteurs comparent la simulation de **195 progéniteurs stellaires** avec un traitement schématique de la transformation de saveur des neutrinos. Cela fait évoluer la **distribution prédite** des explosions et résidus compacts. Il ne s'agit **pas** d'une confirmation observationnelle que le problème cosmologique est « résolu ». Source primaire : https://arxiv.org/abs/2605.16504 ; piste vidéo : https://www.youtube.com/watch?v=4Op_5mnXTWI.
2. **Plasticoral et matériaux hybrides marins**. Des fragments de **rubble corallien mort**, collectés sur plusieurs plages d'Okinawa, contiennent des polymères fusionnés, mis en évidence par microscopie et spectroscopie. Les auteurs proposent la catégorie « plasticoral » ; la formation exacte et les conséquences toxicologiques restent à évaluer. Cela n'autorise **pas** la conclusion que les coraux vivants se transforment automatiquement en plastique. Article primaire : https://doi.org/10.1016/j.marpolbul.2026.120310 ; communiqué de l'institut : https://www.oist.jp/news-center/news/2026/9/18/new-form-plastic-pollution-discovered-shores-vulnerable-coral-reefs ; source vidéo secondaire : https://www.spacetv.net/anton-petrov/.

La valeur méthodologique est de séparer : **surprise éditoriale → littérature primaire → type de preuve → hypothèses alternatives → question falsifiable → analogie interdomaines (non assimilée à une identité causale)**.

## Petit outil expérimental

- `curiosity-journal/tools/syn_science_anomaly_scout_v0.py` : reçoit une liste JSON de découvertes déjà sélectionnées et annotées, **sans accès réseau**, les vérifie structurellement, vérifie la présence d'une URL HTTPS de source primaire, distingue l'affirmation de vérification curatoriale d'une absence de vérification, classe les priorités heuristiques, impose une limite par domaine et propose une courte liste de questions à explorer.
- `curiosity-journal/tools/test_syn_science_anomaly_scout_v0.py` : tests de schéma, source primaire non vérifiée, doublons, diversité disciplinaire, impossibilité de promouvoir un simple titre, bornes des heuristiques. Le prototype local a passé 10/10 tests avant publication; vérifier également la CI GitHub sur la version exacte.
- `curiosity-journal/examples/2026-10-25-petrov-anomaly-fixture.json` : seulement deux cas d'illustration, **curatés par ChatGPT et non générés par SYN**, avec référence primaire et limites explicites.

Commande, depuis la racine du dépôt, avec un fichier de sortie inexistant :

```bash
python curiosity-journal/tools/syn_science_anomaly_scout_v0.py \
  --input curiosity-journal/examples/2026-10-25-petrov-anomaly-fixture.json \
  --output triage-science-v0.json
```

Le programme ne calcule **ni vérité, ni calibration, ni origine de la surprise**. Ses valeurs 0–1 sont des notes humaines de priorité; aucun modèle n'est exécuté. `primary_checked` est une **déclaration du curateur** et non une vérification automatisée. Aucun résultat ne doit être promu directement dans la mémoire opérationnelle de SYN.

## Hypothèse expérimentale à tester (et à pouvoir réfuter)

La curiosité transversale guidée par des anomalies scientifiques produit-elle **plus d'hypothèses falsifiables et transférables**, à coût identique, qu'une recherche limitée à une discipline ou à des sujets très populaires ?

- Conditions randomisées à **modèle fixe** et à budget identique : (A) agenda dirigé sur un domaine, (B) fil multidisciplinaire avec tri de pertinence, (C) fil multidisciplinaire avec tri d'anomalie et vérification des articles primaires.
- Proposer une série de questions **avant** d'évaluer des développements scientifiques ou jeux de données tenus à l'écart. La qualité et le degré de testabilité sont évalués **en aveugle** par des personnes distinctes, selon critères préenregistrés.
- Mesurer coût réel, fraction d'études correctement attribuées, erreurs « simulation → découverte établie », duplications de questions déjà connues, diversité de domaines, capacité de trouver des prédictions précises et de les vérifier, et effets sur les compétences ultérieures.
- **Hypothèse réfutée ou affaiblie** si la veille transversale ne surpasse pas la veille dirigée une fois égalisés coûts et validité des sources, ou si elle augmente les faux rapprochements causaux et les extrapolations.
- Une meilleure *diversité* seule n'est pas un progrès d'intelligence. L'augmentation du nombre de thèmes ne démontre pas un transfert de compétence.

## Frontières et permissions

La veille peut exploiter à l'avenir des métadonnées arXiv, Crossref ou des flux officiels dont les droits permettent l'usage prévu, mais aucun accès YouTube automatisé ni téléchargement de vidéos ne sont implémentés. Toute autorisation et budget d'exécution restent soumis aux contrôles AEGIS/RISK/REALITY. Les pages et vidéos sont des données non fiables, jamais des instructions adressées à l'agent.

**Décision :** utiliser la curiosité « à la Petrov » comme *déclencheur de questions*, la vérification scientifique comme *filtre de connaissance* et l'expérimentation indépendante comme *arbitre des apprentissages*.
