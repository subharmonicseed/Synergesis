# Syn et God’s Eye View : parcours sismique vérifié

Cette copie reprend Syn `0b92fce71f96cb6dd912d542a86832bf8234279e` (PR #50,
`feat/model-comparison`) et GEV `aa16b7c3b0166a89d8c7a6089e0aff53a22faaee`.
Elle conserve les autres installations, conversations et modèles.

## Sur le PC de Gabriel

Dans PowerShell, lancer le fichier `LANCER_GODS_EYE_PC.ps1` de cette copie :

```powershell
& "C:\Users\Lenovo\Documents\Codex\2026-09-30\github-plugin-github-openai-curated-remote-2\outputs\Synergesis-GodsEye\LANCER_GODS_EYE_PC.ps1"
```

Attendre le message `Globe` dans le terminal, puis cliquer **Relire le journal**
sur la page ouverte. Choisir un événement pour déplacer la vraie caméra du globe.
Poser ensuite sa question dans le terminal Syn ; relire le journal pour afficher
sa réponse. `/actualiser` effectue une nouvelle lecture autorisée du même intervalle.
`/quitter` ferme Syn et le serveur du globe ; la mémoire reste conservée.
Trois lectures de projection sont possibles par page ; recharger la page renouvelle
ce budget local. Il n’y a aucun suivi automatique ni clé API.

La mémoire géographique est dans `/home/gabriel/synergesis-geo-noto` sous Ubuntu.
Le lanceur utilise Python isolé `/home/gabriel/syn-geo-venv/bin/python`, le Mistral
llama.cpp déjà présent sur le port 8080 et Node portable 24.21.0. Le lanceur ne
démarre pas Docker et ne télécharge rien. S’il signale un port déjà occupé, fermer
la session précédente. Ses paramètres permettent de changer chemins et distribution.

## Résultat réellement contrôlé

Le 3 octobre 2026, une requête USGS limitée à 12 résultats a trouvé deux événements
dans la région 36–38°N, 135–138°E, du 1 au 3 janvier 2024, magnitude ≥ 6 :

| Identifiant USGS | Magnitude | Date UTC | Lieu dans le catalogue |
|---|---:|---|---|
| us6000m0xl | 7,5 mww | 2024-01-01 07:10:09.476 | 2024 Noto Peninsula, Japan Earthquake |
| us6000m0xm | 6,2 mb | 2024-01-01 07:18:41.584 | 8 km SW of Anamizu, Japan |

Premier lancement : deux nouvelles observations. Second processus : deux doublons,
les mêmes glyphes retrouvés, aucune observation supplémentaire. Deux questions
existent dans l’agenda ROAM par la règle programmée magnitude déclarée ≥ 6.
Elles sont **ouvertes, pas résolues** : aucune recherche automatique ni prédiction.
Les révisions, conflits et données périmées ont été contrôlés avec des fixtures
explicitement synthétiques ; aucune révision réelle n’a été observée pendant cet essai.

Mistral a réellement reçu les observations et leurs références après redémarrage.
Syn affiche les valeurs exactes produites par le programme, puis le commentaire
Mistral non vérifié. Des essais précédents du modèle ont inventé un lieu ou
approximé un seuil ; sa prose n’est donc jamais une preuve scientifique.
REALITY contrôle la remise du texte au programme, pas sa vérité.

Exemple de chaîne conservée pour Noto :

- Observation normalisée : `g:01197d718b5767def74ffa18b3dba8e8`.
- Preuve Syn : `g:5c37fd9b294b27dff1dee818ff152981`.
- Question : `need:7cd97d27cdde550cc3e4fb896bc961ec`.
- Contexte transmis : `g:47b55e76fe21a44609996bea9e61f733`.
- Cycle de réponse réel : `g:3aeaa96df261499a30bc6686e2b5d364`.

Les exports locaux `SYN_GEO_COLLECTE_REELLE.json`, `SYN_GEO_REPRISE_MODELE_REEL.json`
et `SYN_GEO_RESULTAT_FINAL.json` sont dans le dossier `outputs` parent. Le journal
Glyph, la mémoire des Evidence, l’agenda et les audits demeurent dans la racine Syn
Ubuntu ; l’API HTTP n’est qu’une projection temporaire, sans seconde base de données.

## Chemin des données et interfaces vérifiées

