# Synergesis AI System 🧠

**Synergesis** is an advanced modular AI agent system with quantum computing enhancements for knowledge synthesis, inconsistency detection, and creative suggestion generation. It combines LLM reasoning with tool execution (web search, file I/O, shell) and quantum-enhanced algorithms to perform complex tasks autonomously.

## 🔧 Core Features

- **Modular Architecture**: Clean separation of agents, core, API, CLI, and storage components
- **Quantum Agents**: Enhanced agents using quantum computing principles (Qiskit/PennyLane)
- **Persistent Storage**: Neo4j graph database integration for knowledge persistence
- **Multiple Interfaces**: Web dashboard and CLI chat interfaces
- **Security**: Sandboxed tools and secure environment configuration
- **Testing**: Comprehensive test suite with pytest


## 🚀 Quick Start


### 1. Clone the repo

```bash
git clone <repository-url>
cd Synergesis
```

### 2. Set up environment

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up API keys

```bash
cp .env.example .env  # or create .env manually
```

Edit `.env`:

```env
SERPAPI_KEY=your_serpapi_key_here
LLM_MODEL=gpt-3.5-turbo
```

> Get a free SerpAPI key at [serpapi.com](https://serpapi.com/)


### 5. Run the agent

```bash
python main.py
```


## 🛠️ Tools


| Tool | Security |
|------|----------|
| `WebSearchTool` | Requires SerpAPI key |
| `FileTool` | Sandboxed in `sandbox/` |
| `ShellTool` | Whitelisted commands only |


## 📂 Project Structure

```text
Synergesis/
├── agents/          # Agent logic
├── tools/           # Action tools
├── planning/        # Plan & reflect
├── memory/          # Memory system
├── sandbox/         # Restricted file/shell area (auto-created)
├── .env             # API keys (not tracked)
└── synergesis.log   # Runtime logs
```


## ⚠️ System Requirements


**Minimum Hardware Requirements:**
- **RAM**: 16 GB (8 GB is insufficient for full stack)
- **CPU**: Multi-core processor (Intel i5/AMD Ryzen 5 or better)
- **Storage**: 10 GB free space

**Recommended Hardware:**
- **RAM**: 32 GB
- **CPU**: Intel i7/AMD Ryzen 7 or better
- **Storage**: SSD with 20+ GB free space

**Software Requirements:**
- Python 3.11+
- Docker Desktop (for containerized deployment)
- Windows 10/11, macOS 12+, or Ubuntu 20.04+


## 🐳 Docker Setup

```bash
docker-compose up -d neo4j
```


## 🧪 Run Tests

```bash
pytest tests/
```


## 📦 Install as Package

```bash
pip install -e .
synergesis
```


## 📊 Launch Dashboard

```bash
streamlit run dashboard.py
```


## 🔄 CI/CD

GitHub Actions will:
- Run tests on every push
- Scan for security issues
- Build Docker image

## 📄 License
MIT
