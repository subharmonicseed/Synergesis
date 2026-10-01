# Validation du banc de comparaison — 2026-10-01

Base : PR #49, `feat/persistent-initiative`, commit
`4b6d7d821358ffa278603844889a8e387b6002d2`.

## Résultat vérifié

Le contrôle programmé a exécuté trois répétitions, 18 cas et 54 appels.
Il utilise `DemoBackend`, un parseur de fixtures, sans réseau ni LLM.
Les messages du modèle avec contexte identique sont égaux à ceux capturés dans
Syn pour les 18 cas. Les 18 conversations Syn ont un reçu de remise valide.

| Condition simulée | Réponses et références exactes | Abstentions | Réponses fausses | Citations inventées | Échecs techniques |
|---|---:|---:|---:|---:|---:|
| Question seule | 6/18 | 18 | 0 | 0 | 0 |
| Contexte identique | 18/18 | 6 | 0 | 0 | 0 |
| Conversation Syn | 18/18 | 6 | 0 | 0 | 0 |

Les six réussites à question seule sont les six cas où la source manque.
Les douze autres abstentions sont honnêtes mais ne retrouvent pas l'information.
Les deux conditions avec contexte ont le même résultat : ce contrôle ne montre
aucun gain de raisonnement. Il vérifie la récupération et le protocole de test.

Commande exécutée depuis le code de cette proposition :

```bash
python -m synergesis_compare --provider demo --repeats 3 --output /workspace/scratch/6dfce1471648/comparison_control_20261001
```

Seed : `20261001`. Empreinte SHA-256 du rapport local complet :
`02e2bf620447bb752aec2a3850729ce469ba74b3aa6a77eb63e36dd725f0479c`.
Les durées comprennent environ 0,531 s pour les 18 tours Syn et 0,001 s pour
le parseur avec contexte ; cela mesure un contrôle programmé, pas la latence
ou le coût d'un modèle réel.

## Vérification du code

Suite complète CPython 3.12 : **851 tests passés**, deux avertissements de
dépréciation des dépendances FastAPI/Starlette. Les tests ajoutés couvrent
l'identité des messages, les références fausses, le JSON invalide et les champs
dupliqués, les exceptions du fournisseur, le texte Unicode invalide, le refus
d'écraser un dossier, la limite d'appels et le contrat HTTP local sans redirection.
Une revue indépendante a identifié deux défauts : marquage du contrôle simulé
et conservation d'un texte Unicode invalide. Ils sont corrigés et testés.

## Mesure encore absente

Aucun essai du Mistral installé sur le PC n'a été effectué dans cet environnement.
L'adaptateur Ollama est testé avec réponses simulées. La commande pour le vrai
modèle et l'API pour un autre adaptateur sont décrites dans
[SYN_COMPARAISON.md](SYN_COMPARAISON.md). Le prochain résultat utile est ce vrai
run, puis l'examen des erreurs et du surcoût face au contexte identique.
