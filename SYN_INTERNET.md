# Recherche Internet depuis la conversation

Cette version raccorde réellement arXiv à `/web`, sans clé API. Elle consulte
les métadonnées et résumés scientifiques ; elle ne parcourt pas tout le Web,
ne lit pas les PDF et ne prouve pas les conclusions des publications.

Après installation de cette branche, avec Ollama et un modèle déjà présents :

```bash
python -m synergesis_chat --provider ollama --model mistral \
  --internet --profile ./profil-utilisateur --output ./session-internet-1
```

Dans la conversation :

```text
/web quantum gravity
```

Utiliser des mots-clés courts, de préférence anglais : arXiv cherche l'expression
exacte, pas une question reformulée automatiquement. Trois résultats au maximum
sont affichés avec titre, URL, date de consultation et extrait. La publication est
également datée dans le reçu. Le modèle reçoit un contexte borné pour une synthèse
française ; seuls certains extraits peuvent y tenir. Les sources affichées ne
prouvent pas que la synthèse du modèle est correcte.

Seule la requête explicite est envoyée à arXiv. Les souvenirs et l'historique ne
sont pas envoyés au moteur de recherche. Les extraits pertinents sont en revanche
transmis au fournisseur de conversation choisi, y compris OpenAI si ce mode est
sélectionné. Les commandes et recherches restent déclenchées par l'utilisateur.

Les reçus sont conservés dans le profil Glyph. Après redémarrage avec le même
profil et un nouveau dossier de session, une question contenant les mots-clés
peut retrouver ces instantanés sans nouveau téléchargement. Ils peuvent être
périmés. L'empreinte porte sur l'extrait enregistré, pas sur le PDF entier ; le
numéro de ligne 1 désigne cet extrait normalisé.

## Bornes

Trois tentatives par instance de profil, partagées avec `/initiative`, y compris
les échecs. Ce budget se réinitialise au redémarrage ; le journal a son propre
quota persistant. Une interruption laisse une tentative en cours et bloque sa
relance automatique. Pas de nouvelle tentative HTTP ni redirection ; destination
HTTPS fixe `export.arxiv.org`, réponse maximale 256 Kio. Timeout réseau de
15 secondes et budget coopératif de 20 secondes, sans garantie d'échéance absolue.
Une absence de résultats et une panne sont distinctes. Aucun échec n'est remplacé
par des résultats fictifs. Entrée vide n'arrête plus immédiatement le dialogue ;
le plafond global de commandes reste appliqué.

## Essai exécuté

Le 4 octobre 2026, une recherche réelle `/web quantum` a reçu trois notices arXiv,
dont `https://arxiv.org/abs/2610.02192v1`. Reçu local :
`g:94ac0293e6dcdcbf69c6d5a3f0f64554`.
La collecte a utilisé le réseau réel ; la réponse de conversation de cet essai
était le backend de démonstration. Aucun essai Mistral réel n'est revendiqué ici.
