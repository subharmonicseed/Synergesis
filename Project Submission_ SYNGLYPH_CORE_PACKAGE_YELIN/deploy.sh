#!/bin/bash

# Script de déploiement pour SYNERGESIS

# Créer le répertoire de données s'il n'existe pas
mkdir -p data

# Vérifier si Docker est installé
if ! command -v docker &> /dev/null; then
    echo "Docker n'est pas installé. Veuillez installer Docker avant de continuer."
    exit 1
fi

# Vérifier si Docker Compose est installé
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose n'est pas installé. Veuillez installer Docker Compose avant de continuer."
    exit 1
fi

echo "Déploiement de SYNERGESIS..."

# Construire et démarrer les conteneurs
docker-compose up -d --build

# Vérifier si le déploiement a réussi
if [ $? -eq 0 ]; then
    echo "SYNERGESIS a été déployé avec succès!"
    echo "L'API est accessible à l'adresse: http://localhost:8000"
    echo "L'interface utilisateur est accessible à l'adresse: http://localhost:8000/static/code.html"
else
    echo "Une erreur s'est produite lors du déploiement de SYNERGESIS."
    exit 1
fi

# Afficher les logs pour vérification
echo "Affichage des logs du conteneur SYNERGESIS:"
docker-compose logs synergesis
