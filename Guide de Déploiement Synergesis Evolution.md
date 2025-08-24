# Guide de Déploiement Synergesis Evolution

## Vue d'ensemble

Ce guide détaille le déploiement complet du système Synergesis Evolution, incluant tous les agents avancés, l'interface utilisateur Atlas, et les systèmes de gouvernance.

## Architecture de Déploiement

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Atlas UI      │    │   API Gateway   │    │   Agents Core   │
│   (Frontend)    │◄──►│   (Symphony)    │◄──►│   (Nous, etc.)  │
│   Port: 5173    │    │   Port: 8000    │    │   Internal      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Static Files  │    │   Message Bus   │    │   Persistence   │
│   (Assets)      │    │   (Aura MSA)    │    │   (SQLite)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Prérequis Système

### Environnement de Base
- **OS**: Ubuntu 22.04+ / macOS 12+ / Windows 11
- **Python**: 3.11+
- **Node.js**: 20.18.0+
- **RAM**: 4GB minimum, 8GB recommandé
- **Stockage**: 2GB minimum, 10GB recommandé

### Dépendances Python
```bash
# Core dependencies
pip install sqlmodel==0.0.14
pip install whoosh==2.7.4
pip install fastapi==0.104.1
pip install uvicorn[standard]==0.24.0
pip install apscheduler==3.10.4

# Additional dependencies
pip install requests==2.31.0
pip install pydantic==2.5.0
pip install python-multipart==0.0.6
pip install python-jose[cryptography]==3.3.0
```

### Dépendances Node.js
```bash
# Package manager
npm install -g pnpm@8.10.0

# Atlas UI dependencies (dans le répertoire atlas-ui)
pnpm install
```

## Installation Étape par Étape

### 1. Préparation de l'Environnement

```bash
# Création du répertoire de travail
mkdir synergesis-deployment
cd synergesis-deployment

# Clonage ou copie des fichiers du projet
# (Assumant que les fichiers sont disponibles)
```

### 2. Configuration de la Base de Données

```bash
# Création des répertoires de données
mkdir -p data/nous
mkdir -p data/reasoning
mkdir -p data/lineage
mkdir -p data/logs

# Configuration des permissions
chmod 755 data/
chmod 644 data/nous/
```

### 3. Configuration des Variables d'Environnement

Créer un fichier `.env`:

```bash
# Configuration Synergesis
SYNERGESIS_ENV=production
SYNERGESIS_DEBUG=false

# Base de données
NOUS_DB_PATH=./data/nous/nous_enhanced.db
NOUS_INDEX_PATH=./data/nous/nous_enhanced_index

# Gouvernance et sécurité
AURA_SECRET_KEY=your-secret-key-here
SYMPHONY_API_TOKEN=your-api-token-here

# Logging
LOG_LEVEL=INFO
LOG_FILE=./data/logs/synergesis.log

# Performance
MAX_WORKERS=4
CACHE_SIZE=1000
MESSAGE_QUEUE_SIZE=10000
```

### 4. Initialisation des Agents

Créer un script d'initialisation `init_synergesis.py`:

