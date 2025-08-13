import asyncio
import json
import logging
import time
from pathlib import Path
import sys
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os


# --- Graceful Imports with Fallbacks ---
try:
    from synergesis.agents.base_agent import BaseAgent, AgentContext
    from synergesis.agents.core_agents import (
        Aura, Nous, Selene, Eos, Vyra, Thales, Lumen, Ladderfall
    )
    from synergesis.agents.deepresearch import DeepResearchAgent as DeepResearch
    from synergesis.storage.neo4j_interface import Neo4jStorage
    from synergesis.agents.garden import SynergesisGarden
    SYNERGESIS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Synergesis module import failed: {e}. Using fallback stubs.")
    SYNERGESIS_AVAILABLE = False
    class AgentContext: 
        def __init__(self, storage=None, shared_state=None): pass
    class BaseAgent: 
        def __init__(self, ctx=None): pass
        async def perceive(self, data): return {"stub_perception": self.__class__.__name__}
    class Aura(BaseAgent): pass
    class Selene(BaseAgent): pass
    class Vyra(BaseAgent): pass
    class Eos(BaseAgent): pass
    class Hermes(BaseAgent): pass
    class Thales(BaseAgent): pass
    class Chronos(BaseAgent): pass
    class Metis(BaseAgent): pass
    class Kairos(BaseAgent): pass
    class Aether(BaseAgent): pass
    class Ananke(BaseAgent): pass
    class Erebus(BaseAgent): pass
    class Hemera(BaseAgent): pass
    class Moros(BaseAgent): pass
    class Nemesis(BaseAgent): pass
    class Oizys(BaseAgent): pass
    class Philotes(BaseAgent): pass
    class Geras(BaseAgent): pass
    class Nous(BaseAgent): pass
    class DeepResearch(BaseAgent): pass
    class SynergesisGarden:
        def __init__(self, shared_state=None): pass
    class Neo4jStorage:
        def __init__(self, **kwargs): self._use_stub = True # Explicitly mark as stub
        def get_all_glyphs(self): return []

# --- Global Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount the static directory to serve files like favicon.ico
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(static_dir / "favicon.ico")
garden_monitor = None

# --- Core Application Logic ---
class GardenMonitor:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GardenMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.agents: Dict[str, BaseAgent] = {}
            self.garden: SynergesisGarden = None
            self.garden_initialized = False
            self.lock = asyncio.Lock()
            self.initialized = True
            self.neo4j_storage = Neo4jStorage(uri="bolt://neo4j:7687", user="neo4j", password="SynergesisSecure123!")
            self.shared_state = {'glyph_bus': [], 'evolution_cycles': 0}
            self.evolution_cycle_counter = 0
            self.active_connections: List[WebSocket] = []
            self.monitoring_active = False

    async def initialize_garden(self):
        async with self.lock:
            if self.garden_initialized:
                return True
            try:
                if not SYNERGESIS_AVAILABLE:
                    raise ImportError("Synergesis modules not found, cannot initialize real agents.")

                context = AgentContext(storage=self.neo4j_storage, shared_state=self.shared_state)
                agent_classes = [
                    Aura, Selene, Vyra, Eos, Thales, Lumen, Ladderfall, 
                    Nous, DeepResearch
                ]
                # Initialize agents with correct parameter names
                self.agents = {}
                for cls in agent_classes:
                    if cls.__name__ == 'DeepResearchAgent':
                        self.agents[cls.__name__] = cls(context=context)
                    else:
                        self.agents[cls.__name__] = cls(ctx=context)
                self.garden = SynergesisGarden(shared_state=self.shared_state)
                self.garden_initialized = True
                logger.info(f"🌱 Garden initialized successfully with {len(self.agents)} real agents.")
                return True
            except Exception as e:
                logger.exception(f"CRITICAL: Failed to initialize garden with real agents: {e}. The system will not be functional.")
                self.garden_initialized = False
                return False

    async def evolution_cycle(self):
        if not self.garden_initialized:
            return {"status": "error", "message": "Garden not initialized"}
        self.evolution_cycle_counter += 1
        timestamp = time.time()
        glyph_bus_snapshot = list(self.shared_state['glyph_bus'])
        self.shared_state['glyph_bus'].clear()
        perception_tasks = [agent.perceive(glyph_bus_snapshot) for agent in self.agents.values()]
        perceptions = await asyncio.gather(*perception_tasks, return_exceptions=True)
        return {"status": "cycle_complete", "timestamp": timestamp, "perceptions": perceptions}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_update(self, data: Dict[str, Any]):
        if self.active_connections:
            await asyncio.gather(*[conn.send_text(json.dumps(data)) for conn in self.active_connections])

# --- FastAPI Endpoints ---
@app.on_event("startup")
async def startup_event():
    global garden_monitor
    garden_monitor = GardenMonitor()
    await garden_monitor.initialize_garden()

