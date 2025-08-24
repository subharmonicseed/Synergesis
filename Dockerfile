FROM python:3.11-slim

# Métadonnées
LABEL maintainer="Équipe Synergesis <contact@synergesis.ai>"
LABEL version="1.0.0"
LABEL description="Pipeline réflexif topologique pour le projet Synergesis"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NEO4J_URI=bolt://neo4j:7687
ENV NEO4J_USER=neo4j
ENV NEO4J_PASSWORD=synergesis
ENV METRICS_PORT=8000
ENV EXPOSE_METRICS=true
ENV PUSH_GATEWAY_URL=""

# Répertoire de travail
WORKDIR /app

# Copie des fichiers de dépendances
COPY requirements.txt .

# Installation des dépendances
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY src/ /app/src/
COPY setup.py README.md ./

# Installation du package
RUN pip install -e .

# Exposition du port pour les métriques Prometheus
EXPOSE 8000

# Commande par défaut
CMD ["python", "-m", "src.synergesis_reflexive_pipeline", "--expose-metrics"]

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/metrics || exit 1
