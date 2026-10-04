# Dialogue Mistral et intégration Internet

Cette branche part de PR51 (`91d5d7b86f7f6b8c29af7e9d963623bb77662cde`) et intègre localement PR53 (`e0fa93d51e87551469f6e41f23d23ae6b2e18f3b`). Elle conserve les corrections locales du dialogue, du profil et du contrôle des reçus. Aucune fusion GitHub automatique.

## Lancer

Dans Linux ou Ubuntu sous WSL, avec les dépendances existantes et le modèle déjà importé :

```bash
python -m synergesis_chat --provider ollama --model syn-mistral-import:latest \
  --profile /chemin/profil-persistant --output /chemin/nouvelle-session --internet
```

Le dossier de session doit être nouveau. Le profil reste le même à chaque lancement. Une ligne vide est ignorée ; `/quitter` et la fin du flux ferment proprement. Les commandes `/memoriser`, `/memoire`, `/question` et `/initiative` conservent leur fonctionnement explicite. Le programme ne transforme pas automatiquement les réponses du modèle en souvenirs ou faits.

`/web quantum gravity` consulte arXiv, affiche les titres et URL puis fait synthétiser les extraits par le modèle local. Trois recherches au maximum par instance de profil, partagées avec `/initiative`. Seule la requête explicite est envoyée à arXiv. Le modèle ne déclenche aucune recherche autonome. Voir également [SYN_INTERNET.md](SYN_INTERNET.md).

Pour un document local, ajouter `--document /chemin/fiche.md`, puis saisir :

```text
/question MOT-IDENTIFIABLE
/initiative
Question sur MOT-IDENTIFIABLE, avec la source ?
```

Le document est réellement lu seulement lors de `/initiative`. Après relance, les extraits enregistrés peuvent être retrouvés sans relire le fichier. Ce sont des instantanés : une modification ultérieure du document ne les actualise pas automatiquement.

## Corrections et preuves réelles du 4 octobre 2026

Le même Mistral 7B Instruct v0.3 Q4_K_M, importé dans Ollama, a été interrogé avant correction avec et sans le contexte ajouté par Syn. Avec un profil vide, le paquet JSON et ses avertissements provoquaient un refus de répondre à « bonjour Syn » ; sans ce paquet, le modèle répondait. La ligne vide arrêtait la CLI avant le message suivant. Les reçus de ces deux essais et les paquets HTTP réels sont conservés sur le PC.

Le dialogue utilise désormais un contexte court uniquement quand des données pertinentes existent. Les articles grammaticaux ne suffisent plus à sélectionner un souvenir ; les questions en attente sont filtrées sur la demande. Les références M/D/W sont stables dans une session et leur mapping est journalisé. Les empreintes, dates, reçus et portée des extraits restent dans le paquet complet et dans les références du programme. Les comparaisons JSON gardent leur protocole antérieur. Le délai socket de conversation est borné à 180 secondes pour le modèle sur CPU ; le benchmark conserve sa limite de 60 secondes.

Les consignes de dialogue demandent une réponse française normale sans citation quand aucun extrait n'est disponible. Leur formulation anglaise a été essayée avec ce Mistral : à « bonjour Syn », réponse réelle « Bonjour ! Comment ça va ? ». Aucun texte de salutation n'est codé en dur. Avec ces mêmes consignes finales, une relance retrouve `CORAIL-7C91 [D2]` et une question sur la masse reçoit une absence explicite d'information.

Essais effectués avec des profils de test distincts du profil utilisateur :

- Une fiche fictive contient le code `CORAIL-7C91` pour `LANTERNE-Q93`. `/question` puis `/initiative` lisent réellement le fichier ; Mistral répond `CORAIL-7C91 [D2]`, référence de la ligne 2. SHA-256 du document : `7656ef0c0f5b3ff9636fdda6c26274472eb364ffd6cb3947571d602801126026`.
- Un nouveau processus, même profil et nouvelle session, retrouve le code et le reçu `g:5ded93752c9ee2528274f0df52551f8a`. La question ne contient pas le code ; aucun `--document` ni `/initiative` n'est réintroduit dans cette relance.
- À « Quelle est la masse… ? », réponse réelle : « La masse de l'objet fictif LANTERNE-Q93 n'est pas spécifiée dans les extraits fournis. »
- Mistral seul sans le fait s'abstient, mais ajoute une référence `[D1]` non fournie : limite observée du modèle. Avec exactement le même paquet de messages que Syn, il donne exactement la même réponse `CORAIL-7C91 [D2]`. Aucun bénéfice de raisonnement n'est établi par cette comparaison ; recherche et persistance rendent l'information accessible.
- `/web quantum gravity` a réellement collecté trois notices : [Floquet-Universal Hamiltonian Simulation](https://arxiv.org/abs/2610.01878v1), [DSSYK, open ASEP/TASEP and 2d dilaton gravity at strong coupling](https://arxiv.org/abs/2610.01790v1), [Algebraic structure in holographic tensor networks](https://arxiv.org/abs/2610.00478v1). Deux extraits bornés ont été transmis à Mistral, qui cite W1/W2. Cycle de remise : `g:8bd5619434f5a5b4d5898e2838655c8c`. Un autre processus a réutilisé les premières notices sans réseau.

Le premier essai de synthèse web avait expiré à 60 secondes ; ses sources restaient conservées. Les versions des fichiers et messages effectivement exécutés sont enregistrées pour chaque essai. Les contrôles unitaires et les serveurs contrôlés sont distingués des essais Mistral réels. Le script [scripts/record_real_chat.py](scripts/record_real_chat.py) enregistre un parcours réel, délègue au transport original et conserve les réponses et reçus ; il ne remplace pas le modèle par une simulation.

## Validation et limites

La suite complète finale sur Ubuntu/Python 3.12.3 a donné 899 tests réussis : deux avertissements de dépréciation FastAPI/Starlette et un avertissement d'écriture du cache pytest sur le montage Windows. Le défaut de cache des reçus hérité de PR51 est corrigé avec les octets effectivement parsés et sept régressions. Une revue indépendante a détecté le risque de réattribuer D1/W1/M1 entre les tours ; il a été corrigé avec un registre par session et des tests. La relecture finale n'a trouvé aucun problème bloquant.

Les notices arXiv et leurs extraits ne sont ni des PDF complets ni des conclusions scientifiquement vérifiées. Trois notices peuvent être conservées mais seulement deux extraits sont transmis dans le paquet courant ; les omissions et troncatures restent explicites. Les réponses peuvent être bavardes, extrapoler et présenter des capacités de façon imprécise : le texte du modèle est non vérifié, même si ses références se résolvent. L'essai web ne valide pas l'affirmation de Mistral selon laquelle les articles ne contiendraient aucun résultat prouvé. REALITY vérifie la remise du texte au programme, pas sa vérité. Le timeout socket n'est pas une échéance absolue.

Les preuves détaillées du PC se trouvent dans `outputs/MistralExperienceDemo/` : paquets HTTP, texte réel, empreintes de code, PID distincts, profils fictifs et vérification des références. Elles ne contiennent pas les souvenirs du profil utilisateur. Aucun nouveau modèle, achat, clé API ou service de modèle cloud n'a été utilisé.
