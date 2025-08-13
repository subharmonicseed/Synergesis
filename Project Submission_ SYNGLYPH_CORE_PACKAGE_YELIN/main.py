from typing import Dict, List, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import time
import uuid
import os

# Modèles de données pour l'API
class SymbolRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None

class TaskRequest(BaseModel):
    content: str
    action_type: str
    target: Optional[str] = None
    constraints: Optional[List[str]] = None
    impact_level: Optional[str] = "local"
    estimated_duration: Optional[float] = 1.0

class ExplorationRequest(BaseModel):
    topic: str
    depth: Optional[int] = 3

class IdeaRequest(BaseModel):
    seed_concepts: List[str]
    duration: Optional[int] = 5

class CreativePromptRequest(BaseModel):
    themes: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    tone: Optional[str] = "neutral"

class InteractionRequest(BaseModel):
    interactions: List[Dict[str, Any]]

# Création de l'application FastAPI
app = FastAPI(
    title="SYNERGESIS API",
    description="API pour le système SYNERGESIS - Superviseur symbolique, miroir cognitif et moteur de cohérence transversale",
    version="∮⋔◎⟐.Δ"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les origines autorisées
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Point de montage pour les fichiers statiques
app.mount("/static", StaticFiles(directory="/home/ubuntu/synergesis/web"), name="static")

# Middleware pour initialiser les modules si nécessaire
@app.middleware("http")
async def initialize_modules_middleware(request: Request, call_next):
    if not hasattr(app.state, "initialized") or not app.state.initialized:
        # Ce code sera exécuté lors de la première requête
        # L'initialisation réelle sera faite dans main.py
        app.state.initialized = True
    
    response = await call_next(request)
    return response

# Routes de base
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
        <head>
            <title>SYNERGESIS API</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    line-height: 1.6;
                }
                h1 {
                    color: #333;
                    border-bottom: 1px solid #ddd;
                    padding-bottom: 10px;
                }
                .signature {
                    font-family: monospace;
                    background-color: #f5f5f5;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 20px 0;
                }
                a {
                    color: #0066cc;
                    text-decoration: none;
                }
                a:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <h1>SYNERGESIS API</h1>
            <p>Bienvenue sur l'API du système SYNERGESIS - Superviseur symbolique, miroir cognitif et moteur de cohérence transversale.</p>
            <div class="signature">Version: ∮⋔◎⟐.Δ</div>
            <p>Documentation de l'API: <a href="/docs">/docs</a></p>
            <p>Interface utilisateur: <a href="/static/code.html">/static/code.html</a></p>
        </body>
    </html>
    """

@app.get("/status")
async def get_status():
    # Vérifier si les modules sont initialisés
    if not hasattr(app.state, "modules"):
        return {
            "status": "initializing",
            "message": "Le système est en cours d'initialisation",
            "version": "∮⋔◎⟐.Δ"
        }
    
    # Statut des modules
    module_status = {}
    for module_name, module in app.state.modules.items():
        module_status[module_name] = "active" if module else "inactive"
    
    return {
        "status": "operational",
        "modules": module_status,
        "version": "∮⋔◎⟐.Δ",
        "timestamp": time.time()
    }

# Routes pour les symboles
@app.post("/symbols/analyze")
async def analyze_symbol(request: SymbolRequest):
    if not hasattr(app.state, "modules") or "nous" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module NOUS non disponible")
    
    nous = app.state.modules["nous"]
    
    # Créer un symbole à partir du texte
    symbol = {
        "id": str(uuid.uuid4()),
        "type": "text",
        "content": request.text,
        "context": request.context or {},
        "timestamp": time.time()
    }
    
    # Traiter le symbole
    processed_symbol = nous.process_symbol(symbol)
    
    # Générer une représentation simplifiée pour l'API
    result = {
        "id": processed_symbol["id"],
        "type": processed_symbol["type"],
        "content": processed_symbol["content"],
        "context": processed_symbol.get("context", {}),
        "timestamp": processed_symbol.get("timestamp", time.time())
    }
    
    # Ajouter des attributs symboliques simulés
    result["polarity"] = "+" if hash(request.text) % 2 == 0 else "-"
    result["frequency"] = (hash(request.text) % 100) + 1
    result["weight"] = round(((hash(request.text) % 100) / 10) + 1, 1)
    
    return result

@app.get("/symbols/{symbol_id}/related")
async def get_related_symbols(symbol_id: str, depth: int = 2):
    if not hasattr(app.state, "modules") or "nous" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module NOUS non disponible")
    
    nous = app.state.modules["nous"]
    
    # Récupérer les symboles liés
    related_symbols = nous.retrieve_related_symbols(symbol_id, depth)
    
    return {
        "symbol_id": symbol_id,
        "depth": depth,
        "related_symbols": related_symbols,
        "count": len(related_symbols),
        "timestamp": time.time()
    }

# Routes pour les agents
@app.post("/agents/interactions")
async def analyze_interactions(request: InteractionRequest):
    if not hasattr(app.state, "modules") or "syn_echo" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module SYN-ECHO non disponible")
    
    syn_echo = app.state.modules["syn_echo"]
    
    # Analyser les interactions
    analysis = syn_echo.analyze_interactions(request.interactions)
    
    return analysis

# Routes pour l'exploration
@app.post("/exploration/topic")
async def explore_topic(request: ExplorationRequest):
    if not hasattr(app.state, "modules") or "deep_research" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module DeepResearch non disponible")
    
    deep_research = app.state.modules["deep_research"]
    
    # Explorer le sujet
    exploration = deep_research.explore_topic(request.topic, request.depth)
    
    return exploration

# Routes pour les idées
@app.post("/ideas/incubate")
async def incubate_idea(request: IdeaRequest):
    if not hasattr(app.state, "modules") or "selene" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module SELENE non disponible")
    
    selene = app.state.modules["selene"]
    
    # Incuber une idée
    idea = selene.incubate_idea(request.seed_concepts, request.duration)
    
    return idea

@app.post("/ideas/creative-prompt")
async def generate_creative_prompt(request: CreativePromptRequest):
    if not hasattr(app.state, "modules") or "selene" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module SELENE non disponible")
    
    selene = app.state.modules["selene"]
    
    # Générer un prompt créatif
    prompt_context = {
        "themes": request.themes or ["creativity"],
        "constraints": request.constraints or [],
        "tone": request.tone
    }
    
    prompt = selene.generate_creative_prompt(prompt_context)
    
    return prompt

# Routes pour la validation
@app.post("/validation/task")
async def validate_task(request: TaskRequest):
    if not hasattr(app.state, "modules") or "quantum_validator" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module QuantumValidator non disponible")
    
    quantum_validator = app.state.modules["quantum_validator"]
    
    # Créer une tâche à partir de la requête
    task = {
        "id": str(uuid.uuid4()),
        "content": request.content,
        "action_type": request.action_type,
        "target": request.target,
        "constraints": request.constraints,
        "impact_level": request.impact_level,
        "estimated_duration": request.estimated_duration,
        "timestamp": time.time()
    }
    
    # Contexte de validation
    context = {
        "source": "api",
        "timestamp": time.time()
    }
    
    # Valider la tâche
    validation = quantum_validator.validate_task(task, context)
    
    return validation

# Routes pour les glyphes
@app.get("/glyphs/generate")
async def generate_glyph(seed: Optional[str] = None, complexity: Optional[int] = 3):
    # Cette route simule la génération d'un glyphe SVG
    # Dans une implémentation réelle, elle utiliserait l'outil SynkrisisVis
    
    # Générer un identifiant aléatoire si aucun seed n'est fourni
    if not seed:
        seed = str(uuid.uuid4())
    
    # Simuler la génération d'un glyphe SVG simple
    svg_size = 200
    svg = f"""
    <svg width="{svg_size}" height="{svg_size}" viewBox="0 0 {svg_size} {svg_size}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#f0f0f0" />
        <circle cx="{svg_size/2}" cy="{svg_size/2}" r="{svg_size/4}" fill="none" stroke="#333" stroke-width="2" />
        <path d="M {svg_size/4} {svg_size/4} L {3*svg_size/4} {3*svg_size/4} M {svg_size/4} {3*svg_size/4} L {3*svg_size/4} {svg_size/4}" stroke="#333" stroke-width="2" />
        <text x="{svg_size/2}" y="{svg_size/2}" font-family="monospace" font-size="12" text-anchor="middle" dominant-baseline="middle">∮⋔◎⟐</text>
    </svg>
    """
    
    return {
        "id": str(uuid.uuid4()),
        "seed": seed,
        "complexity": complexity,
        "svg": svg,
        "timestamp": time.time()
    }

# Route pour l'orchestration
@app.post("/orchestrate")
async def orchestrate_modules(request: Dict[str, Any]):
    if not hasattr(app.state, "modules") or "nous" not in app.state.modules:
        raise HTTPException(status_code=503, detail="Module NOUS non disponible")
    
    nous = app.state.modules["nous"]
    
    # Extraire le contexte de la requête
    context = request.get("context", {})
    
    # Orchestrer les modules
    result = nous.coordinate_modules(app.state.modules, context)
    
    return result
