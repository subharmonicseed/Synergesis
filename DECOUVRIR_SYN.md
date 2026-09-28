# Découvrir Syn

Cette démonstration lance le véritable assemblage de Syn avec un raisonnement
programmé. Elle ne nécessite aucune clé API et ne contacte pas Internet.
Elle montre le contrôle des résultats et leur historique ; elle ne constitue pas
encore une conversation avec un LLM ni une autonomie prolongée.

## Premier lancement

Utiliser Linux, macOS ou Ubuntu dans WSL sous Windows. Les verrous actuels
ne fonctionnent pas avec Python Windows natif. Python 3.11 ou 3.12 est requis
pour reproduire la matrice testée.

Depuis le dossier de cette version du projet :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python run_syn_discovery.py --output ./ma-premiere-decouverte
```

L'installation télécharge les dépendances Python ; la démonstration elle-même
fonctionne hors réseau. Le dossier de sortie doit être nouveau. Aucun ancien
dossier n'est supprimé ou réutilisé. Sans `--output`, un nouveau dossier temporaire
est créé et son chemin apparaît dans les résultats ; préférer un dossier explicite
pour conserver les traces.

## Ce que tu vas voir

1. Une action écrit un fichier réel. Syn vérifie sa présence et son contenu,
   puis retient le résultat confirmé.
2. Un autre exécutant annonce « réussi » sans écrire le fichier. Syn observe
   l'absence du fichier, contredit cette annonce et attribue un score nul à
   l'apprentissage de cette réussite annoncée.
3. Les deux historiques sont vérifiés puis relus avec de nouveaux lecteurs.

Chaque scénario possède son propre dossier vierge : le fichier du premier ne
peut pas faire croire que le second a réussi. Le score de 0,9 du premier cas
est fourni par le raisonnement programmé ; ce n'est pas une probabilité de vérité
mesurée. La correction du second à 0 vient bien du contrôle REALITY.

`bilan.json` contient les résultats observés, les identifiants des traces et les
empreintes des historiques. Les fichiers `stack/glyph_ledger.jsonl` conservent
les événements : demande, décision, autorisation, action, déclaration de
l'exécutant, observation du fichier, verdict, prédiction et révision.

## Limites de cette première découverte

Le seul exécutant accepte l'écriture d'un contenu fixe dans un fichier fixe du
dossier de démonstration. Il n'y a ni commande shell pilotée par modèle, ni source
Internet, ni import distant. Le profil local autorise cette action sans capacité
signée : cela ne démontre pas une politique d'autorisation pour des actions à risque.
L'observateur consulte le système de fichiers indépendamment de la déclaration
mais reste dans le même processus : ce n'est pas une attestation matérielle.

Une chaîne vérifiée permet de détecter certaines altérations ; elle ne certifie
pas la vérité de toutes les données ni ne résiste seule à une réécriture complète
par un acteur disposant de tous les accès. La relecture des journaux ici ne prouve
pas la récupération de l'ensemble du programme après une coupure.

La version reprend la pile des corrections jusqu'à la proposition GitHub nº 42.
Elle reste une version de découverte, pas une livraison autonome finalisée.
Restent notamment la revue du remplacement de l'ancien `main`, les contrats de
permissions, la protection des stockages encore mono-écrivain et le traitement
opérateur des imports partiels. Le guide ne demande pas de lancer les anciens
scripts de stress, dont certains nécessitent encore un nettoyage de leurs chemins.
