# SYN — Prisme YouTube · prototype 0.1

Un premier compagnon dans YouTube sur ordinateur. Tu choisis les sujets, réduis ceux qui t’ennuient et laisses plus de place aux chaînes que Prisme n’a pas encore rencontrées. Un panneau explique sa sélection et te laisse la corriger.

**État : prototype à installer et à essayer sur ton navigateur. Il n’est pas installé sur ton ordinateur et n’a pas encore été validé sur ton véritable fil YouTube.** Les tests locaux passent ; voir VERIFICATION.md. Ce paquet ne modifie pas le dépôt Synergesis ni le skill SYN — Prisme déjà installé dans ChatGPT.

## Installation Windows simplifiée

Après extraction complète du paquet, double-cliquer **Installer-Windows.cmd**. Ce lanceur copie uniquement les fichiers de l’extension dans `%LOCALAPPDATA%\SynPrisme\extension-v0.1`, copie ce chemin dans le presse-papiers et ouvre la page des extensions dans Chrome (ou Edge si Chrome est absent). Il ne requiert pas Python.

La validation du navigateur reste nécessaire : **Mode développeur → Charger l’extension non empaquetée → coller le chemin avec Ctrl+V**. Le lanceur ne modifie pas les politiques du navigateur et ne prétend pas installer silencieusement l’extension. Ce lanceur Windows n’a pas pu être exécuté dans l’environnement Linux de développement.

## Installer la partie YouTube

Cible initiale : Chrome sur ordinateur, ou navigateur Chromium compatible avec les extensions Manifest V3. Firefox, applications de télévision, Instagram et YouTube Android ne sont pas pris en charge dans cette version.

1. Extraire entièrement l’archive dans un dossier que tu garderas.
2. Dans Chrome, ouvrir `chrome://extensions` puis activer **Mode développeur**.
3. Cliquer **Charger l’extension non empaquetée** et sélectionner le sous-dossier **extension** (celui qui contient manifest.json).
4. Ouvrir ou recharger YouTube. Le panneau **SYN / PRISME** apparaît en bas à droite. Le bouton **⚙** ouvre tes réglages. Le bouton **−** réduit le panneau.

Pas de clé ni de serveur requis pour le premier essai : le tri local et les traces fonctionnent seuls.

### Ce que tu peux régler

- **Explorer** : mots ou expressions dans les titres et noms de chaînes, séparés par des virgules.
- **Moins voir** : sujets ou noms de chaînes dont tu veux réduire la priorité dans la sélection SYN.
- **Chaînes nouvelles** : bonus de classement pour les chaînes absentes des traces locales précédentes. Ce réglage ne mesure pas la diversité idéologique et ne garantit pas une proportion de nouveautés.
- **+ Pour moi / − Moins / Annuler** : correction explicite pour cette vidéo, réversible. Les avis ne sont pas généralisés automatiquement à toute une communauté ou opinion.

Le panneau classe jusqu’à cinq cartes reconnues parmi celles visibles à l’écran. Il ne change pas le classement du serveur YouTube, ne bloque pas les vidéos et ne découvre pas encore de vidéos extérieures au fil. Le classement local repose sur des mots-clés : il ne peut pas mesurer la véracité, l’expertise ou la qualité scientifique d’une vidéo.

## Activer l’IA automatique (facultatif)

Le relais Python fourni relie l’extension soit à **Ollama installé sur ton ordinateur**, soit à **l’API OpenAI**. Ce n’est pas la session ChatGPT de ton abonnement et il ne récupère pas tes conversations. Le relais n’invoque pas automatiquement tes skills ChatGPT.

Prérequis : Python 3.10 ou plus. Aucune bibliothèque Python supplémentaire n’est requise. Le nom du modèle doit être renseigné explicitement. La faisabilité d’un modèle local dépend de ta machine ; aucun modèle n’est téléchargé par ce paquet.

### Modèle local Ollama

Après installation d’Ollama et d’un modèle local compatible avec les sorties structurées, lance dans le dossier du paquet :

```text
python bridge/server.py --provider ollama --model NOM_EXACT_DU_MODELE
```

Remplace `NOM_EXACT_DU_MODELE` par celui indiqué par `ollama list`. Selon le système, la commande Python est `python3` ou `py` plutôt que `python`. Le relais appelle uniquement l’API locale d’Ollama sur 127.0.0.1:11434. Choisis un modèle local, pas un modèle relayé dans le cloud, si tu veux que le traitement reste sur ta machine.

### API OpenAI

Définis `OPENAI_API_KEY` dans l’environnement du terminal, puis lance :

```text
python bridge/server.py --provider openai --model NOM_DU_MODELE_ACCESSIBLE
```

