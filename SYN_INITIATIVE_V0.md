# Initiative v0 : mémoire explicite et questions persistantes

Ce lot raccorde au dialogue un profil persistant construit sur le journal Glyph
existant. Les souvenirs sont ajoutés explicitement par l'utilisateur et restent
des déclarations non vérifiées, avec leur référence. Les réponses du modèle ne
sont pas enregistrées automatiquement comme connaissances.

Le profil est distinct du dossier neuf de chaque conversation. Une nouvelle
session peut retrouver les souvenirs et les questions précédentes. Le modèle
reçoit un dossier borné de souvenirs pertinents, de questions et de reçus
documentaires pertinents déjà collectés ; ce dossier est
également enregistré dans les traces du tour. Le texte reste une donnée non fiable,
pas une autorisation ni une preuve de vérité. Ces étiquettes ne garantissent pas
que le modèle résiste à toute injection d'instructions.

## Essai sans clé

Installer cette branche dans un environnement isolé, puis :

```bash
python -m synergesis_chat --profile ./profil-syn --output ./session-1
```

Dans le terminal :

```text
/memoriser Le nom de mon atelier est Capelli à Jarrie.
/question Comment contrôler les réponses de Synergesis ?
/quitter
```

Relancer avec le même profil et un nouveau dossier de session :

```bash
python -m synergesis_chat --profile ./profil-syn --output ./session-2
```

```text
/memoire Jarrie
```

Le programme doit afficher la déclaration originale et sa référence, avant tout
appel au modèle. En mode démonstration, les réponses restent programmées. Le même
paramètre `--profile` peut être utilisé avec le backend OpenAI existant : les
souvenirs sélectionnés sont alors envoyés au fournisseur. Le backend Mistral
peut maintenant être sélectionné avec `--provider ollama --model mistral` et
le même `--profile`, si ce modèle est déjà disponible dans le serveur Ollama local.
Voir [le guide de conversation](PREMIERE_CONVERSATION.md) pour le port et les limites.

## Une prochaine étape effectivement exécutée

Choisir explicitement des documents texte, par exemple le guide de cette branche :

```bash
python -m synergesis_chat --profile ./profil-syn --output ./session-3 \
  --document ./PREMIERE_CONVERSATION.md --document ./SYN_AUDIT_STATUS.md
```

Les reçus pertinents peuvent ensuite être cités par le modèle dans un nouveau
tour, avec leur identifiant et les références de leurs extraits. Ce sont des
instantanés enregistrés : un document peut avoir changé depuis sa consultation.

La commande `/initiative` sélectionne la plus ancienne question en attente et
recherche des passages dans ces seuls documents. Elle affiche une trace et les
extraits retenus, avec empreinte du fichier et numéro de ligne. Il ne s'agit pas
d'une recherche Internet ou d'une synthèse scientifique. Les fichiers txt/md
sont bornés et les liens symboliques sont refusés. Il n'y a ni parcours récursif
de dossiers ni exécution des contenus. Des occurrences lexicales peuvent être
hors sujet : la pertinence et la vérité restent à évaluer.

Le résultat distingue présence de sources, absence de sources et échec. Une
question avec des extraits n'est pas marquée « résolue ». Les tentatives sont
inscrites avant lecture : une interruption laisse une tentative en cours à
examiner, sans relance automatique. Le choix du prochain objectif est une règle
explicite FIFO, pas une préférence subjective du modèle.

## Bornes et limites

Maximum trois étapes de recherche par instance de profil, jusqu'à seize documents
explicitement choisis. Le journal et ses événements ont des quotas. Le contexte
transmis au modèle est limité à 4096 caractères ; trop peu de place dans la
conversation arrête le tour avant appel au fournisseur. Les plafonds en caractères
ne sont pas des comptages exacts de tokens. Les commandes locales ne déclenchent
pas d'appel au modèle. Le terminal borne aussi le nombre total de commandes.

Le dossier de profil appartient à l'opérateur et ses ancêtres sont de confiance.
Les verrous et la chaîne Glyph contrôlent les écritures coopératives et certaines
altérations ; ils ne constituent pas une attestation matérielle ni une protection
contre un acteur capable de réécrire entièrement les données et leurs empreintes.
Les souvenirs, questions et extraits sont conservés dans les journaux locaux.

Pas encore de service en arrière-plan, d'Internet automatique, d'entraînement,
de volonté subjective ou d'amélioration autonome du code. Cette v0 démontre la
continuité entre sessions et une étape bornée qui choisit une question puis
rapporte ses sources. Elle n'active pas automatiquement les missions du
SynGoalManager ni les recherches de ROAM.

## Validation du lot

827 tests passent localement sous CPython 3.12, dont 27 nouveaux tests de profil
et d'intégration au dialogue. Deux avertissements de dépréciation préexistants.
Les essais adverses couvrent altération du journal, quota avant lecture,
interruption laissant une tentative en cours, sources absentes/invalides,
liens symboliques, empreintes et bornes de sérialisation.

Un essai CLI dans plusieurs processus distincts a enregistré « Mon atelier est à
Jarrie. », puis retrouvé exactement la même déclaration et son identifiant après
redémarrage. Une question QUOTA-EXEMPLE a retrouvé la première ligne d'un document
contrôlé, empreinte `8440610793cad9a8ea1a50bfff04e500f584acd76cbb0dc6789ef890c07ecc7b`.
Son reçu `g:98c365dda6dcf8360e1d90b78285bb67` a été relu dans un nouveau processus
et inclus dans un dossier de contexte de 933 caractères. Le journal contient
quatre événements vérifiés. Ces données sont une fixture de test, pas une
recherche sur un sujet scientifique. Aucun appel LLM réel effectué dans ce lot.
