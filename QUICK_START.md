# Synergesis Quick Start Guide

## Prerequisites
- Python 3.11+
- Docker Desktop
- 16+ GB RAM
- SerpAPI key (free account at serpapi.com)

## Setup & Installation

1. **Activate Virtual Environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   ```

3. **Configure Environment**
   Edit `.env` with your API keys:
   ```env
   SERPAPI_KEY=your_actual_serpapi_key_here
   NEO4J_PASSWORD=SynergesisSecure123!
   ```

## Running the System

### Option 1: Docker (Recommended)
```bash
docker-compose up --build
```

### Option 2: Direct Python
```bash
python main.py
```

## Testing the System

1. **API Documentation**: http://localhost:8000/docs
2. **Health Check**: http://localhost:8000/
3. **Glyph Operations**: 
   - GET http://localhost:8000/glyphs
   - POST http://localhost:8000/glyphs

## Common Issues & Solutions

### Neo4j Unhealthy Status
- **Cause**: Insufficient memory
- **Solution**: Upgrade to 16+ GB RAM

### Docker Build Failures
- **Cause**: Corrupted cache
- **Solution**: 
  ```bash
  docker-compose down --volumes
  docker builder prune -a -f
  ```

### Connection Refused
- **Cause**: Neo4j not ready
- **Solution**: Check container status with `docker-compose ps`

## Next Steps After Hardware Upgrade

1. **Verify Resources**:
   ```bash
   systeminfo | findstr /C:"Total Physical Memory"
   ```

2. **Test Minimal Configuration**:
   - Reduce agents in `synergesis/agents/`
   - Adjust Neo4j memory in `docker-compose.yml`

3. **Full System Validation**:
   - Run all agents
   - Test glyph persistence
   - Verify quantum processing
