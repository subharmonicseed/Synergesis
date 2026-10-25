# SYN — hypothèse d'architecture vers une intelligence plus générale (v0)

Date : 2026-10-25 (Europe/Paris). **Document de recherche, NON une AGI réalisée.**
Aucune autonomie locale, modification du code du superviseur, modification de poids LLM ou autorisation d'exécution supplémentaire n'est créée par ce document.

## Hypothèse H-AGI-01

Une architecture où un modèle de base inchangé sélectionne des lacunes épistémiques, produit des expériences bornées, reçoit des conséquences indépendantes, transforme certains apprentissages en compétences réutilisables et teste ces compétences sur des tâches inconnues **pourrait** élargir graduellement le domaine de compétences observable. Elle ne devient une théorie crédible d'intelligence générale que si les progrès sont **transférables**, **cumulatifs**, **hors échantillon**, **fiables** et **plus importants que les coûts ajoutés**.

Contrairement à une métaphore de « pensée infinie », ceci exige des expériences extérieures au modèle. Le système peut s'améliorer sans mise à jour des poids (compétences procédurales), mais cela ne prouve pas un apprentissage général illimité.

## Boucle expérimentale : du non-savoir à la capacité validée

1. **Observer et mesurer** — Recevoir des sources et un état vérifiable; faire une distinction stricte entre données, hypothèses et résultats. Une conversation convaincante ne compte jamais comme preuve.
2. **Cartographier les lacunes** — Recherche contradictoire, échecs vérifiés, données vieillies et domaines non couverts. Les auto-scores sont des heuristiques de tri, non des mesures d'intelligence.
3. **Choisir une expérience** — Sélectionner l'expérience qui pourrait discriminer le mieux entre hypothèses sous une enveloppe de coût, risque et temps; prévoir un test nul et des critères d'arrêt.
4. **Déclarer le résultat attendu AVANT l'essai** — Prévision chiffrée, jeux de test gelés, horodatage, seuil d'échec, budget de tokens/temps et références; aucune édition après résultat.
5. **Exécuter uniquement les actions autorisées** — Sandboxing; AEGIS, RISK, REALITY et approbation humaine conservés. Les cycles ChatGPT planifiés sont des recherches ponctuelles, pas une exécution continue sur le PC.
6. **Arbitrer indépendamment** — Données et vérificateur externes, résultats bruts, tests négatifs et contradictions; l'agent candidat ne peut ni modifier son évaluateur ni réécrire les reçus.
7. **Compiler une compétence candidate** — Extraire des règles utiles de comparaisons réussite/échec; conserver son contexte d'applicabilité, les preuves, le comportement attendu et les contre-exemples. Un texte stocké n'est pas encore une compétence.
8. **Comparer avec/sans compétence** — Même modèle, même budget, mêmes tâches inédites; mesurer cas réparés ET régressions induites, y compris hors du domaine d'origine.
9. **Promouvoir, refuser ou revenir en arrière** — Une compétence n'entre en mémoire opérationnelle qu'après essais concluants et validation humaine; garder la provenance et permettre la révocation.
10. **Recommencer avec de nouvelles lacunes** — Les contre-exemples deviennent de nouveaux besoins de recherche. Les réussites non reproductibles n'augmentent pas le score de maîtrise.

```text
Sources/monde → Détecteur de lacunes → Agenda de curiosité → Hypothèse/test gelés
                                                        ↓
Bibliothèque de compétences ← Promotion humaine ← Arbitrage indépendant ← Exécution autorisée
           │                                                 ↑
           └──────────────── transfert et tests inconnus ─────┘
```

## Liens avec l'état inspecté de Synergesis

- `ResearchAgenda` et `synergesis_roam_attention.py` : classement de besoins et sélection bornée, **déjà documentés**.
- `CuriosityObserver` et `CuriosityJournal` dans `synergesis_curiosity_observatory.py` : propositions et journal hashé, **pas** vérification externe automatique.
- Journal public `curiosity-journal/entries/` : observations sourcées partageables, **pas** mémoire opérationnelle approuvée; import local explicite.
- Chaîne AEGIS/RISK/REALITY et superviseur : bornes à préserver; ce document **ne suppose pas** que les nouveaux organes ci-dessous sont implémentés.
- **Manquants/proposés** : `ExperimentRegistry` (pré-enregistrement), `IndependentOutcomeVerifier` (arbitrage sous autorité séparée), `SkillCandidate` + `SkillTransferEvaluator`, `PromotionGate` (approbation et restauration), suivi du coût et du déclin hors distribution.
- Le pilote prospectif USGS `curiosity-journal/protocols/2026-10-25-prospective-forecast-pilot-v0.md` peut vérifier la mécanique de dépôt et de résolution, **pas** une AGI.

