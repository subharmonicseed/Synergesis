#!/usr/bin/env python3
"""
Test de sécurité pour l'API NOUS
================================

Ce script teste que la sécurité Bearer token fonctionne correctement.
"""

import requests
import json

API_BASE_URL = "http://localhost:8001"
VALID_TOKEN = "synergesis_nous_token_2025"
INVALID_TOKEN = "invalid_token"

def test_public_endpoints():
    """Test des endpoints publics (sans token)."""
    print("🔓 Test des endpoints publics...")
    
    # Test /health
    response = requests.get(f"{API_BASE_URL}/health")
    assert response.status_code == 200, f"Erreur /health: {response.status_code}"
    print("✅ /health accessible sans token")
    
    # Test /info
    response = requests.get(f"{API_BASE_URL}/info")
    assert response.status_code == 200, f"Erreur /info: {response.status_code}"
    data = response.json()
    assert "authentication" in data, "Info manquante sur l'authentification"
    print("✅ /info accessible sans token")

def test_protected_endpoints_without_token():
    """Test des endpoints protégés sans token (doit échouer)."""
    print("\n🔒 Test des endpoints protégés sans token...")
    
    # Test GET /concepts sans token
    response = requests.get(f"{API_BASE_URL}/concepts")
    assert response.status_code == 403, f"Erreur attendue 403, reçu: {response.status_code}"
    print("✅ GET /concepts bloqué sans token")
    
    # Test POST /concepts sans token
    concept_data = {
        "concept_id": "test_concept",
        "natural_prompt": "Test concept",
        "concept_type": "TEST",
        "source": "Test"
    }
    response = requests.post(f"{API_BASE_URL}/concepts", json=concept_data)
    assert response.status_code == 403, f"Erreur attendue 403, reçu: {response.status_code}"
    print("✅ POST /concepts bloqué sans token")

def test_protected_endpoints_with_invalid_token():
    """Test des endpoints protégés avec un token invalide (doit échouer)."""
    print("\n❌ Test des endpoints protégés avec token invalide...")
    
    headers = {"Authorization": f"Bearer {INVALID_TOKEN}"}
    
    # Test GET /concepts avec token invalide
    response = requests.get(f"{API_BASE_URL}/concepts", headers=headers)
    assert response.status_code == 401, f"Erreur attendue 401, reçu: {response.status_code}"
    print("✅ GET /concepts bloqué avec token invalide")

def test_protected_endpoints_with_valid_token():
    """Test des endpoints protégés avec un token valide (doit réussir)."""
    print("\n🔑 Test des endpoints protégés avec token valide...")
    
    headers = {"Authorization": f"Bearer {VALID_TOKEN}"}
    
    # Test GET /concepts avec token valide
    response = requests.get(f"{API_BASE_URL}/concepts", headers=headers)
    assert response.status_code == 200, f"Erreur GET /concepts: {response.status_code}"
    print("✅ GET /concepts accessible avec token valide")
    
    # Test POST /concepts avec token valide
    concept_data = {
        "concept_id": "test_security_concept",
        "natural_prompt": "Concept de test pour la sécurité",
        "concept_type": "TEST_SECURITY",
        "source": "SecurityTest"
    }
    response = requests.post(f"{API_BASE_URL}/concepts", json=concept_data, headers=headers)
    assert response.status_code == 201, f"Erreur POST /concepts: {response.status_code}"
    print("✅ POST /concepts accessible avec token valide")
    
    # Test GET concept spécifique
    response = requests.get(f"{API_BASE_URL}/concepts/test_security_concept", headers=headers)
    assert response.status_code == 200, f"Erreur GET concept: {response.status_code}"
    concept = response.json()
    assert concept["concept_id"] == "test_security_concept", "Concept ID incorrect"
    print("✅ GET concept spécifique accessible avec token valide")
    
    # Test DELETE concept
    response = requests.delete(f"{API_BASE_URL}/concepts/test_security_concept", headers=headers)
    assert response.status_code == 204, f"Erreur DELETE concept: {response.status_code}"
    print("✅ DELETE concept accessible avec token valide")

def test_bus_endpoints():
    """Test des endpoints de debug du bus."""
    print("\n🚌 Test des endpoints du bus...")
    
    headers = {"Authorization": f"Bearer {VALID_TOKEN}"}
    
    # Test /bus/history
    response = requests.get(f"{API_BASE_URL}/bus/history", headers=headers)
    assert response.status_code == 200, f"Erreur /bus/history: {response.status_code}"
    data = response.json()
    assert "events" in data, "Clé 'events' manquante"
    assert "count" in data, "Clé 'count' manquante"
    print("✅ /bus/history accessible avec token valide")
    
    # Test /bus/subscribers
    response = requests.get(f"{API_BASE_URL}/bus/subscribers", headers=headers)
    assert response.status_code == 200, f"Erreur /bus/subscribers: {response.status_code}"
    data = response.json()
    assert isinstance(data, dict), "Réponse doit être un dictionnaire"
    print("✅ /bus/subscribers accessible avec token valide")

def main():
    """Exécute tous les tests de sécurité."""
    print("🔐 Tests de sécurité de l'API NOUS")
    print("=" * 50)
    
    try:
        test_public_endpoints()
        test_protected_endpoints_without_token()
        test_protected_endpoints_with_invalid_token()
        test_protected_endpoints_with_valid_token()
        test_bus_endpoints()
        
        print("\n" + "=" * 50)
        print("🎉 Tous les tests de sécurité sont passés avec succès !")
        print("🔒 L'API NOUS est correctement sécurisée.")
        
    except AssertionError as e:
        print(f"\n❌ Échec du test: {e}")
        return 1
    except requests.exceptions.RequestException as e:
        print(f"\n🌐 Erreur de connexion: {e}")
        print("Assurez-vous que l'API NOUS est démarrée sur le port 8001")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