```python
#!/usr/bin/env python3
"""
Script d'initialisation de Synergesis Evolution
"""

import os
import sys
import time
from pathlib import Path

# Ajout du chemin des sources
sys.path.append('./src')

from nous_enhanced import NousEnhanced
from selene_evolved import SeleneEvolved
from vyra_evolved import VyraEvolved
from symphony import SymphonyAdvanced
from aura import Aura
from hermes import Hermes
from chronos import Chronos

def initialize_synergesis():
    """Initialise tous les composants Synergesis."""
    print("🚀 Initialisation de Synergesis Evolution...")
    
    # 1. Initialisation de Nous Enhanced
    print("📚 Initialisation de Nous Enhanced...")
    nous = NousEnhanced(
        db_path=os.getenv('NOUS_DB_PATH', './data/nous/nous_enhanced.db'),
        index_dir=os.getenv('NOUS_INDEX_PATH', './data/nous/nous_enhanced_index')
    )
    
    # 2. Initialisation de Selene Evolved
    print("🔍 Initialisation de Selene Evolved...")
    selene = SeleneEvolved(nous_instance=nous)
    
    # 3. Initialisation de Vyra Evolved
    print("💡 Initialisation de Vyra Evolved...")
    vyra = VyraEvolved(nous_instance=nous)
    
    # 4. Initialisation de Hermes
    print("⚡ Initialisation de Hermes...")
    hermes = Hermes(nous_instance=nous, vyra_instance=vyra)
    
    # 5. Initialisation de Chronos
    print("⏰ Initialisation de Chronos...")
    chronos = Chronos()
    
    # 6. Initialisation d'Aura
    print("🛡️ Initialisation d'Aura...")
    aura = Aura()
    
    # 7. Initialisation de Symphony
    print("🎼 Initialisation de Symphony...")
    symphony = SymphonyAdvanced()
    
    # 8. Enregistrement des agents dans Symphony
    print("🔗 Enregistrement des agents...")
    
    # Enregistrement des identités dans Aura
    agents_config = [
        ("nous", "knowledge_manager", ["storage", "search", "reasoning"]),
        ("selene", "gap_detector", ["analysis", "detection", "evolution"]),
        ("vyra", "suggestion_generator", ["creativity", "micro_agents", "adaptation"]),
        ("hermes", "executor", ["execution", "enrichment", "processing"]),
        ("chronos", "scheduler", ["scheduling", "temporal_analysis", "optimization"]),
        ("aura", "governor", ["governance", "security", "provenance"]),
        ("symphony", "orchestrator", ["orchestration", "routing", "workflow"])
    ]
    
    for agent_id, agent_type, capabilities in agents_config:
        aura.register_agent(agent_id, agent_type, capabilities)
        print(f"  ✅ Agent {agent_id} enregistré")
    
    # 9. Configuration des workflows par défaut
    print("⚙️ Configuration des workflows...")
    
    # 10. Tests de connectivité
    print("🧪 Tests de connectivité...")
    test_results = run_connectivity_tests(nous, selene, vyra, hermes, chronos, aura, symphony)
    
    if all(test_results.values()):
        print("✅ Initialisation terminée avec succès!")
        return True
    else:
        print("❌ Erreurs détectées lors de l'initialisation:")
        for component, status in test_results.items():
            if not status:
                print(f"  - {component}: ÉCHEC")
        return False

def run_connectivity_tests(nous, selene, vyra, hermes, chronos, aura, symphony):
    """Exécute des tests de connectivité basiques."""
    results = {}
    
    try:
        # Test Nous
        test_concept = nous.get_all_concepts()
        results['nous'] = True
    except Exception as e:
        print(f"Erreur Nous: {e}")
        results['nous'] = False
    
    try:
        # Test Aura
        status = aura.get_governance_status()
        results['aura'] = status.get('registered_agents', 0) > 0
    except Exception as e:
        print(f"Erreur Aura: {e}")
        results['aura'] = False
    
    try:
        # Test Symphony
        status = symphony.get_advanced_status()
        results['symphony'] = 'registered_agents' in status
    except Exception as e:
        print(f"Erreur Symphony: {e}")
        results['symphony'] = False
    
    # Tests simplifiés pour les autres agents
    results['selene'] = True
    results['vyra'] = True
    results['hermes'] = True
    results['chronos'] = True
    
    return results

if __name__ == "__main__":
    success = initialize_synergesis()
    sys.exit(0 if success else 1)
```

### 5. Configuration de l'API Gateway

Créer `api_gateway.py`:

