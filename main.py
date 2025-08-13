from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from storage.neo4j_interface import Neo4jStorage, GlyphNode
import uvicorn
from dotenv import load_dotenv
import os
from typing import Optional

# Load environment variables
load_dotenv()

# Initialize storage
storage = Neo4jStorage()

# --- CLUSTER/LOG API INTEGRATION ---
from synergesis.core import cluster_api
from synergesis.core.cluster_state import performance_log, patterns_seen, engine_start_ts
app = FastAPI(title="Synergesis API")
app.include_router(cluster_api.router)
# --- END CLUSTER/LOG API INTEGRATION ---

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to Synergesis API"}

@app.get("/glyphs")
async def get_glyphs(type: Optional[str] = None, limit: int = 10):
    """Get list of glyphs (limited to 10 results)"""
    return storage.query_glyphs(type=type, limit=limit)

@app.post("/glyphs")
async def create_glyph(glyph: GlyphNode):
    """Create a new glyph"""
    success = storage.upsert_glyph_node(glyph)
    if not success:
        return {"error": "Failed to create glyph"}
    return {"message": "Glyph created successfully", "id": glyph.id}

@app.get("/glyphs/count")
async def get_glyph_count():
    """Get total number of glyphs"""
    return {"count": storage.get_glyph_count()}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=False,  # Disable hot reload to save memory
    )
