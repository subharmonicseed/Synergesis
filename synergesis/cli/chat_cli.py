#!/usr/bin/env python3
"""
Synergesis CLI Chat Interface - VRAIE CONVERSATION EN LIGNE DE COMMANDE
======================================================================
Interface simple et directe pour parler avec vos agents sans navigateur.
Plus de gadgets - juste une conversation authentique !
"""

import asyncio
import json
import sys
import os
from typing import Dict, Any
from datetime import datetime

# Ajouter le chemin du projet pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from synergesis.core.conversation_engine import conversation_engine
    CONVERSATION_ENGINE_AVAILABLE = True
except ImportError:
    CONVERSATION_ENGINE_AVAILABLE = False
    print("⚠️ Moteur conversationnel non disponible - mode fallback")

class SynergesisCliChat:
    """Interface CLI pour chat avec les agents Synergesis"""
    
    def __init__(self):
        self.running = True
        self.conversation_count = 0
        
    def print_banner(self):
        """Affiche la bannière de bienvenue"""
        print("\n" + "="*60)
        print("🌟 SYNERGESIS CLI CHAT - INTERFACE CONVERSATIONNELLE")
        print("="*60)
        print("💬 Parlez directement avec vos agents intelligents")
        print("🤖 Agents disponibles: Aura, Nous, Selene, Thales, DeepResearch, Eos, Vyra, Lumen, Ladderfall")
        print("📝 Tapez 'help' pour les commandes, 'quit' pour quitter")
        print("="*60 + "\n")
        
        if CONVERSATION_ENGINE_AVAILABLE:
            print("✅ Moteur d'IA conversationnelle: ACTIF")
        else:
            print("⚠️ Moteur d'IA conversationnelle: INDISPONIBLE (mode fallback)")
        print()
    
    def print_help(self):
        """Affiche l'aide"""
        print("\n📚 COMMANDES DISPONIBLES:")
        print("  help          - Affiche cette aide")
        print("  quit, exit    - Quitte le chat")
        print("  clear         - Efface l'écran")
        print("  status        - Affiche le statut du système")
        print("  agents        - Liste les agents disponibles")
        print("  @agent_name   - Parle à un agent spécifique (ex: @Aura)")
        print("  history       - Affiche l'historique des conversations")
        print("\n💡 Tapez simplement votre message pour parler à tous les agents !")
        print()
    
    def print_agents(self):
        """Affiche la liste des agents"""
        print("\n🤖 AGENTS DISPONIBLES:")
        agents = {
            "Aura": "Empathie et Résonance Émotionnelle",
            "Nous": "Raisonnement Collectif et Logique", 
            "Selene": "Créativité et Inspiration",
            "Thales": "Vérification Logique et Cohérence",
            "DeepResearch": "Recherche Approfondie Multi-Sources",
            "Eos": "Nouveaux Commencements et Éveil",
            "Vyra": "Reconnaissance de Motifs",
            "Lumen": "Illumination et Clarté",
            "Ladderfall": "Cascades d'Information"
        }
        
        for name, role in agents.items():
            print(f"  • {name:<12} - {role}")
        print()
    
    def print_status(self):
        """Affiche le statut du système"""
        print("\n📊 STATUT DU SYSTÈME:")
        print(f"  • Moteur IA: {'✅ ACTIF' if CONVERSATION_ENGINE_AVAILABLE else '❌ INDISPONIBLE'}")
        print(f"  • Conversations: {self.conversation_count}")
        print(f"  • Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if CONVERSATION_ENGINE_AVAILABLE:
            try:
                summary = conversation_engine.get_conversation_summary()
                print(f"  • Échanges totaux: {summary.get('total_exchanges', 0)}")
                print(f"  • État émotionnel: {summary.get('current_emotional_state', {}).get('global_mood', 'neutre')}")
            except Exception as e:
                print(f"  • Erreur récupération statut: {e}")
        print()
    
    async def process_message(self, message: str, target_agent: str = "all") -> Dict[str, Any]:
        """Traite un message avec le moteur conversationnel"""
        if CONVERSATION_ENGINE_AVAILABLE:
            try:
                return await conversation_engine.process_conversation(message, target_agent)
            except Exception as e:
                print(f"❌ Erreur moteur conversationnel: {e}")
                return self.fallback_response(message, target_agent)
        else:
            return self.fallback_response(message, target_agent)
    
    def fallback_response(self, message: str, target_agent: str) -> Dict[str, Any]:
        """Réponse de fallback si le moteur n'est pas disponible"""
        return {
            "user_message": message,
            "agents": [{
                "name": "Système",
                "response": f"Message reçu: '{message}'. Moteur conversationnel en cours de chargement...",
                "confidence": 0.5
            }],
            "analysis": {"topics": ["système"], "emotions": [], "intentions": ["test"]},
            "timestamp": datetime.now().isoformat(),
            "engine": "fallback"
        }
    
    def format_response(self, result: Dict[str, Any]):
        """Formate et affiche la réponse des agents"""
        agents = result.get("agents", [])
        analysis = result.get("analysis", {})
        
        print("\n" + "─"*50)
        
        # Afficher l'analyse si disponible
        if analysis.get("emotions") or analysis.get("topics"):
            print("🧠 Analyse:")
            if analysis.get("emotions"):
                print(f"   Émotions détectées: {', '.join(analysis['emotions'])}")
            if analysis.get("topics"):
                print(f"   Sujets identifiés: {', '.join(analysis['topics'])}")
            print()
        
        # Afficher les réponses des agents
        for agent in agents:
            name = agent.get("name", "Agent")
            response = agent.get("response", "Pas de réponse")
            confidence = agent.get("confidence", 0.0)
            
            print(f"🤖 {name} (confiance: {confidence:.1%}):")
            print(f"   {response}")
            print()
        
        print("─"*50 + "\n")
    
    def parse_command(self, user_input: str) -> tuple:
        """Parse la commande utilisateur"""
        user_input = user_input.strip()
        
        if user_input.startswith('@'):
            # Commande pour agent spécifique
            parts = user_input[1:].split(' ', 1)
            if len(parts) == 2:
                agent_name, message = parts
                return agent_name.capitalize(), message
            else:
                return "help", ""
        
        return "all", user_input
    
    async def run(self):
        """Boucle principale du chat CLI"""
        self.print_banner()
        
        while self.running:
            try:
                # Prompt utilisateur
                user_input = input("💬 Vous: ").strip()
                
                if not user_input:
                    continue
                
                # Commandes spéciales
                if user_input.lower() in ['quit', 'exit']:
                    print("\n👋 Au revoir ! Merci d'avoir utilisé Synergesis Chat.")
                    break
                elif user_input.lower() == 'help':
                    self.print_help()
                    continue
                elif user_input.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    self.print_banner()
                    continue
                elif user_input.lower() == 'status':
                    self.print_status()
                    continue
                elif user_input.lower() == 'agents':
                    self.print_agents()
                    continue
                elif user_input.lower() == 'history':
                    if CONVERSATION_ENGINE_AVAILABLE:
                        try:
                            summary = conversation_engine.get_conversation_summary()
                            print(f"\n📜 Historique: {summary.get('total_exchanges', 0)} échanges")
                            if summary.get('last_exchange'):
                                last = summary['last_exchange']
                                print(f"Dernier échange: {last.get('user_message', 'N/A')}")
                        except Exception as e:
                            print(f"❌ Erreur historique: {e}")
                    else:
                        print("📜 Historique non disponible (moteur conversationnel inactif)")
                    print()
                    continue
                
                # Traitement du message
                target_agent, message = self.parse_command(user_input)
                
                if not message:
                    print("❌ Message vide. Tapez 'help' pour l'aide.")
                    continue
                
                print(f"\n🔄 Traitement en cours...")
                
                # Traiter avec le moteur conversationnel
                result = await self.process_message(message, target_agent)
                
                # Afficher la réponse
                self.format_response(result)
                
                self.conversation_count += 1
                
            except KeyboardInterrupt:
                print("\n\n👋 Interruption détectée. Au revoir !")
                break
            except Exception as e:
                print(f"\n❌ Erreur inattendue: {e}")
                print("Tapez 'help' pour l'aide ou 'quit' pour quitter.\n")

def main():
    """Point d'entrée principal"""
    chat = SynergesisCliChat()
    
    try:
        asyncio.run(chat.run())
    except KeyboardInterrupt:
        print("\n👋 Au revoir !")
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