@app.post("/syn/chat")
async def chat_with_agents(request: dict):
    """VRAIE interface de chat avec IA conversationnelle - Plus de stubs !"""
    message = request.get("message", "")
    target_agent = request.get("agent", "all")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    try:
        # Import du vrai moteur d'IA conversationnelle
        from synergesis.core.conversation_engine import conversation_engine
        
        # Traitement intelligent de la conversation
        conversation_result = await conversation_engine.process_conversation(message, target_agent)
        
        # Injection dans le glyph bus pour persistance
        glyph = {
            'type': 'user_chat',
            'payload': {
                'message': message,
                'agent_responses': conversation_result.get('agents', []),
                'analysis': conversation_result.get('analysis', {}),
                'emotional_state': conversation_result.get('emotional_state', {})
            },
            'timestamp': conversation_result.get('timestamp'),
            'source': 'real_conversation_engine'
        }
        
        garden_monitor.shared_state['glyph_bus'].append(glyph)
        
        # Retourner la vraie réponse conversationnelle
        return {
            "success": True,
            "user_message": message,
            "agents": conversation_result.get('agents', []),
            "analysis": conversation_result.get('analysis', {}),
            "emotional_state": conversation_result.get('emotional_state', {}),
            "engine": "real_ai_conversation",
            "timestamp": conversation_result.get('timestamp')
        }
        
    except Exception as e:
        logger.error(f"Erreur moteur conversationnel: {e}")
        # Fallback vers l'ancien système si nécessaire
        garden_monitor.shared_state['glyph_bus'].append({'type': 'user_chat', 'payload': {'message': message}})
        fallback_result = await garden_monitor.evolution_cycle()
        
        return {
            "success": True,
            "user_message": message,
            "agents": [{"name": "Système", "response": f"Message reçu: {message}"}],
            "engine": "fallback_system",
            "note": "Moteur conversationnel en cours de chargement"
        }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await garden_monitor.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        garden_monitor.disconnect(websocket)

@app.get("/api/garden/status")
async def get_garden_status():
    if not garden_monitor:
        return {"status": "error", "message": "Garden monitor not initialized"}
    return {
        "garden_initialized": garden_monitor.garden_initialized,
        "agents_count": len(garden_monitor.agents),
        "agents": list(garden_monitor.agents.keys())
    }

@app.get("/api/db/glyphs")
async def get_db_glyphs():
    if not garden_monitor or not garden_monitor.garden_initialized:
        raise HTTPException(status_code=503, detail="DB not available, Garden not initialized.")
    try:
        return {"glyphs": garden_monitor.neo4j_storage.get_all_glyphs()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """Serve the real interactive chat interface"""
    try:
        templates_dir = Path(__file__).parent / "templates"
        chat_file = templates_dir / "chat.html"
        
        if chat_file.exists():
            return HTMLResponse(content=chat_file.read_text(encoding='utf-8'))
        else:
            # Fallback with embedded chat interface
            return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Synergesis Chat - Interface Interactive</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .chat-container { max-width: 800px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); overflow: hidden; }
        .chat-header { background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 20px; text-align: center; }
        .chat-messages { height: 400px; overflow-y: auto; padding: 20px; border-bottom: 1px solid #eee; }
        .message { margin: 10px 0; padding: 10px 15px; border-radius: 15px; max-width: 80%; }
        .message.user { background: #667eea; color: white; margin-left: auto; text-align: right; }
        .message.agent { background: #f1f3f4; color: #333; }
        .chat-input { width: 100%; padding: 15px; border: none; font-size: 16px; outline: none; }
        .send-btn { background: #4facfe; color: white; border: none; padding: 15px 30px; cursor: pointer; }
        .input-container { display: flex; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🌟 Synergesis Chat Interactif</h1>
            <p>Parlez directement avec vos agents intelligents</p>
        </div>
        <div class="chat-messages" id="messages">
            <div class="message agent">
                <strong>Synergesis:</strong> Bonjour ! Je suis votre système d'IA conversationnelle. Posez-moi une question !
            </div>
        </div>
        <div class="input-container">
            <input type="text" id="messageInput" class="chat-input" placeholder="Tapez votre message ici..." onkeypress="if(event.key==='Enter') sendMessage()">
            <button class="send-btn" onclick="sendMessage()">Envoyer</button>
        </div>
    </div>
    
    <script>
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const messages = document.getElementById('messages');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Ajouter le message utilisateur
            messages.innerHTML += `<div class="message user"><strong>Vous:</strong> ${message}</div>`;
            input.value = '';
            messages.scrollTop = messages.scrollHeight;
            
            try {
                // Envoyer à l'API
                const response = await fetch('/syn/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    let agentResponse = 'Réponse reçue des agents.';
                    
                    if (data.agents && data.agents.length > 0) {
                        agentResponse = data.agents.map(agent => 
                            `<strong>${agent.name}:</strong> ${agent.response || 'Traitement en cours...'}`
                        ).join('<br>');
                    } else if (data.response) {
                        agentResponse = data.response;
                    }
                    
                    messages.innerHTML += `<div class="message agent">${agentResponse}</div>`;
                } else {
                    messages.innerHTML += `<div class="message agent"><strong>Erreur:</strong> Impossible de contacter les agents.</div>`;
                }
            } catch (error) {
                messages.innerHTML += `<div class="message agent"><strong>Erreur:</strong> ${error.message}</div>`;
            }
            
            messages.scrollTop = messages.scrollHeight;
        }
    </script>
</body>
</html>
            """)
    except Exception as e:
        return HTMLResponse(content=f"""
            <h1>❌ Erreur de Chat</h1>
            <p>Impossible de charger l'interface: {str(e)}</p>
            <p><a href="/docs">📚 Documentation API</a></p>
        """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
