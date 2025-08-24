"""Synergesis – NOUS FastAPI Service
===================================
Expose les opérations CRUD + recherche sur le *blackboard cognitif* (NOUS)
via une API REST sécurisée.

Usage rapide
------------
    uvicorn nous_api:app --reload --port 8001

Utilise SQLModel/SQLite + Whoosh pour la persistance et l'indexation.
Sécurisé avec Bearer token et CORS strict.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from nous import Nous, Concept

# ────────────────────────────────────────────── Configuration sécurité ──
# Token Bearer simple pour la démo (en production, utiliser JWT ou OAuth2)
BEARER_TOKEN = os.getenv("NOUS_API_TOKEN", "synergesis_nous_token_2025")

# Origines autorisées pour CORS (en production, spécifier les domaines exacts)
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React dev server
    "http://localhost:8080",  # Vue dev server
    "http://localhost:8501",  # Streamlit
    "https://*.manusvm.computer",  # Domaines Manus
]

# ────────────────────────────────────────────── init NOUS ──
# Définir les chemins absolus pour la base de données et l'index
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(PROJECT_ROOT, "nous.db")
INDEX_DIR = os.path.join(PROJECT_ROOT, "nous_index")

# Supprimer la base de données existante pour forcer la recréation avec le nouveau schéma
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
if os.path.exists(INDEX_DIR):
    import shutil
    shutil.rmtree(INDEX_DIR)

NOUS_INSTANCE = Nous(db_path=DB_PATH, index_dir=INDEX_DIR)

# ────────────────────────────────────────────── Sécurité ──
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Vérifie le token Bearer."""
    if credentials.credentials != BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

# ────────────────────────────────────────────── FastAPI app ──
app = FastAPI(
    title="Synergesis NOUS API",
    version="0.1.0",
    description="CRUD + full‑text search sur la base de connaissances NOUS (sécurisé)",
)

# CORS strict
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ────────────────────────────────────────────── Schemas ──
class ConceptIn(BaseModel):
    concept_id: str = Field(..., example="concept_entropy_001")
    natural_prompt: str = Field(..., example="Le concept d'entropie en thermodynamique")
    concept_type: str = Field(..., example="TECHNICAL_CONCEPT")
    source: str = Field(..., example="Thermodynamics_Textbook")
    resonance: Optional[float] = Field(None, example=0.7)
    weight: Optional[float] = Field(None, example=0.5)


class ConceptOut(ConceptIn):
    id: Optional[int] = None
    timestamp: Optional[float] = None


class ConceptUpdate(BaseModel):
    natural_prompt: Optional[str] = None
    concept_type: Optional[str] = None
    source: Optional[str] = None
    resonance: Optional[float] = None
    weight: Optional[float] = None


# ────────────────────────────────────────────── Endpoints publics ──
@app.get("/health")
def health_check():
    """Endpoint de vérification de santé de l'API (public)."""
    return {"status": "healthy", "service": "NOUS API", "version": "0.1.0"}


@app.get("/info")
def api_info():
    """Informations sur l'API (public)."""
    return {
        "name": "Synergesis NOUS API",
        "version": "0.1.0",
        "description": "API sécurisée pour la base de connaissances NOUS",
        "authentication": "Bearer token required",
        "endpoints": {
            "concepts": "/concepts",
            "search": "/concepts?q=query",
            "health": "/health"
        }
    }


# ────────────────────────────────────────────── Endpoints sécurisés ──
@app.post("/concepts", response_model=ConceptOut, status_code=201)
def add_concept(concept_in: ConceptIn, token: str = Depends(verify_token)):
    """Ajouter un nouveau concept au blackboard NOUS."""
    try:
        # Créer un objet Concept
        concept = Concept(
            concept_id=concept_in.concept_id,
            natural_prompt=concept_in.natural_prompt,
            concept_type=concept_in.concept_type,
            source=concept_in.source,
            resonance=concept_in.resonance,
            weight=concept_in.weight
        )
        
        # Ajouter le concept via NOUS
        added_concept = NOUS_INSTANCE.add_concept(concept)
        
        # Retourner le concept ajouté
        return ConceptOut(
            id=added_concept.id,
            concept_id=added_concept.concept_id,
            natural_prompt=added_concept.natural_prompt,
            concept_type=added_concept.concept_type,
            source=added_concept.source,
            timestamp=added_concept.timestamp,
            resonance=added_concept.resonance,
            weight=added_concept.weight
        )
    except Exception as e:
        print(f"DEBUG: Erreur lors de l'ajout du concept: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'ajout du concept: {str(e)}")