Le modèle doit prendre en charge l’API Responses et les sorties structurées. La disponibilité dépend de ton compte. **Les appels API utilisent une facturation distincte ; ce prototype ne se sert pas de ton abonnement ChatGPT.** La clé reste dans l’environnement du relais, jamais dans l’extension. Ne nous l’envoie pas dans le chat.

### Raccorder une fois le relais lancé

1. Copier le **code de raccordement** affiché dans le terminal du relais.
2. Dans les réglages SYN, ouvrir **Analyse IA automatique**, coller ce code, cocher **Autoriser l’analyse automatique**, puis **Appliquer**.
3. Cliquer **Tester le raccordement enregistré**. Ce test vérifie le relais, pas la disponibilité effective du modèle.
4. Ouvrir une vidéo YouTube. L’analyse apparaît automatiquement après quelques secondes et le temps de réponse du modèle. En cas de problème temporaire, cliquer **Relancer la lecture IA**.

Garder le terminal du relais ouvert pendant l’utilisation. Le code change à chaque démarrage : recopier le nouveau code dans les réglages. Ctrl+C arrête le relais. La collecte locale peut être mise en pause séparément depuis les réglages.

## Ce qui est effectivement analysé

- Pour le tri du fil : titre et chaîne des cartes reconnues dans la partie visible de la page.
- Pour l’IA : titre, chaîne, description présente dans la page (4 000 caractères maximum), et texte de transcription déjà chargé par YouTube (12 000 caractères maximum).
- Pour obtenir une transcription quand YouTube la propose, ouvrir son panneau **Afficher la transcription**. L’extension ne contourne pas les restrictions et ne transcrit pas le son.
- Sans transcription, le résultat le signale. L’IA propose un intérêt possible et une question à vérifier ; elle n’a ni regardé la vidéo entière ni vérifié le web.
- Aucun traitement de l’image, du son, des commentaires ou des messages privés. Les Shorts peuvent être reconnus dans le fil, mais leur lecteur n’est pas analysé automatiquement.

Une réponse peut être erronée. L’interface affiche la base textuelle disponible et ne donne pas de note de vérité. Une recherche Ground News / SYN Prisme approfondie demeure une opération distincte.

## Le recul sur ton fil

Le bilan donne le nombre d’observations vidéo/jour, les chaînes rencontrées, la part de la chaîne la plus présente et tes corrections. Il décrit **les cartes visibles détectées**, pas ton temps de visionnage ni l’ensemble des suggestions YouTube. Une vidéo rencontrée plusieurs jours peut compter une fois chaque jour. La page courante seule ne prouve pas un visionnage.

Les traces restent dans le stockage local du navigateur : 30 jours et 800 observations maximum. Jusqu’à 800 avis explicites et 60 analyses mises en cache sont conservés. Le relais conserve au plus 60 résultats en mémoire jusqu’à son arrêt. Il n’écrit pas de journal de navigation sur disque. Le bouton **Exporter mes traces** crée un JSON sans code de raccordement ni clé API ; ce fichier peut être fourni à SYN pour une méta-analyse plus poussée. **Effacer mes traces** supprime les observations, avis et analyses du navigateur ; arrêter le relais pour vider ses résultats en mémoire.

Quand l’IA est activée, les textes de la vidéo et tes critères sont transmis au moteur choisi. Rien n’est transmis au moteur en mode local sans IA. Les requêtes déjà parties peuvent se terminer après une mise en pause. Le relais limite à une inférence à la fois et 20 tentatives par heure par lancement (réglable par `--limit`, maximum 100). Les échecs comptent. Cette limite n’est pas un plafond financier ; régler aussi les contrôles de dépense du fournisseur si tu utilises son API.

## Limites et prochaines étapes

- Interface et extraction à valider sur le vrai YouTube ; les sélecteurs peuvent casser quand YouTube change sa mise en page.
- Ni recherche de contrepoints hors du fil, ni vérification factuelle multisource, ni apprentissage sémantique des avis dans cette V0.
- Instagram nécessitera un raccordement distinct. Ne pas mélanger automatiquement ses usages à ceux de YouTube : les critères pourront être propres à chaque plateforme.
- Une télévision ou une application native nécessitera une autre intégration ; cette extension couvre le navigateur d’ordinateur.

## Sources techniques consultées le 27 octobre 2026

- Chrome, scripts de contenu : https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
- Chrome, permissions : https://developer.chrome.com/docs/extensions/develop/concepts/declare-permissions
- Chrome, motifs d’URL : https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns
- Ollama, sorties structurées : https://ollama.com/blog/structured-outputs
- OpenAI, sorties structurées : https://developers.openai.com/api/docs/guides/structured-outputs