Le MCP GEV `get_earthquakes` utilise le flux USGS des dernières 24 heures, filtré
à M≥2,5. Il n’accepte pas d’intervalle historique. `show_in_gods_eye_view` fournit
une vue/URL ; ce n’est pas une commande arbitraire de navigateur ou un outil de
recherche historique. Cette intégration utilise donc explicitement :

`catalogue USGS → adaptateur Syn → PerceptionBus → Evidence/agenda/Glyph → projection locale → couche séismes GEV`.

Le profil `syn.html` utilise le viewer Cesium, la couche et les overlays **réels**
de GEV. Il désactive les autres couches, les tuiles/terrains distants et le polling.
La texture NaturalEarthII est servie depuis les assets locaux Cesium. La sélection
déplace la caméra ; les disques représentent la magnitude visuellement, jamais
une zone de dégâts mesurée. Une simulation porte une nature et une couleur distinctes.

Source : [API officielle USGS](https://earthquake.usgs.gov/fdsnws/event/1/).
Les dates de séisme, de révision du fournisseur et de collecte sont séparées.
Les coordonnées sont en degrés et la profondeur en kilomètres. Magnitude et position
restent des estimations de catalogue. Les données anciennes restent historiques ou
périmées, même après une nouvelle collecte. Les rapports externes conservent le taint
`external_untrusted`, une confiance absente et une admission `evidence_only`.

Code GEV : MIT, notice conservée dans `integrations/gods-eye-view/GEV_LICENSE.txt`.
Les autres licences d’assets restent dans son dépôt et ses packages.
Données : [conditions USGS](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits).
Le dépôt Syn n’est pas relicencié par cette proposition.

## Bornes et contrôle

- Source autorisée explicitement dans le registre Syn ; unique destination HTTPS
  `earthquake.usgs.gov`, point d’entrée fixe, aucun secret, proxy ou redirection.
- Quatre lectures USGS par processus manuel ; 12 événements par défaut (maximum 100),
  1 Mio décodé, timeout socket 10 s, contrôle coopératif 12 s, aucune relance automatique.
  Ces délais ne constituent pas une échéance absolue d’interruption réseau.
- HTTP 204 demandé par `nodata=204` signifie succès sans événements. Corps HTTP 200
  vide, source indisponible et observations invalides ont des états séparés.
- Modèle llama.cpp fixe `127.0.0.1:8080`, dix appels maximum, entrée courante limitée
  à 4000 octets, 420 tokens de sortie, timeout 120 s, réponse ≤1 Mio, pas d’outils.
- Services nouveaux : `127.0.0.1:8765` et `127.0.0.1:5173`. API uniquement GET,
  Host vérifié, CORS limité au globe. Le Mistral ancien garde sa configuration Docker
  existante ; elle n’est pas modifiée par le lanceur.
- Un seul runtime Syn possède la mémoire avec le verrou de session existant.
  L’agenda suit les mécanismes ROAM ; le modèle ne peut pas déclencher de recherche.

## Configuration et reproduction technique

Le fichier `LANCER_GODS_EYE_PC.ps1` correspond au PC préparé. Pour un autre environnement,
installer Syn avec ses dépendances puis le profil GEV suivant le README d’intégration.
La commande CLI accepte `--bbox SUD NORD OUEST EST`, `--start`, `--end`,
`--min-magnitude`, `--threshold` et `--recent`. Un seuil modifié nécessite une nouvelle
racine de mémoire : l’ancien contrat n’est pas réinterprété silencieusement.

```bash
python synergesis_gods_eye.py --root /chemin/memoire --allow-usgs --collect \
  --message "Qu’as-tu observé et sur quelles données t’appuies-tu ?" --serve --interactive
python -m pytest -q -p no:cacheprovider
python scripts/verify_manifest.py
```

Validation exécutée sur le PC : Python 3.12.3 sous Ubuntu 24.04, **932 tests passent**
en 40,25 s, deux avertissements FastAPI/Starlette préexistants. Cela comprend 74 tests
géographiques/source/modèle/serveur et 7 nouvelles régressions de provenance.
Le test de reçus avait révélé un défaut préexistant : une réécriture de même taille
pouvait échapper au cache fondé sur l’horodatage. Le cache vérifie désormais une
empreinte du contenu effectivement lu ; les reçus, transports et stress ont été revérifiés.
GEV : **12 tests de profil passent**, build Vite réussi avec Node 24.21.0.
Le parcours source réelle, reprise, modèle réel, sélection d’événements et globe
ont été contrôlés séparément des fixtures. Les autres couches de GEV ne sont pas testées.
