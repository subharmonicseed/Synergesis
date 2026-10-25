# SYN-COGNITIVE-TWIN v0 — un scaphandre ontologique minimal, testable

**25 octobre 2026 · branche isolée `feat/syn-cognitive-twin-v0`, issue de `feat/syn-recursive-inheritance-v1`.**

Il ne s'agit ni d'un double parfait, ni d'une conscience indépendante, ni d'un système qui lit les intentions préverbales. **La première propriété visée est concrète : reprendre, après fermeture et réouverture, une intention explicitement enregistrée, des objections persistantes et une décision effectivement validée par l'utilisateur, sans substituer l'acquiescement automatique à la critique.**

## Ce qui existait déjà

- `synergesis_chat.py` / `synergesis_conversation.py` : conversation réelle, remises contrôlées par AEGIS/REALITY, journaux par session.
- `synergesis_initiative.py` : souvenirs déclarés et questions persistants d'une session à l'autre, extraction lexicale limitée.
- `synergesis_ollama_backend.py` : conversation sans clé à `127.0.0.1` avec modèle installé.
- La branche Work `feat/syn-recursive-inheritance-v1` : expérimentation d'un routeur héritant de statistiques d'exécution vérifiées, distinct de la personnalisation intellectuelle.

## Nouveau code

`synergesis_cognitive_twin.py` ne modifie pas le cœur de SYN. Il enveloppe le backend de génération et utilise `open_conversation` existant :
- **Contrat de dialogue** : expliciter l'intention, offrir une objection sérieuse, demander une épreuve discriminante et proposer une suite concrète. Le modèle doit pouvoir dire « je ne sais pas ». C'est une instruction, pas une preuve de son comportement réel.
- **Mémoire privée explicite** : intentions, objections et décisions saisies par l'utilisateur, dans `<profile>/twin.jsonl`; n'autorise aucune écriture autonome du modèle. Les décisions ne sont jamais déduites d'une réponse LLM.
- **Continuité** : le dernier objectif, au plus deux objections, et la dernière décision sont transmis dans chaque tour du nouveau dialogue. Le registre complet demeure sur disque, append-only et chaîné par SHA-256.
- **Limites** : 128 annotations au total, 1 200 caractères par annotation, extraits du contexte bornés à 500 caractères, 19 tours maximum, nouveaux dossiers de session obligatoires, profil et sorties locaux. Un hash ne constitue pas une attestation externe d'intégrité contre une personne pouvant tout réécrire.
- **Sécurité** : aucune permission nouvelle, aucun nouveau système d'outil, aucune écriture de fait scientifique, aucune auto-modification. Les textes mémorisés restent déclaratifs et non vérifiés. La boîte de livraison reste celle d'AEGIS/REALITY; ce contrôle certifie seulement la remise du texte.
- **Ollama** : le mode `conversation=True` de l'adaptateur existant refuse un message système fourni par le client. Le jumeau utilise donc le **transport existant** en `conversation=False, response_format=None`, pour fournir lui-même son seul message système en texte ordinaire, sans activer d'outil. Timeout HTTP de 60 secondes sans relance. La connexion locale n'a pas été testée depuis ce chat.

## Commandes utilisables sous WSL/Linux

Depuis la racine du dépôt, environnement Python du projet déjà installé, serveur Ollama démarré et `ollama list` confirmant le nom du modèle :

```bash
# 1. Noter son intention en privé (aucun appel LLM)
python -m synergesis_cognitive_twin \
  --profile ./syn-private/twin-profile \
  --output ./syn-private/twin-session-001 \
  --intent "Construire un assistant qui prolonge mes intuitions mais critique mes erreurs." \
  --objection "Une forte impression de compréhension n'est pas une mesure scientifique." \
  --provider ollama --model syn-mistral-import:latest \
  --message "Quelle serait la meilleure expérience pour tester cette intuition ?"

# 2. Redémarrer dans un NOUVEAU dossier, avec le même profil
python -m synergesis_cognitive_twin \
  --profile ./syn-private/twin-profile \
  --output ./syn-private/twin-session-002 \
  --provider ollama --model syn-mistral-import:latest \
  --message "Que poursuis-je et quelle objection devrais-je garder en tête ?"

# 3. Sans modèle ni API, démontrer uniquement la chaîne technique
python -m synergesis_cognitive_twin \
  --profile ./syn-private/demo-profile \
  --output ./syn-private/demo-session-001 \
  --provider demo --intent "Examiner mes idées contradictoirement." \
  --message "Teste mon hypothèse."
```

Sans `--message`, le programme accepte en mode terminal interactif : `/intention ...`, `/objection ...`, `/decision ...`, puis le dialogue libre et `/quitter`. Seuls ces trois ordres ou les trois options CLI équivalentes peuvent créer une annotation. L'historique de conversation ordinaire reste dans les traces de session, pas dans le registre de décisions approuvées.

**Ne pas publier les dossiers privés** : le dépôt GitHub public ne contient que le code et des exemples fictifs. Le profil de travail doit rester hors du contrôle de version.

## Ce qui reste à prouver

Le test logiciel avec un faux modèle vérifie l'injection du contexte, la relecture de sessions distinctes, les refus en cas de corruption et le passage par AEGIS/REALITY. Les tests de transport utilisent la vraie construction des requêtes Ollama mais un faux échange HTTP; ils ne mesurent pas la qualité cognitive de Mistral.

**Protocole du premier essai réel :** même modèle local, mêmes questions complexes tenues à l'écart, comparaison aveugle :
A. conversation standard SYN ; B. instructions de critique sans héritage ; C. contrat cognitif avec état hérité.
Critères : fidélité au but exprimé, objection non triviale et pertinente, capacité à reconnaître une erreur, proposition de test réalisable, conservation des décisions confirmées, fausses attributions et coût en tokens. Un évaluateur indépendant doit identifier les défauts; aucun score ne se déduit de la présence des mots « objection » et « test ».

**Ce que ce v0 démontre si ses tests passent : la continuité de données et de prompts dans la chaîne de conversation existante. Ce qu'il ne démontre pas : la compréhension de ton intention non exprimée, un apprentissage personnel autonome ou un double cognitif parfait.**

## Articulation avec Work

Ne pas merger la branche sans comparer les divergences et les tests. La route expérimentale récursive choisit des outils; cette route conversationnelle nourrit un contrat cognitif contrôlé par l'utilisateur. L'intégration ne sera justifiée qu'après un essai empirique de dialogue, des contrôles de confidentialité et l'inspection du coût.
