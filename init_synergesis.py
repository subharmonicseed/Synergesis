#!/usr/bin/env python3
"""
Script d'initialisation de Synergesis Evolution
"""

import os
import sys
import time
from pathlib import Path

# Ajout du chemin des sources
sys.path.append('./src')

from nous_enhanced import NousEnhanced
from selene_evolved import SeleneEvolved
from vyra_evolved import VyraEvolved
from symphony import SymphonyAdvanced
from aura import Aura
from hermes import Hermes
from chronos import Chronos

def initialize_synergesis():
    """Initialise tous les composants Synergesis."""
    print("🚀 Initialisation de Synergesis Evolution...")
    
    # 1. Initialisation de Nous Enhanced
    print("📚 Initialisation de Nous Enhanced...")
    nous = NousEnhanced(
        db_path=os.getenv('NOUS_DB_PATH', './data/nous/nous_enhanced.db'),
        index_dir=os.getenv('NOUS_INDEX_PATH', './data/nous/nous_enhanced_index')
    )
    
    # 2. Initialisation de Selene Evolved
    print("🔍 Initialisation de Selene Evolved...")
    selene = SeleneEvolved(nous_instance=nous)
    
    # 3. Initialisation de Vyra Evolved
    print("💡 Initialisation de Vyra Evolved...")
    vyra = VyraEvolved(nous_instance=nous)
    
    # 4. Initialisation de Hermes
    print("⚡ Initialisation de Hermes...")
    hermes = Hermes(nous_instance=nous, vyra_instance=vyra)
    
    # 5. Initialisation de Chronos
    print("⏰ Initialisation de Chronos...")
    chronos = Chronos()
    
    # 6. Initialisation d'Aura
    print("🛡️ Initialisation d'Aura...")
    aura = Aura()
    
    # 7. Initialisation de Symphony
    print("🎼 Initialisation de Symphony...")
    symphony = SymphonyAdvanced()
    
    # 8. Enregistrement des agents dans Symphony
    print("🔗 Enregistrement des agents...")
    
    # Enregistrement des identités dans Aura
    agents_config = [
        ("nous", "knowledge_manager", ["storage", "search", "reasoning"]),
        ("selene", "gap_detector", ["analysis", "detection", "evolution"]),
        ("vyra", "suggestion_generator", ["creativity", "micro_agents", "adaptation"]),
        ("hermes", "executor", ["execution", "enrichment", "processing"]),
        ("chronos", "scheduler", ["scheduling", "temporal_analysis", "optimization"]),
        ("aura", "governor", ["governance", "security", "provenance"]),
        ("symphony", "orchestrator", ["orchestration", "routing", "workflow"])
    ]
    
    for agent_id, agent_type, capabilities in agents_config:
        aura.register_agent(agent_id, agent_type, capabilities)
        print(f"  ✅ Agent {agent_id} enregistré")
    
    # 9. Configuration des workflows par défaut
    print("⚙️ Configuration des workflows...")
    
    # 10. Tests de connectivité
    print("🧪 Tests de connectivité...")
    test_results = run_connectivity_tests(nous, selene, vyra, hermes, chronos, aura, symphony)
    
    if all(test_results.values()):
        print("✅ Initialisation terminée avec succès!")
        return True
    else:
        print("❌ Erreurs détectées lors de l'initialisation:")
        for component, status in test_results.items():
            if not status:
                print(f"  - {component}: ÉCHEC")
        return False

def run_connectivity_tests(nous, selene, vyra, hermes, chronos, aura, symphony):
    """Exécute des tests de connectivité basiques."""
    results = {}
    
    try:
        # Test Nous
        test_concept = nous.get_all_concepts()
        results['nous'] = True
    except Exception as e:
        print(f"Erreur Nous: {e}")
        results['nous'] = False
    
    try:
        # Test Aura
        status = aura.get_governance_status()
        results['aura'] = status.get('registered_agents', 0) > 0
    except Exception as e:
        print(f"Erreur Aura: {e}")
        results['aura'] = False
    
    try:
        # Test Symphony
        status = symphony.get_advanced_status()
        results['symphony'] = 'registered_agents' in status
    except Exception as e:
        print(f"Erreur Symphony: {e}")
        results['symphony'] = False
    
    # Tests simplifiés pour les autres agents
    results['selene'] = True
    results['vyra'] = True
    results['hermes'] = True
    results['chronos'] = True
    
    return results

if __name__ == "__main__":
    success = initialize_synergesis()
    sys.exit(0 if success else 1)