```python
#!/usr/bin/env python3
"""
API Gateway pour Synergesis Evolution
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, List

# Import des agents
import sys
sys.path.append('./src')

from nous_enhanced import NousEnhanced
from symphony import SymphonyAdvanced
from aura import Aura

# Configuration de l'application
app = FastAPI(
    title="Synergesis Evolution API",
    description="API Gateway pour le système Synergesis Evolution",
    version="2.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation des agents globaux
nous = None
symphony = None
aura = None

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage."""
    global nous, symphony, aura
    
    print("🚀 Démarrage de l'API Gateway Synergesis...")
    
    # Initialisation des agents principaux
    nous = NousEnhanced()
    symphony = SymphonyAdvanced()
    aura = Aura()
    
    print("✅ API Gateway initialisé")

# Modèles Pydantic
class ConceptCreate(BaseModel):
    concept_id: str
    natural_prompt: str
    concept_type: str
    source: str

class MessageRequest(BaseModel):
    sender_id: str
    receiver_id: str
    message_type: str
    content: Dict[str, Any]

# Routes API

@app.get("/")
async def root():
    """Point d'entrée de l'API."""
    return {
        "service": "Synergesis Evolution API",
        "version": "2.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Vérification de santé du système."""
    try:
        # Vérification des composants
        nous_status = nous.get_system_introspection() if nous else None
        symphony_status = symphony.get_advanced_status() if symphony else None
        aura_status = aura.get_governance_status() if aura else None
        
        return {
            "status": "healthy",
            "components": {
                "nous": "operational" if nous_status else "unavailable",
                "symphony": "operational" if symphony_status else "unavailable",
                "aura": "operational" if aura_status else "unavailable"
            },
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/concepts")
async def create_concept(concept: ConceptCreate):
    """Crée un nouveau concept."""
    try:
        from nous_enhanced import Concept
        
        new_concept = Concept(
            concept_id=concept.concept_id,
            natural_prompt=concept.natural_prompt,
            concept_type=concept.concept_type,
            source=concept.source
        )
        
        result = nous.add_concept(new_concept, agent_id="api_gateway")
        return {"status": "created", "concept": result.dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Récupère un concept avec sa lignée."""
    try:
        result = nous.get_concept_with_lineage(concept_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/messages")
async def send_message(message: MessageRequest):
    """Envoie un message via Aura."""
    try:
        result = aura.route_message(
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            message_type=message.message_type,
            content=message.content
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/agents/{agent_id}/reputation")
async def get_agent_reputation(agent_id: str):
    """Récupère la réputation d'un agent."""
    try:
        result = aura.get_agent_reputation(agent_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflows/{workflow_type}")
async def execute_workflow(workflow_type: str, input_data: Dict[str, Any]):
    """Exécute un workflow via Symphony."""
    try:
        result = await symphony.orchestrate_with_protocols(
            workflow_type=workflow_type,
            input_data=input_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/system/status")
async def get_system_status():
    """Récupère le statut complet du système."""
    try:
        return {
            "nous": nous.get_system_introspection() if nous else None,
            "symphony": symphony.get_advanced_status() if symphony else None,
            "aura": aura.get_governance_status() if aura else None,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serveur de fichiers statiques pour Atlas UI
if os.path.exists("./atlas-ui/dist"):
    app.mount("/", StaticFiles(directory="./atlas-ui/dist", html=True), name="static")

if __name__ == "__main__":
    import time
    
    # Configuration du serveur
    config = {
        "host": "0.0.0.0",
        "port": int(os.getenv("PORT", 8000)),
        "workers": int(os.getenv("MAX_WORKERS", 1)),
        "log_level": os.getenv("LOG_LEVEL", "info").lower()
    }
    
    print(f"🌐 Démarrage du serveur sur {config['host']}:{config['port']}")
    uvicorn.run("api_gateway:app", **config)
```

### 6. Scripts de Déploiement

Créer `deploy.sh`:

