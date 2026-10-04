# Interface locale de Syn

Une interface française légère, servie par Python sur `127.0.0.1` uniquement. Elle réutilise la conversation auditée, le profil persistant, la recherche documentaire et arXiv existants. HTML, CSS et JavaScript sont fournis localement ; aucune dépendance frontend, CDN, télémétrie, clé API ou modèle supplémentaire.

## Lancer et arrêter

Sous Linux/WSL, depuis les sources installées, avec les dépendances et un modèle Ollama déjà disponibles :

```bash
python -m synergesis_ui --profile /chemin/profil --root /chemin/interface \
  --model NOM-EXACT-DU-MODELE --port 8765 --ollama-port 11434 --internet
```

Ouvrir `http://127.0.0.1:8765`. Sous Windows, utiliser WSL : le moteur et ses verrous sont POSIX. Le lanceur PC `scripts/open_syn.ps1` et son raccourci « Ouvrir Syn » vérifient l'installation existante de Gabriel, les sources installées et l'identité du serveur avant de réutiliser une instance. Un port occupé par une application différente n'est pas récupéré en arrêtant son processus. Le processus WSL du service reste en arrière-plan, avec des journaux de démarrage distincts.

Le bouton **Arrêter l'application** ferme proprement le service et sa conversation ; Ollama reste disponible. Une opération en cours doit finir avant l'arrêt. Le serveur peut aussi être arrêté par Ctrl+C dans son terminal Linux. Le profil, les documents importés et les journaux restent conservés.

## Parcours

- Conversation : Entrée envoie, Maj+Entrée insère une ligne, les messages vides sont ignorés. Un indicateur indique le traitement réel ; la réponse apparaît une fois complète, sans streaming simulé.
- Mémoire : ajouter explicitement un souvenir, consulter la liste ou rechercher un texte. Les souvenirs sont des déclarations utilisateur non vérifiées. Une nouvelle conversation ou un redémarrage conserve le profil.
- Document : importer un fichier UTF-8 `.txt` ou `.md`, choisir ce document et poser une question. Le moteur lit la copie importée et enregistre ses extraits, lignes et empreinte. La demande est limitée au reçu de cette lecture : les souvenirs, autres documents et ancien dialogue ne servent pas de preuve pour ce document.
- **Recherche scientifique** : envoyer des mots-clés à arXiv, puis faire synthétiser les extraits par le modèle local. Ce n'est pas une recherche sur tout Internet. Seule la requête scientifique est envoyée à arXiv.
- Sources : titres, URL ou document, extraits, dates et reçus des sources réellement consultées. Les étiquettes distinguent source consultée, fournie au modèle et citée par sa réponse. Une correspondance de référence ne certifie pas la justesse du texte.
- Détails : reçu de remise, références, session et chemins de journaux. Le modèle choisi et le dernier modèle effectivement renvoyé par Ollama sont distingués ; disponibilité du serveur Ollama et présence du modèle sont affichées séparément.

## Cycle de vie et limites

Un worker unique possède le contexte moteur, de son ouverture à sa fermeture. Les requêtes HTTP lisent des instantanés et soumettent une opération à la fois. Les mutations ont un identifiant unique ; rejouer exactement un identifiant ne refait pas l'opération. Un identifiant utilisé avec un autre contenu est refusé. La page verrouille ses contrôles avant tout envoi ou lecture de fichier. Une erreur libère les contrôles ; une demande interrompue n'est jamais relancée automatiquement.

Les limites existantes sont conservées : vingt tentatives du modèle par conversation, contexte de 32 000 caractères avec place réservée pour la réponse, 32 commandes de profil et trois recherches partagées entre documents et arXiv. Une tentative de modèle échouée consomme un tour. Une recherche interrompue ne se rejoue pas automatiquement. Une nouvelle conversation crée un dossier de journaux neuf et réinitialise ses budgets, en conservant le profil.

Au maximum seize documents de 256 Kio sont importés. Seuls leur nom simple et leur contenu sont acceptés : aucun chemin provenant du navigateur n'est utilisé. Les copies ont des identifiants générés par le serveur ; les fichiers originaux ne sont pas modifiés. Les documents UTF-8 peuvent nécessiter une conversion depuis un autre encodage. Les PDF ne sont pas pris en charge.

Le délai socket Ollama est de 180 secondes ; la page attend jusqu'à quatre minutes avant de proposer une actualisation explicite de l'état. Sur CPU, les synthèses peuvent prendre plus d'une minute. Le délai socket ne constitue pas une échéance absolue.

## Protection locale et traces

Le service refuse les hôtes étrangers, les origines externes et les requêtes provenant d'autres sites. Un jeton aléatoire propre au lancement est obligatoire pour chaque mutation. Aucun CORS permissif. Les fichiers statiques ont des routes fixes, sans lecture de chemin arbitraire. Les requêtes et imports sont bornés. Les données du modèle, des documents et des sources sont rendues comme texte, sans exécution HTML. Les liens externes sont limités aux références HTTPS arXiv.

Un verrou de service empêche deux interfaces de partager simultanément le même profil ou dossier de service. Les journaux moteur sont conservés par conversation ; `transport.jsonl` conserve les requêtes et réponses HTTP réelles d'Ollama. Ces fichiers contiennent du texte de conversation et restent locaux. Utiliser un profil fictif distinct pour partager des preuves. REALITY vérifie la remise de la réponse au programme, pas sa vérité ni son utilité.

Les tests `test_syn_ui_backend.py` et `test_syn_ui_security.py` utilisent des fournisseurs contrôlés explicitement : ils vérifient les limites, la persistance, le ciblage documentaire, la concurrence et les protections HTTP. Ils ne démontrent pas la qualité du vrai Mistral. Les essais PC et leurs captures doivent être rapportés séparément.
