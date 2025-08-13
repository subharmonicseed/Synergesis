# Système de Logging des Échanges Inter-Agents en Temps Réel
# Capture et stocke toutes les communications entre agents pour le dashboard

import time
import json
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import threading

class AgentCommunicationLogger:
    """
    Logger spécialisé pour capturer les échanges entre agents
    Intégré au dashboard pour monitoring en temps réel
    """
    
    def __init__(self):
        self.storage = None
        self.lock = threading.Lock()
        
        # Initialiser le stockage persistant
        try:
            from synergesis.core.persistent_storage import get_persistent_storage
            self.storage = get_persistent_storage()
        except ImportError:
            print("⚠️ Stockage persistant non disponible pour AgentLogger")
    
    def log_agent_communication(self, 
                               source_agent: str, 
                               target_agent: str, 
                               message_type: str,
                               content: str,
                               metadata: Dict[str, Any] = None) -> bool:
        """Logger une communication entre agents"""
        try:
            with self.lock:
                log_entry = {
                    'source_agent': source_agent,
                    'target_agent': target_agent,
                    'message_type': message_type,
                    'content': content,
                    'metadata': metadata or {},
                    'timestamp': time.time(),
                    'communication_id': f"comm-{int(time.time() * 1000)}"
                }
                
                # Stocker dans la base persistante
                if self.storage:
                    success = self.storage.log_system_event(
                        agent_name=f"{source_agent}→{target_agent}",
                        message=f"[{message_type}] {content}",
                        level="COMM",
                        metadata=log_entry
                    )
                    
                    if success:
                        print(f"📡 Communication loggée: {source_agent} → {target_agent}")
                        return True
                
                return False
                
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur logging communication: {str(e)}")
            return False
    
    def log_glyph_generation(self, 
                           agent_name: str, 
                           glyph_data: Dict[str, Any],
                           trigger_context: str = "") -> bool:
        """Logger la génération d'un glyph par un agent"""
        try:
            content = f"Glyph généré: {glyph_data.get('visual_symbol', '🌸')} - {glyph_data.get('content', 'N/A')[:100]}"
            
            metadata = {
                'glyph_id': glyph_data.get('id', 'unknown'),
                'visual_symbol': glyph_data.get('visual_symbol', ''),
                'purity_score': glyph_data.get('purity_score', 0),
                'trigger_context': trigger_context,
                'symbolic_properties': glyph_data.get('symbolic_properties', {})
            }
            
            return self.log_agent_communication(
                source_agent=agent_name,
                target_agent="JARDIN",
                message_type="GLYPH_CREATION",
                content=content,
                metadata=metadata
            )
            
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur logging glyph: {str(e)}")
            return False
    
    def log_agent_activation(self, 
                           agent_name: str, 
                           activation_reason: str,
                           processing_result: str = "") -> bool:
        """Logger l'activation d'un agent"""
        try:
            content = f"Agent activé: {activation_reason}"
            if processing_result:
                content += f" → {processing_result[:100]}"
            
            metadata = {
                'activation_reason': activation_reason,
                'processing_result': processing_result,
                'activation_timestamp': time.time()
            }
            
            return self.log_agent_communication(
                source_agent="SYSTEM",
                target_agent=agent_name,
                message_type="AGENT_ACTIVATION",
                content=content,
                metadata=metadata
            )
            
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur logging activation: {str(e)}")
            return False
    
    def log_nous_update(self, 
                       concept: str, 
                       source_agent: str,
                       importance: float = 0.5) -> bool:
        """Logger une mise à jour de NOUS"""
        try:
            content = f"Concept ajouté à NOUS: {concept}"
            
            metadata = {
                'concept': concept,
                'importance': importance,
                'source_agent': source_agent
            }
            
            return self.log_agent_communication(
                source_agent=source_agent,
                target_agent="NOUS",
                message_type="KNOWLEDGE_UPDATE",
                content=content,
                metadata=metadata
            )
            
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur logging NOUS: {str(e)}")
            return False
    
    def log_quantum_processing(self, 
                             agent_name: str, 
                             quantum_data: Dict[str, Any]) -> bool:
        """Logger un traitement quantique"""
        try:
            content = f"Traitement quantique: {quantum_data.get('operation', 'unknown')}"
            
            metadata = {
                'quantum_operation': quantum_data.get('operation', ''),
                'energy_level': quantum_data.get('energy', 0),
                'coherence': quantum_data.get('coherence', 0),
                'qubits_used': quantum_data.get('qubits', 0)
            }
            
            return self.log_agent_communication(
                source_agent=agent_name,
                target_agent="QUANTUM_CORE",
                message_type="QUANTUM_PROCESSING",
                content=content,
                metadata=metadata
            )
            
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur logging quantum: {str(e)}")
            return False
    
    def log_deepresearch_query(self, 
                             query: str, 
                             sources_found: List[str],
                             verification_level: str) -> bool:
        """Logger une requête DeepResearch"""
        try:
            content = f"Recherche: {query} → {len(sources_found)} sources ({verification_level})"
            
            metadata = {
                'query': query,
                'sources_found': sources_found,
                'verification_level': verification_level,
                'source_count': len(sources_found)
            }
            
            return self.log_agent_communication(
                source_agent="DeepResearch",
                target_agent="KNOWLEDGE_BASE",
                message_type="RESEARCH_QUERY",
                content=content,
                metadata=metadata
            )
            
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur logging research: {str(e)}")
            return False
    
    def get_recent_communications(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupérer les communications récentes"""
        try:
            if not self.storage:
                return []
            
            # Récupérer les logs de communication
            logs = self.storage.get_system_logs(limit=limit)
            
            # Filtrer les communications inter-agents
            communications = []
            for log in logs:
                if '→' in log.get('agent_name', '') or log.get('level') == 'COMM':
                    communications.append({
                        'id': log.get('id'),
                        'source_agent': log.get('agent_name', '').split('→')[0] if '→' in log.get('agent_name', '') else 'SYSTEM',
                        'target_agent': log.get('agent_name', '').split('→')[1] if '→' in log.get('agent_name', '') else 'UNKNOWN',
                        'message': log.get('message', ''),
                        'level': log.get('level', 'INFO'),
                        'timestamp': log.get('timestamp', 0),
                        'metadata': log.get('metadata', {})
                    })
            
            return communications
            
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur récupération communications: {str(e)}")
            return []
    
    def get_agent_activity_summary(self, agent_name: str = None) -> Dict[str, Any]:
        """Résumé de l'activité d'un agent ou de tous les agents"""
        try:
            communications = self.get_recent_communications(limit=200)
            
            if agent_name:
                # Filtrer pour un agent spécifique
                agent_comms = [c for c in communications 
                              if c['source_agent'] == agent_name or c['target_agent'] == agent_name]
                
                return {
                    'agent_name': agent_name,
                    'total_communications': len(agent_comms),
                    'as_source': len([c for c in agent_comms if c['source_agent'] == agent_name]),
                    'as_target': len([c for c in agent_comms if c['target_agent'] == agent_name]),
                    'recent_activity': agent_comms[:10],
                    'last_activity': max([c['timestamp'] for c in agent_comms]) if agent_comms else 0
                }
            else:
                # Résumé global
                agents = set()
                for comm in communications:
                    agents.add(comm['source_agent'])
                    agents.add(comm['target_agent'])
                
                agent_stats = {}
                for agent in agents:
                    if agent not in ['SYSTEM', 'UNKNOWN']:
                        agent_comms = [c for c in communications 
                                      if c['source_agent'] == agent or c['target_agent'] == agent]
                        agent_stats[agent] = {
                            'total_communications': len(agent_comms),
                            'last_activity': max([c['timestamp'] for c in agent_comms]) if agent_comms else 0
                        }
                
                return {
                    'total_agents': len(agent_stats),
                    'total_communications': len(communications),
                    'agent_statistics': agent_stats,
                    'most_active_agent': max(agent_stats.items(), key=lambda x: x[1]['total_communications'])[0] if agent_stats else None
                }
                
        except Exception as e:
            logging.error(f"Agent logger error: {e}")
            print(f"❌ Erreur résumé activité: {str(e)}")
            return {}

# Instance globale
_logger_instance = None

def get_agent_logger() -> AgentCommunicationLogger:
    """Obtenir l'instance du logger (singleton)"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = AgentCommunicationLogger()
    return _logger_instance

# Fonctions utilitaires pour les agents
def log_agent_communication(source: str, target: str, msg_type: str, content: str, metadata: Dict = None):
    """Fonction utilitaire pour logger une communication"""
    logger = get_agent_logger()
    return logger.log_agent_communication(source, target, msg_type, content, metadata)

def log_glyph_creation(agent_name: str, glyph_data: Dict, context: str = ""):
    """Fonction utilitaire pour logger la création d'un glyph"""
    logger = get_agent_logger()
    return logger.log_glyph_generation(agent_name, glyph_data, context)

def log_agent_activation(agent_name: str, reason: str, result: str = ""):
    """Fonction utilitaire pour logger l'activation d'un agent"""
    logger = get_agent_logger()
    return logger.log_agent_activation(agent_name, reason, result)
