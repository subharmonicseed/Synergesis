# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# LLM Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

# SerpAPI Key (for web search)
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY is required. Set it in .env or environment variables.")

# Optional: Base directory for file/shell tools
SANDBOX_DIR = os.getenv("SANDBOX_DIR", "sandbox")

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "blackstar1989")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