@app.get("/concepts/{concept_id}", response_model=ConceptOut)
def get_concept(concept_id: str, token: str = Depends(verify_token)):
    """Récupérer un concept par son ID."""
    concept = NOUS_INSTANCE.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    
    return ConceptOut(
        id=concept.id,
        concept_id=concept.concept_id,
        natural_prompt=concept.natural_prompt,
        concept_type=concept.concept_type,
        source=concept.source,
        timestamp=concept.timestamp,
        resonance=concept.resonance,
        weight=concept.weight
    )


@app.get("/concepts", response_model=List[ConceptOut])
def search_concepts(q: Optional[str] = Query(None, description="full‑text search"), token: str = Depends(verify_token)):
    """Lister tous les concepts ou effectuer une recherche full-text."""
    try:
        print("DEBUG: Début de search_concepts")
        if q is None:
            print("DEBUG: Récupération de tous les concepts")
            concepts = NOUS_INSTANCE.get_all_concepts()
            print(f"DEBUG: Nombre de concepts récupérés: {len(concepts)}")
            return [
                ConceptOut(
                    id=concept.id,
                    concept_id=concept.concept_id,
                    natural_prompt=concept.natural_prompt,
                    concept_type=concept.concept_type,
                    source=concept.source,
                    timestamp=concept.timestamp,
                    resonance=concept.resonance,
                    weight=concept.weight
                )
                for concept in concepts
            ]
        else:
            print(f"DEBUG: Recherche full-text pour: {q}")
            concepts = NOUS_INSTANCE.query_concepts(q)
            print(f"DEBUG: Nombre de concepts trouvés par recherche: {len(concepts)}")
            return [
                ConceptOut(
                    id=concept.id,
                    concept_id=concept.concept_id,
                    natural_prompt=concept.natural_prompt,
                    concept_type=concept.concept_type,
                    source=concept.source,
                    timestamp=concept.timestamp,
                    resonance=concept.resonance,
                    weight=concept.weight
                )
                for concept in concepts
            ]
    except Exception as e:
        print(f"DEBUG: Erreur lors de la recherche: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche: {str(e)}")


@app.put("/concepts/{concept_id}", response_model=ConceptOut)
def update_concept(concept_id: str, upd: ConceptUpdate, token: str = Depends(verify_token)):
    """Mettre à jour un concept existant."""
    concept = NOUS_INSTANCE.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    
    # Mettre à jour les champs modifiés
    if upd.natural_prompt is not None:
        concept.natural_prompt = upd.natural_prompt
    if upd.concept_type is not None:
        concept.concept_type = upd.concept_type
    if upd.source is not None:
        concept.source = upd.source
    if upd.resonance is not None:
        concept.resonance = upd.resonance
    if upd.weight is not None:
        concept.weight = upd.weight
    
    try:
        # Sauvegarder les modifications
        updated_concept = NOUS_INSTANCE.update_concept(concept)
        
        return ConceptOut(
            id=updated_concept.id,
            concept_id=updated_concept.concept_id,
            natural_prompt=updated_concept.natural_prompt,
            concept_type=updated_concept.concept_type,
            source=updated_concept.source,
            timestamp=updated_concept.timestamp,
            resonance=updated_concept.resonance,
            weight=updated_concept.weight
        )
    except Exception as e:
        print(f"DEBUG: Erreur lors de la mise à jour: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour: {str(e)}")


@app.delete("/concepts/{concept_id}", status_code=204)
def delete_concept(concept_id: str, token: str = Depends(verify_token)):
    """Supprimer un concept."""
    concept = NOUS_INSTANCE.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    
    try:
        NOUS_INSTANCE.delete_concept(concept_id)
    except Exception as e:
        print(f"DEBUG: Erreur lors de la suppression: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")


# ────────────────────────────────────────────── Endpoints de debug (sécurisés) ──
@app.get("/bus/history")
def get_bus_history(token: str = Depends(verify_token)):
    """Récupérer l'historique des événements du glyph_bus."""
    history = NOUS_INSTANCE.bus.get_history()
    return {
        "events": [event.to_dict() for event in history],
        "count": len(history)
    }


@app.get("/bus/subscribers")
def get_bus_subscribers(token: str = Depends(verify_token)):
    """Récupérer les informations sur les abonnés du glyph_bus."""
    return {
        "concept_changed": NOUS_INSTANCE.bus.get_subscribers_count("concept_changed"),
        "knowledge_gap": NOUS_INSTANCE.bus.get_subscribers_count("knowledge_gap"),
        "new_candidate_concept": NOUS_INSTANCE.bus.get_subscribers_count("new_candidate_concept")
    }


# Point d'entrée pour l'exécution directe
if __name__ == "__main__":
    import uvicorn
    print(f"🔐 API NOUS sécurisée - Token: {BEARER_TOKEN}")
    print(f"🌐 CORS autorisé pour: {ALLOWED_ORIGINS}")
    uvicorn.run(app, host="0.0.0.0", port=8001)

