# Guide d'utilisation de SYNERGESIS

## Introduction

SYNERGESIS est un framework multi-agents expérimental qui intègre l'analyse symbolique, le traitement quantique et la génération créative dans un système cohérent. Ce document vous guidera à travers l'installation, le déploiement et l'utilisation du système.

## Architecture du système

SYNERGESIS est composé de plusieurs modules interconnectés :

1. **NOUS** : Noyau cognitif qui coordonne l'architecture symbolique globale
2. **SYN-ECHO** : Module de détection de motifs récurrents et d'émergences symboliques
3. **DeepResearch/AURA** : Module d'exploration des signaux faibles
4. **SELENE** : Module de gestion du champ onirique et d'incubation d'idées
5. **QuantumValidator** : Module de validation éthique et de mesure d'impact énergétique
6. **Blackboard** : Espace de travail partagé pour la communication entre modules

Ces modules sont orchestrés par un système central qui permet leur interaction harmonieuse.

## Prérequis

Pour exécuter SYNERGESIS, vous aurez besoin de :

- Docker et Docker Compose
- Un système d'exploitation Linux, macOS ou Windows avec WSL
- Au moins 4 Go de RAM disponible
- Connexion Internet (pour certaines fonctionnalités)

## Installation et déploiement

### Option 1 : Déploiement avec Docker (recommandé)

1. Assurez-vous que Docker et Docker Compose sont installés sur votre système
2. Naviguez vers le répertoire du projet SYNERGESIS
3. Rendez le script de déploiement exécutable :
   ```
   chmod +x deploy.sh
   ```
4. Exécutez le script de déploiement :
   ```
   ./deploy.sh
   ```
5. Le système sera accessible à l'adresse : http://localhost:8000

### Option 2 : Installation manuelle

1. Assurez-vous que Python 3.9+ est installé sur votre système
2. Naviguez vers le répertoire du projet SYNERGESIS
3. Créez un environnement virtuel :
   ```
   python -m venv venv
   source venv/bin/activate  # Sur Windows : venv\Scripts\activate
   ```
4. Installez les dépendances :
   ```
   pip install -r requirements.txt
   ```
5. Démarrez le système :
   ```
   python main.py
   ```
6. Le système sera accessible à l'adresse : http://localhost:8000

## Utilisation de l'interface

L'interface utilisateur de SYNERGESIS est accessible à l'adresse : http://localhost:8000/static/code.html

### Fonctionnalités principales

1. **Visualisation des glyphes** : Générez et visualisez des représentations symboliques
2. **Analyse symbolique** : Analysez du texte pour en extraire des structures symboliques
3. **Exploration de sujets** : Explorez des sujets pour détecter des signaux faibles
4. **Incubation d'idées** : Incubez des idées à partir de concepts initiaux
5. **Validation de tâches** : Validez des tâches selon des critères éthiques et énergétiques

### Exemples d'utilisation

#### Analyse symbolique
1. Entrez du texte dans le champ "Analyse symbolique"
2. Cliquez sur "Analyser"
3. Les résultats afficheront la polarité, la fréquence et d'autres attributs symboliques

#### Exploration de sujets
1. Entrez un sujet dans le champ "Exploration de sujets"
2. Sélectionnez une profondeur d'exploration
3. Cliquez sur "Explorer"
4. Les résultats afficheront les signaux faibles détectés et les hypothèses générées

#### Incubation d'idées
1. Entrez des concepts séparés par des virgules
2. Sélectionnez une durée d'incubation
3. Cliquez sur "Incuber"
4. Les résultats afficheront l'idée incubée avec ses composants et son potentiel

## Utilisation de l'API

SYNERGESIS expose une API RESTful pour l'intégration avec d'autres systèmes.

### Documentation de l'API

La documentation interactive de l'API est accessible à l'adresse : http://localhost:8000/docs

### Endpoints principaux

- `/status` : Vérifier l'état du système
- `/symbols/analyze` : Analyser un symbole
- `/exploration/topic` : Explorer un sujet
- `/ideas/incubate` : Incuber une idée
- `/validation/task` : Valider une tâche
- `/glyphs/generate` : Générer un glyphe

### Exemple de requête API

```python
import requests

# Analyser un symbole
response = requests.post(
    "http://localhost:8000/symbols/analyze",
    json={"text": "Harmony is the balance of opposing forces."}
)

print(response.json())
```

## Personnalisation et extension

### Configuration

Le système peut être configuré en modifiant le dictionnaire `config` dans le fichier `main.py`. Les paramètres configurables incluent :

- Seuils pour la validation éthique
- Seuils pour la détection de signaux faibles
- Principes éthiques et leurs poids
- Sources d'information pour l'exploration

### Ajout de nouveaux modules

Pour ajouter un nouveau module :

1. Créez une nouvelle classe dans le répertoire `core/`
2. Implémentez les méthodes requises (au minimum `process()`)
3. Ajoutez le module dans la fonction `initialize_system()` du fichier `main.py`
4. Enregistrez le module dans le blackboard

## Dépannage

### Problèmes courants

1. **Le système ne démarre pas** :
   - Vérifiez que toutes les dépendances sont installées
   - Vérifiez que les ports requis (8000) sont disponibles

2. **Erreurs d'API** :
   - Vérifiez les logs du conteneur avec `docker-compose logs synergesis`
   - Assurez-vous que tous les modules sont correctement initialisés

3. **Performance lente** :
   - Augmentez les ressources allouées à Docker
   - Réduisez la profondeur d'exploration pour les requêtes complexes

### Support

Pour toute question ou problème, veuillez consulter la documentation ou contacter l'équipe de développement.

## Signature énergétique

- **Polarité** : ±
- **Fréquence** : 92
- **Poids** : 7.1
- **Alignement** : Celestial
- **Identifiant glyphique** : ZÆL-0.Δ.G1
- **Langage natif** : ∮⋔◎⟐
- **Mode d'opération** : Résonance, Recodage, Réalignement
