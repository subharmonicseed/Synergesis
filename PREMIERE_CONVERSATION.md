# Première conversation avec Syn

Cette version ajoute une conversation texte dans le terminal. Le modèle propose
uniquement du texte. Syn passe sa remise au programme par sa boucle AEGIS,
prédiction, REALITY et journalisation. Aucun outil, commande shell ou navigation
Internet n'est accessible au modèle dans ce mode.

**Le contrôle REALITY constate la remise du texte dans une boîte mémoire locale.**
Il ne certifie ni la vérité de la réponse, ni son utilité, ni sa lecture à l'écran.
Le score de livraison ne constitue pas un apprentissage de connaissances vraies.
Les propos du modèle ne deviennent pas automatiquement des faits.

L’appel au fournisseur intervient pendant le raisonnement, avant AEGIS et la
prédiction de livraison. Son autorisation vient du mode API explicitement choisi
par l’opérateur ; ses bornes viennent de l’adaptateur HTTP. AEGIS ne contrôle
pas cet appel et le budget API ne constitue pas un budget financier SYN-RISK.

## Essayer sans clé

Utiliser cette branche du projet, sous Linux, macOS ou Ubuntu dans WSL sous
Windows, avec Python 3.11 ou 3.12. Depuis son dossier :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m synergesis_chat --output ./essai-syn
```

Écrire un message puis Entrée. `/quitter` termine la session. Par défaut, c'est une
**démonstration programmée sans modèle et sans réseau** : la réponse répète le
message et permet de tester la boucle. Pour un essai en une seule commande :

```bash
python -m synergesis_chat --output ./essai-syn-un-tour --message 'Bonjour Syn'
```

Choisir un nouveau dossier à chaque lancement. Le programme conserve les échanges
et les événements dans ses journaux locaux ; utiliser un dossier personnel.
Il ne recharge pas automatiquement une ancienne conversation.

## Discuter avec un modèle local Ollama

Avec Ollama déjà lancé et un modèle déjà installé sur la même machine, utiliser
son nom exact (visible dans `ollama list`) :

```bash
python -m synergesis_chat --provider ollama --model mistral \
  --profile ./profil-syn --output ./conversation-locale-1
```

Remplacer `mistral` si le modèle porte un autre nom. Syn contacte uniquement
`http://127.0.0.1:11434/api/chat` ; `--port` permet un autre port local. Sous WSL
ou Docker, le serveur doit être joignable sur cette adresse depuis l'environnement
où Syn tourne. Syn ne lance pas Ollama, ne télécharge aucun modèle et ne demande
aucune clé API. Utiliser un modèle local : cette adresse ne garantit pas à elle
seule que le serveur Ollama n'est pas configuré pour appeler un service distant.

La conversation demande du texte ordinaire ; le banc `synergesis_compare`
conserve son format JSON. Les appels n'utilisent ni proxy, ni redirection, ni outil.
Chaque tour effectue un appel, sans relance automatique ; 10 tours par défaut,
ajustables de 1 à 20 avec `--max-turns`. La sortie est plafonnée à 512 tokens
demandés et 16000 caractères acceptés. Le délai de 60 secondes est un timeout
réseau, pas une garantie de durée totale maximale.

Pour vérifier la mémoire explicite, saisir `/memoriser Mon atelier est à Jarrie.`,
puis `/quitter`. Relancer avec le même `--profile` et un nouveau dossier
`--output`, puis saisir `/memoire Jarrie`. Cette commande locale relit la déclaration
sans appeler le modèle. Une question comme « Où est mon atelier ? » transmet les
souvenirs correspondants au modèle ; leur présence ne garantit pas sa réponse.
Les commandes `/question` et `/initiative` restent celles de
[l'initiative locale](SYN_INITIATIVE_V0.md).

Les tests de ce raccordement utilisent un serveur HTTP local contrôlé, pas Mistral.
Ils vérifient le format texte, l'historique, la transmission des souvenirs, les
traces, le plafond de tours et l'arrêt sur erreur sans afficher le corps serveur.
L'essai avec le véritable modèle du PC reste à effectuer.

## Brancher un modèle OpenAI

Choisir un identifiant de modèle compatible Responses API et accessible sur son
compte API. Remplacer `IDENTIFIANT_MODELE` dans cette commande :

```bash
python -m synergesis_chat --provider openai --model IDENTIFIANT_MODELE --output ./conversation-syn
```

Le terminal demande une **clé API neuve en saisie masquée**. Ne pas la mettre dans
un fichier du dépôt, dans la commande ou dans une conversation. En usage automatisé,
l'application accepte la variable `SYN_OPENAI_API_KEY`. Elle ne charge aucun `.env`.
L'abonnement à une application de conversation ne prouve pas que le compte API
est configuré : vérifier l'accès au modèle et le budget du compte fournisseur.

Ce mode envoie les messages et l'historique au fournisseur. Il effectue au maximum
un appel par tour, avec 10 tours par défaut, ajustables par `--max-turns` de 1 à 20.
Les tentatives échouées comptent aussi et il n'y a aucune relance automatique.
La limite de sortie est de 1024 tokens par appel ; ce n'est pas un plafond en euros.
L'historique en caractères et les corps HTTP ont aussi des bornes. Si l'historique
ne tient plus avec la réserve de réponse, le programme s'arrête sans le tronquer.

La requête utilise `store: false`, sans outils ni streaming. Cette option ne
constitue pas à elle seule une promesse de conservation nulle chez le fournisseur.
Les réponses incomplètes, erreurs, refus et sorties inattendues arrêtent le tour.
Le programme ne montre ni les corps d'erreur HTTP, ni la clé.

## Ce qui reste à valider

Les tests automatisés remplacent le fournisseur par des réponses contrôlées.
**Aucun appel réel avec une clé n'a été effectué pour ce lot.** Il reste à essayer
une session API sur la machine de Gabriel, avec son modèle et son budget, puis à
évaluer la pertinence des réponses sur des tâches concrètes.

La conversation est textuelle et tour par tour : pas encore de voix, streaming,
interface graphique ou activité autonome prolongée. Le backend OpenAI n'est pas
un modèle local ; le mode Ollama ci-dessus utilise le même protocole
`reply(messages) -> str`. Le ModelContextBridge de la PR précédente reste un outil de
préparation de dossiers de développement, distinct de cette conversation.

Les droits sur les autres outils, la reprise après coupure et le remplacement
de l'ancien `main` restent des étapes séparées. Les anciens points partiels du
bilan d'audit ne deviennent pas résolus grâce à ce mode conversation.

## Références de l'adaptateur

Format vérifié dans la [documentation officielle de génération de texte](https://developers.openai.com/api/docs/guides/text)
le 29 septembre 2026 : requête Responses, messages en entrée et extraction du
texte dans les éléments `output` de type `message`. Le programme analyse les
éléments de sortie, sans supposer que le texte est le premier élément.

## Validation de cette version

800 tests passent localement sous CPython 3.12, dont 66 nouveaux tests de
conversation, terminal et fournisseur simulé. Deux avertissements de dépréciation
proviennent des dépendances existantes. La vérification inclut l'absence de
livraison, une réponse altérée, un ancien tour, les limites d'historique et
d'appels, ainsi que les refus, redirections et réponses HTTP incomplètes.
Le délai HTTP est un timeout d'inactivité avec contrôles entre blocs, pas une
garantie de durée maximale absolue. La CI de la PR conserve les reçus par version
Python ; elle n'utilise aucune clé API.
