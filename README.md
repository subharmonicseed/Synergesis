# Synergesis 🧠

**Synergesis** is a modular AI agent system that plans, acts, reflects, and learns. It combines LLM reasoning with tool execution (web search, file I/O, shell) to perform complex tasks autonomously.

![Agent Loop](https://i.imgur.com/abc123.png) <!-- Optional: Add diagram later -->


## 🔧 Features


- **Planning Agent**: Breaks tasks into steps
- **Reflection**: Self-critiques and improves plans
- **Memory**: Short-term and long-term memory (JSON)
- **Tools**:
  - Web search (via SerpAPI)
  - File read/write (sandboxed)
  - Shell commands (safe execution)
- **Extensible**: Easy to add new tools and agents


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