## Expérience qui peut réfuter H-AGI-01

Geler le même modèle, le même corpus autorisé, les mêmes permissions, le même budget de calcul et une série de tâches dont certaines ne sont révélées qu'après la création de compétences. Répartir à l'avance plusieurs tâches dans **au moins trois domaines distincts** (par exemple prévision probabiliste, correction de logiciel isolée, extraction de données avec vérificateur déterministe).

Comparaison ablatrice :
- **A, témoin** : modèle + accès standard aux mêmes sources, sans mémoire historique ni curricula.
- **B, journal seul** : A + mémoire d'observations, sans compilation de compétences.
- **C, recherche vérifiée** : B + agenda d'incertitude, expériences et arbitrage externe.
- **D, compétences transférables** : C + promotion de compétences réellement validées.

Geler les versions de modèles, les règles de sélection et les budgets avant les essais. Randomiser l'ordre des tâches, utiliser des jeux de tests inconnus des agents, conserver les échecs, et empêcher l'accès aux solutions d'arbitrage. Les comparaisons interdomaines exigent plusieurs réplications et une mesure de coût.

**Critère principal candidat** : gain apparié hors échantillon (score de D moins A), par domaine et agrégé avec pondération fixée avant le test. Aucun gain n'est revendiqué avant l'expérience.
Secondaires : calibration/Brier sur prévisions binaires, proportion de tâches réussies avec critères déterministes, « réparation moins régression » par compétence, adaptation à un nouvel environnement, persistance après effacement de contexte, consommation de ressources, diversité des cas résolus, fiabilité des sources.

Les résultats qui infirmeraient le mécanisme comprennent : (i) D ne surpasse pas B sur tâches inédites au budget égal, (ii) progrès uniquement sur les tâches ayant servi à concevoir les compétences, (iii) plus de régressions ou de fraude aux métriques, (iv) aucune amélioration transférable après plusieurs cycles, (v) effets qui disparaissent lorsqu'on élimine le contexte court.

Aucune de ces conditions ne constitue à elle seule une définition consensuelle de l'AGI. Il faudrait davantage : planification robuste à long horizon, transfert entre domaines très hétérogènes, compréhension des mécanismes du monde, corrigibilité, sécurité et capacité d'adaptation hors distribution.

## Précautions contre le « score hacking »

- L'agent peut proposer un test, **jamais** choisir ou modifier son résultat de vérité.
- Les logs, données brutes, jeux cachés et portes de déploiement sont en dehors de son autorité.
- Un agent candidat ne doit pas être juge unique de sa propre amélioration.
- Séparer « modification proposée », « code testé » et « comportement effectivement observé ».
- Empêcher des compétences apprises de contourner la politique de permissions, d'éditer la CI, les tests ou les garde-fous.
- Maintenir des limites de dépense et une intervention humaine pour toute modification de capacité ou de code.

## État réel au dépôt

**Ce qui existe** : veille ChatGPT ponctuelle/récurrente, entrées GitHub auditées, observateur de propositions, références bibliographiques, protocole futur de prévision.

**Ce qui n'existe pas encore** : boucle d'expériences locale persistante, promoteur autonome de compétences, vérificateur indépendant en service, essai A/B exécuté, preuve de transfert, et AGI.

## Sources primaires — pertinence ET limites

- Voyager (2023/2024), curriculum + bibliothèque + feedback dans Minecraft : https://arxiv.org/abs/2305.16291
- Darwin Gödel Machine (2025), auto-modification et tests sous sandbox : https://arxiv.org/abs/2505.22954
- AlphaEvolve (2025), recherche évolutive à vérification automatique : https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- SkillLearnBench (COLM 2026), apprentissage de compétences inconstant et risque de dérive en auto-feedback : https://arxiv.org/abs/2604.20087
- ContinualSkillBench (août 2026), bénéfice variable de compétences explicites par rapport au contexte : https://arxiv.org/abs/2608.03874
- SkillGen (mai 2026), induction à partir de traces contrastées et tests d'impact : https://arxiv.org/abs/2605.10999
- MSCE (EMNLP 2026), mémoire procédurale reliée à la preuve : https://aclanthology.org/2026.findings-emnlp.1637/
- Reward Hacking Challenges Oversight of Autonomous Research Agents (sept. 2026) : https://www.microsoft.com/en-us/research/publication/reward-hacking-challenges-oversight-of-autonomous-research-agents/

**Décision méthodologique** : consacrer la prochaine série de recherches à mesurer la différence entre « se souvenir », « appliquer une compétence », « transférer » et « améliorer sa capacité d'apprendre ». Ne pas confondre une suite de conversations profondes avec une auto-amélioration démontrée.
