# Synergesis Hardware Requirements & Migration Guide

## System Requirements

### Minimum Hardware
- **RAM**: 16 GB
- **CPU**: Multi-core processor (Intel i5/AMD Ryzen 5 or better)
- **Storage**: 10 GB free space

### Recommended Hardware
- **RAM**: 32 GB
- **CPU**: Intel i7/AMD Ryzen 7 or better
- **Storage**: SSD with 20+ GB free space

## Why Your Current System Is Insufficient

Your PC has 8 GB of RAM, which is not enough to run:
1. Neo4j Enterprise database (requires 2-4 GB alone)
2. 17 Python agents simultaneously
3. FastAPI web server
4. Docker overhead

This causes silent crashes where the OS kills processes to free memory.

## Migration Steps for New PC

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd Synergesis
   ```

2. **Set Up Environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   ```

4. **Configure API Keys**
   - Get SerpAPI key from https://serpapi.com/
   - Update `.env` file with your keys

5. **Run Docker Stack**
   ```bash
   docker-compose up --build
   ```

## Quick Start Commands

- **Start**: `docker-compose up --build`
- **Stop**: `docker-compose down`
- **View logs**: `docker-compose logs`
- **API docs**: http://localhost:8000/docs

## Performance Optimization Tips

1. **Limit active agents** in `agent_manager.py`
2. **Reduce Neo4j memory allocation** in `docker-compose.yml` if needed
3. **Use --scale option** to control container instances
4. **Monitor with Docker Dashboard** or `docker stats`
