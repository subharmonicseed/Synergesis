# Syn apporte-t-il quelque chose au modèle ?

Cette comparaison mesure deux fonctions concrètes : retrouver un souvenir
explicitement enregistré après rechargement du profil, et répondre depuis un
document local en citant son reçu. Elle ne mesure pas l'intelligence générale,
la volonté, l'entraînement ni la capacité à inventer une théorie scientifique.

Chaque répétition utilise six cas synthétiques : deux souvenirs présents,
deux informations présentes dans un document, un souvenir absent et une
information absente du document. Les clés et valeurs sont générées à partir
d'une seed, et les valeurs attendues ne figurent jamais dans la question.
Le profil est fermé puis reconstruit dans le même processus : cela vérifie sa
relecture depuis le disque, sans simuler un redémarrage de l'ordinateur.

| Condition | Informations reçues | Ce que l'on compare |
|---|---|---|
| `bare_model` | Question seule | Utilité de fournir mémoire et documents |
| `matched_context` | Messages exactement identiques à ceux envoyés par Syn | Réponse du même modèle avec le même contexte |
| `syn` | Même contexte, plus la conversation et le contrôle de remise Syn | Réponse et coût de l'orchestration |

Un modèle seul qui répond `unknown` faute d'information se comporte correctement.
Ce cas reste compté séparément comme abstention honnête, même si une réponse
positive n'est pas retrouvée. Le score global mélange cas présents et absents :
consulter aussi les cas individuels et leur type dans le rapport. Un succès exige
la valeur exacte et les bons IDs ; un reçu de livraison REALITY ne valide pas
la vérité du texte. Le correcteur synthétique effectue cette vérification séparée.

## Vérifier le dispositif sans modèle

Depuis cette branche, installer le projet avec Python 3.11 ou 3.12 :

```bash
python -m pip install .
python -m synergesis_compare --provider demo --output ./comparaison-controle
```

Le dossier doit être nouveau. Le mode `demo` est un parseur programmé qui lit
les valeurs des fixtures : ce résultat vérifie le banc d'essai et ne démontre
aucun gain pour un LLM. Le rapport porte explicitement cette indication.

## Mesurer le vrai modèle local, s'il est servi par Ollama

Le raccordement Mistral réalisé sur le PC n'est pas automatiquement supposé
compatible avec Ollama. Cette commande s'applique uniquement si Ollama y sert
déjà le modèle choisi. Aucun modèle n'est téléchargé ou entraîné par le test.
Utiliser le nom exact du modèle installé, par exemple `mistral` si c'est son nom :

```bash
python -m synergesis_compare --provider ollama --model mistral --repeats 3 --output ./comparaison-mistral
```

Chaque répétition comporte au plus 18 appels ; trois répétitions en comportent
54. L'adaptateur envoie du texte à `127.0.0.1:11434/api/chat`, avec température
zéro, seed fixe, limite de génération de 512 tokens et réponse JSON. `--port`
permet de choisir un autre port local. Pas de proxy, redirection, outils ni
consultation du Web. Un appel expire après 60 secondes ; les échecs sont comptés,
pas transformés en réussites. La [documentation officielle Ollama](https://docs.ollama.com/api/chat)
décrit cet endpoint. Le modèle sélectionné peut avoir sa propre configuration
ou utiliser un service distant : le banc d'essai n'atteste pas son matériel ni
ses poids. Pour un essai réellement hors réseau, choisir un modèle local.

Si le Mistral du PC utilise un autre serveur, brancher son adaptateur existant :

```python
from pathlib import Path
from synergesis_benchmark import run_comparison

# make_backend() crée à chaque appel le même modèle et les mêmes réglages.
# L'objet expose reply(messages) -> str, sans outils ni historique implicite.
report = run_comparison(
    Path("comparaison-autre-serveur"), make_backend,
    {"provider": "adaptateur-local", "model": "nom-exact", "scripted_demo": False},
    repeats=3,
)
```

## Lire les résultats

`report.json` contient les questions, réponses brutes, valeurs synthétiques
attendues, IDs acceptés, messages exacts envoyés, erreurs de format, réponses
fausses, citations inventées, abstentions et durées. Les journaux de chaque
conversation Syn permettent de retrouver ses reçus. Aucune donnée personnelle
réelle n'est nécessaire. Le rapport est conservé localement.

Comparer d'abord `syn` à `matched_context`. Si les réponses sont équivalentes,
le gain observé face au modèle seul vient du contexte retrouvé. L'intérêt à
évaluer ensuite est la persistance, les traces et leur coût pratique. Un meilleur
score face à la question seule ne prouve pas un meilleur raisonnement.

Le temps de préparation du profil et des documents est consigné séparément du
temps de chaque condition. Les caractères et octets des messages sont des
mesures de volume, pas une estimation fiable du prix ou des tokens facturés.
Le modèle seul alterne avant/après Syn ; le contexte identique doit être rejoué
après Syn, ce qui peut favoriser le cache du fournisseur. Les durées incluent
des variations de chargement et ne suffisent pas à attribuer un surcoût précis.
Les IDs et chemins locaux peuvent varier entre runs malgré la seed fixe.

Le JSON strict mesure aussi le respect du protocole. Six exemples ne permettent
pas une conclusion générale : répéter avec d'autres seeds et examiner les
échecs. Ce premier lot ne teste ni modification de code ni auto-amélioration.
Le contrôle simulé est exécutable ici ; la mesure du Mistral du PC doit être
exécutée sur ce PC avec son serveur accessible.