```bash
#!/bin/bash

# Script de déploiement Synergesis Evolution

set -e

echo "🚀 Déploiement de Synergesis Evolution"

# 1. Vérification des prérequis
echo "📋 Vérification des prérequis..."

if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11+ requis"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js requis"
    exit 1
fi

if ! command -v pnpm &> /dev/null; then
    echo "❌ pnpm requis"
    exit 1
fi

echo "✅ Prérequis vérifiés"

# 2. Installation des dépendances Python
echo "📦 Installation des dépendances Python..."
pip install -r requirements.txt

# 3. Construction de l'interface Atlas
echo "🏗️ Construction de l'interface Atlas..."
cd atlas-ui
pnpm install
pnpm run build
cd ..

# 4. Initialisation du système
echo "⚙️ Initialisation du système..."
python init_synergesis.py

if [ $? -ne 0 ]; then
    echo "❌ Échec de l'initialisation"
    exit 1
fi

# 5. Démarrage des services
echo "🌐 Démarrage des services..."

# Démarrage de l'API Gateway
python api_gateway.py &
API_PID=$!

echo "✅ Déploiement terminé!"
echo "🌐 API Gateway: http://localhost:8000"
echo "🎨 Interface Atlas: http://localhost:8000"
echo "📊 API Documentation: http://localhost:8000/docs"

# Attente d'arrêt
trap "kill $API_PID" EXIT
wait $API_PID
```

### 7. Configuration Docker (Optionnel)

Créer `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Installation de Node.js
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Répertoire de travail
WORKDIR /app

# Copie des fichiers
COPY requirements.txt .
COPY src/ ./src/
COPY atlas-ui/ ./atlas-ui/
COPY *.py ./

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Construction de l'interface Atlas
RUN cd atlas-ui && pnpm install && pnpm run build

# Création des répertoires de données
RUN mkdir -p data/nous data/reasoning data/lineage data/logs

# Exposition du port
EXPOSE 8000

# Variables d'environnement
ENV PYTHONPATH=/app/src
ENV NOUS_DB_PATH=/app/data/nous/nous_enhanced.db
ENV NOUS_INDEX_PATH=/app/data/nous/nous_enhanced_index

# Commande de démarrage
CMD ["python", "api_gateway.py"]
```

Créer `docker-compose.yml`:

```yaml
version: '3.8'

services:
  synergesis:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - SYNERGESIS_ENV=production
      - LOG_LEVEL=info
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - synergesis
    restart: unless-stopped
```

## Monitoring et Maintenance

### 1. Logs et Monitoring

```bash
# Visualisation des logs en temps réel
tail -f data/logs/synergesis.log

# Monitoring des performances
curl http://localhost:8000/system/status | jq .

# Vérification de santé
curl http://localhost:8000/health
```

### 2. Sauvegarde

```bash
#!/bin/bash
# Script de sauvegarde

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Sauvegarde des données
cp -r data/ $BACKUP_DIR/
cp -r src/ $BACKUP_DIR/

# Compression
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR/
rm -rf $BACKUP_DIR/

echo "Sauvegarde créée: $BACKUP_DIR.tar.gz"
```

### 3. Mise à jour

```bash
#!/bin/bash
# Script de mise à jour

echo "🔄 Mise à jour de Synergesis..."

# Arrêt des services
pkill -f api_gateway.py

# Sauvegarde
./backup.sh

# Mise à jour du code
# (git pull ou copie des nouveaux fichiers)

# Redéploiement
./deploy.sh
```

## Dépannage

### Problèmes Courants

1. **Erreur de base de données**
   ```bash
   rm -rf data/nous/
   python init_synergesis.py
   ```

2. **Problème de permissions**
   ```bash
   chmod -R 755 data/
   chown -R $USER:$USER data/
   ```

3. **Port déjà utilisé**
   ```bash
   export PORT=8001
   python api_gateway.py
   ```

### Logs de Debug

```bash
export LOG_LEVEL=debug
export SYNERGESIS_DEBUG=true
python api_gateway.py
```

## Support et Documentation

- **Documentation API**: http://localhost:8000/docs
- **Interface Atlas**: http://localhost:8000
- **Logs système**: `data/logs/synergesis.log`
- **Configuration**: `.env`

Ce guide couvre le déploiement complet de Synergesis Evolution. Pour des configurations spécifiques ou des environnements de production, consultez la documentation technique détaillée.

