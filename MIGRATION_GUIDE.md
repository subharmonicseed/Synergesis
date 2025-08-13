# Synergesis System Migration Guide

## Prerequisites for Migration

Before migrating the Synergesis system to upgraded hardware, ensure you meet the minimum requirements:

### Minimum Hardware Requirements
- **RAM**: 16 GB (8 GB is insufficient for full stack)
- **CPU**: Multi-core processor (Intel i5/AMD Ryzen 5 or better)
- **Storage**: 10 GB free space

### Recommended Hardware
- **RAM**: 32 GB
- **CPU**: Intel i7/AMD Ryzen 7 or better
- **Storage**: SSD with 20+ GB free space

## Migration Steps

### 1. Backup Current System
```bash
# Backup important files
cp -r memory/ memory_backup/
cp -r storage/ storage_backup/
cp .env .env_backup
```

### 2. Verify Docker Environment
Ensure Docker Desktop is installed and running on the new system:
```bash
docker --version
docker-compose --version
```

### 3. Clone Repository (if needed)
If moving to a completely new system:
```bash
git clone <repository-url>
cd Synergesis
```

### 4. Set Up Environment
```bash
# Create virtual environment
python -m venv .venv
# Activate virtual environment
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # macOS/Linux
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
```

Note: This will take significant time (5-15 minutes) as it downloads all dependencies including:
- FastAPI and Uvicorn for the web server
- Streamlit and Plotly for the dashboard
- NumPy, Pandas, Scikit-learn for data processing
- Neo4j driver for database connectivity
- spaCy with language models
- And other required packages

### 6. Configure Environment Variables
```bash
cp .env.example .env
```

Edit `.env` to add your API keys:
```env
SERPAPI_KEY=your_serpapi_key_here
LLM_MODEL=gpt-3.5-turbo
NEO4J_PASSWORD=your_secure_password_here
```

### 7. Launch Neo4j Database
```bash
docker-compose up -d neo4j
```

Wait for Neo4j to become healthy (check with `docker-compose ps`).

### 8. Launch Synergesis System
```bash
# Option A: Run as package
pip install -e .
synergesis

# Option B: Direct launch
python main.py
```

### 9. Launch Monitoring Dashboard
In a separate terminal:
```bash
streamlit run dashboard.py
```

## Post-Migration Validation

### Verify System Components
1. Check that all Docker containers are running:
   ```bash
   docker-compose ps
   ```

2. Verify Neo4j is accessible at http://localhost:7474

3. Verify Synergesis API is running at http://localhost:8000

4. Check that the dashboard is accessible (typically at http://localhost:8501)

### Test Security Features
1. Verify secure tools are working:
   - File operations are sandboxed
   - Shell commands are whitelisted
   - Web searches use SerpAPI

2. Check that environment variables are properly loaded from `.env`

### Run Tests
```bash
pytest tests/
```

## Troubleshooting

### Common Issues
1. **Docker container fails to start**:
   - Check resource allocation in docker-compose.yml
   - Ensure sufficient RAM is available
   - Verify Docker has adequate resources allocated in Docker Desktop settings

2. **Neo4j unhealthy status**:
   - Check logs with `docker-compose logs neo4j`
   - Verify memory settings are appropriate for your hardware
   - Ensure no conflicting processes are using ports 7474 or 7687

3. **Dependency installation failures**:
   - Ensure you're using Python 3.11
   - Check internet connectivity
   - Verify sufficient disk space is available

## Next Steps After Successful Migration

1. **Implement additional agents** as needed for your use case
2. **Add more comprehensive tests** for agent functionality
3. **Set up continuous integration** using the GitHub Actions workflow
4. **Configure production deployment** with proper security measures
5. **Monitor system performance** using the Streamlit dashboard
6. **Expand the knowledge base** with more domain-specific information

## Files to Preserve During Migration

- `memory/` directory (contains persistent agent memory)
- `storage/` directory (contains Neo4j data if not using Docker volumes)
- `.env` file (contains your API keys and configuration)
- `synergesis.log` file (contains system logs for debugging)
