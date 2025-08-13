"""
Agent Aura - Gouvernance des messages inter-agents et provenance.

Aura gère la gouvernance des messages inter-agents avec MSA (Message Service Architecture),
identité, réputation et traçabilité complète de la provenance des données.
"""

import json
import time
import uuid
import hashlib
import hmac
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types de messages dans le système."""
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class TrustLevel(Enum):
    """Niveaux de confiance pour les agents."""
    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ProvenanceType(Enum):
    """Types de provenance des données."""
    ORIGINAL = "original"
    DERIVED = "derived"
    AGGREGATED = "aggregated"
    TRANSFORMED = "transformed"
    VALIDATED = "validated"
    SYNTHESIZED = "synthesized"


@dataclass
class AgentIdentity:
    """Identité d'un agent dans le système."""
    agent_id: str
    agent_type: str
    capabilities: List[str]
    trust_level: TrustLevel
    public_key: str
    created_at: float
    last_seen: float
    reputation_score: float
    metadata: Dict[str, Any]


@dataclass
class MessageEnvelope:
    """Enveloppe de message avec métadonnées de gouvernance."""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    timestamp: float
    ttl: float  # Time to live
    priority: int
    signature: str
    encryption_key: Optional[str]
    routing_path: List[str]
    metadata: Dict[str, Any]


@dataclass
class MessagePayload:
    """Charge utile du message."""
    content: Dict[str, Any]
    content_type: str
    encoding: str
    checksum: str
    provenance: Dict[str, Any]


@dataclass
class ProvenanceRecord:
    """Enregistrement de provenance pour les données."""
    record_id: str
    data_id: str
    provenance_type: ProvenanceType
    source_agent: str
    transformation_applied: Optional[str]
    input_data_ids: List[str]
    timestamp: float
    confidence: float
    validation_status: str
    metadata: Dict[str, Any]


@dataclass
class ReputationMetrics:
    """Métriques de réputation pour un agent."""
    agent_id: str
    message_count: int
    success_rate: float
    response_time_avg: float
    error_rate: float
    trust_violations: int
    peer_ratings: Dict[str, float]
    last_updated: float


class CryptographicManager:
    """Gestionnaire cryptographique pour la sécurité des messages."""
    
    def __init__(self):
        self.key_pairs: Dict[str, Dict[str, str]] = {}
        self.shared_secrets: Dict[str, str] = {}
    
    def generate_key_pair(self, agent_id: str) -> Tuple[str, str]:
        """Génère une paire de clés pour un agent."""
        # Simulation de génération de clés (dans un vrai système, utiliser cryptography)
        private_key = hashlib.sha256(f"{agent_id}_{time.time()}".encode()).hexdigest()
        public_key = hashlib.sha256(f"pub_{private_key}".encode()).hexdigest()
        
        self.key_pairs[agent_id] = {
            "private_key": private_key,
            "public_key": public_key
        }
        
        return public_key, private_key
    
    def sign_message(self, message: str, agent_id: str) -> str:
        """Signe un message avec la clé privée de l'agent."""
        if agent_id not in self.key_pairs:
            raise ValueError(f"Clés non trouvées pour l'agent {agent_id}")
        
        private_key = self.key_pairs[agent_id]["private_key"]
        signature = hmac.new(
            private_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_signature(self, message: str, signature: str, agent_id: str) -> bool:
        """Vérifie la signature d'un message."""
        if agent_id not in self.key_pairs:
            return False
        
        private_key = self.key_pairs[agent_id]["private_key"]
        expected_signature = hmac.new(
            private_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def encrypt_message(self, message: str, receiver_id: str) -> Tuple[str, str]:
        """Chiffre un message pour un destinataire."""
        # Simulation de chiffrement (dans un vrai système, utiliser cryptography)
        encryption_key = hashlib.sha256(f"encrypt_{receiver_id}_{time.time()}".encode()).hexdigest()[:32]
        
        # Chiffrement XOR simple pour la démonstration
        encrypted = ""
        for i, char in enumerate(message):
            key_char = encryption_key[i % len(encryption_key)]
            encrypted += chr(ord(char) ^ ord(key_char))
        
        encrypted_b64 = hashlib.sha256(encrypted.encode()).hexdigest()
        
        return encrypted_b64, encryption_key
    
    def decrypt_message(self, encrypted_message: str, encryption_key: str) -> str:
        """Déchiffre un message."""
        # Simulation de déchiffrement
        # Dans un vrai système, implémenter le déchiffrement correspondant
        return f"decrypted_{encrypted_message[:20]}"


class IdentityManager:
    """Gestionnaire d'identité pour les agents."""
    
    def __init__(self, crypto_manager: CryptographicManager):
        self.crypto_manager = crypto_manager
        self.identities: Dict[str, AgentIdentity] = {}
        self.identity_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def register_agent(self, agent_id: str, agent_type: str, 
                      capabilities: List[str]) -> AgentIdentity:
        """Enregistre un nouvel agent dans le système."""
        # Génération des clés cryptographiques
        public_key, private_key = self.crypto_manager.generate_key_pair(agent_id)
        
        # Création de l'identité
        identity = AgentIdentity(
            agent_id=agent_id,
            agent_type=agent_type,
            capabilities=capabilities,
            trust_level=TrustLevel.LOW,  # Niveau de confiance initial
            public_key=public_key,
            created_at=time.time(),
            last_seen=time.time(),
            reputation_score=0.5,  # Score initial neutre
            metadata={"registration_source": "system"}
        )
        
        self.identities[agent_id] = identity
        self.identity_history[agent_id] = [{
            "action": "registration",
            "timestamp": time.time(),
            "details": {"agent_type": agent_type, "capabilities": capabilities}
        }]
        
        logger.info(f"Agent {agent_id} enregistré avec succès")
        return identity
    
    def authenticate_agent(self, agent_id: str, challenge: str, 
                          response: str) -> bool:
        """Authentifie un agent via un défi cryptographique."""
        if agent_id not in self.identities:
            return False
        
        # Vérification de la signature du défi
        is_valid = self.crypto_manager.verify_signature(challenge, response, agent_id)
        
        if is_valid:
            self.identities[agent_id].last_seen = time.time()
            self._log_identity_event(agent_id, "authentication_success")
        else:
            self._log_identity_event(agent_id, "authentication_failure")
        
        return is_valid
    
    def update_trust_level(self, agent_id: str, new_trust_level: TrustLevel, 
                          reason: str):
        """Met à jour le niveau de confiance d'un agent."""
        if agent_id not in self.identities:
            raise ValueError(f"Agent {agent_id} non trouvé")
        
        old_trust_level = self.identities[agent_id].trust_level
        self.identities[agent_id].trust_level = new_trust_level
        
        self._log_identity_event(agent_id, "trust_level_change", {
            "old_level": old_trust_level.value,
            "new_level": new_trust_level.value,
            "reason": reason
        })
        
        logger.info(f"Niveau de confiance de {agent_id} mis à jour: {old_trust_level} -> {new_trust_level}")
    
    def get_agent_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """Récupère l'identité d'un agent."""
        return self.identities.get(agent_id)
    
    def _log_identity_event(self, agent_id: str, event_type: str, 
                           details: Dict[str, Any] = None):
        """Enregistre un événement d'identité."""
        if agent_id not in self.identity_history:
            self.identity_history[agent_id] = []
        
        event = {
            "event_type": event_type,
            "timestamp": time.time(),
            "details": details or {}
        }
        
        self.identity_history[agent_id].append(event)


class ReputationEngine:
    """Moteur de réputation pour les agents."""
    
    def __init__(self):
        self.reputation_metrics: Dict[str, ReputationMetrics] = {}
        self.reputation_history: Dict[str, List[Dict[str, Any]]] = {}
        self.reputation_rules: List[Callable] = []
        self._setup_reputation_rules()
    
    def _setup_reputation_rules(self):
        """Configure les règles de réputation."""
        self.reputation_rules = [
            self._rule_message_success_rate,
            self._rule_response_time,
            self._rule_error_frequency,
            self._rule_peer_ratings,
            self._rule_trust_violations
        ]
    
    def initialize_agent_reputation(self, agent_id: str):
        """Initialise la réputation d'un agent."""
        metrics = ReputationMetrics(
            agent_id=agent_id,
            message_count=0,
            success_rate=1.0,
            response_time_avg=0.0,
            error_rate=0.0,
            trust_violations=0,
            peer_ratings={},
            last_updated=time.time()
        )
        
        self.reputation_metrics[agent_id] = metrics
        self.reputation_history[agent_id] = []
    
    def update_message_metrics(self, agent_id: str, success: bool, 
                             response_time: float):
        """Met à jour les métriques de message pour un agent."""
        if agent_id not in self.reputation_metrics:
            self.initialize_agent_reputation(agent_id)
        
        metrics = self.reputation_metrics[agent_id]
        
        # Mise à jour du nombre de messages
        metrics.message_count += 1
        
        # Mise à jour du taux de succès
        if metrics.message_count == 1:
            metrics.success_rate = 1.0 if success else 0.0
        else:
            current_successes = metrics.success_rate * (metrics.message_count - 1)
            if success:
                current_successes += 1
            metrics.success_rate = current_successes / metrics.message_count
        
        # Mise à jour du temps de réponse moyen
        if metrics.message_count == 1:
            metrics.response_time_avg = response_time
        else:
            total_time = metrics.response_time_avg * (metrics.message_count - 1)
            metrics.response_time_avg = (total_time + response_time) / metrics.message_count
        
        metrics.last_updated = time.time()
        
        # Recalcul de la réputation
        self._recalculate_reputation(agent_id)
    
    def record_error(self, agent_id: str, error_type: str):
        """Enregistre une erreur pour un agent."""
        if agent_id not in self.reputation_metrics:
            self.initialize_agent_reputation(agent_id)
        
        metrics = self.reputation_metrics[agent_id]
        
        # Mise à jour du taux d'erreur
        total_events = metrics.message_count + 1
        current_errors = metrics.error_rate * metrics.message_count
        metrics.error_rate = (current_errors + 1) / total_events
        
        # Enregistrement dans l'historique
        self.reputation_history[agent_id].append({
            "event_type": "error",
            "error_type": error_type,
            "timestamp": time.time()
        })
        
        self._recalculate_reputation(agent_id)
    
    def add_peer_rating(self, agent_id: str, rater_id: str, rating: float):
        """Ajoute une évaluation par les pairs."""
        if agent_id not in self.reputation_metrics:
            self.initialize_agent_reputation(agent_id)
        
        metrics = self.reputation_metrics[agent_id]
        metrics.peer_ratings[rater_id] = rating
        
        self._recalculate_reputation(agent_id)
    
    def record_trust_violation(self, agent_id: str, violation_type: str):
        """Enregistre une violation de confiance."""
        if agent_id not in self.reputation_metrics:
            self.initialize_agent_reputation(agent_id)
        
        metrics = self.reputation_metrics[agent_id]
        metrics.trust_violations += 1
        
        # Enregistrement dans l'historique
        self.reputation_history[agent_id].append({
            "event_type": "trust_violation",
            "violation_type": violation_type,
            "timestamp": time.time()
        })
        
        self._recalculate_reputation(agent_id)
    
    def _recalculate_reputation(self, agent_id: str):
        """Recalcule la réputation d'un agent."""
        if agent_id not in self.reputation_metrics:
            return
        
        metrics = self.reputation_metrics[agent_id]
        reputation_score = 0.0
        
        # Application des règles de réputation
        for rule in self.reputation_rules:
            score_component = rule(metrics)
            reputation_score += score_component
        
        # Normalisation du score (0.0 à 1.0)
        reputation_score = max(0.0, min(1.0, reputation_score / len(self.reputation_rules)))
        
        # Mise à jour de l'identité si disponible
        # (Ceci nécessiterait une référence à l'IdentityManager)
        
        logger.debug(f"Réputation de {agent_id} recalculée: {reputation_score:.3f}")
    
    def _rule_message_success_rate(self, metrics: ReputationMetrics) -> float:
        """Règle basée sur le taux de succès des messages."""
        return metrics.success_rate
    
    def _rule_response_time(self, metrics: ReputationMetrics) -> float:
        """Règle basée sur le temps de réponse."""
        # Score inversement proportionnel au temps de réponse
        if metrics.response_time_avg == 0:
            return 1.0
        
        # Temps de réponse idéal: 1 seconde
        ideal_time = 1.0
        score = ideal_time / (ideal_time + metrics.response_time_avg)
        return score
    
    def _rule_error_frequency(self, metrics: ReputationMetrics) -> float:
        """Règle basée sur la fréquence d'erreurs."""
        return 1.0 - metrics.error_rate
    
    def _rule_peer_ratings(self, metrics: ReputationMetrics) -> float:
        """Règle basée sur les évaluations par les pairs."""
        if not metrics.peer_ratings:
            return 0.5  # Score neutre si pas d'évaluations
        
        avg_rating = sum(metrics.peer_ratings.values()) / len(metrics.peer_ratings)
        return avg_rating
    
    def _rule_trust_violations(self, metrics: ReputationMetrics) -> float:
        """Règle basée sur les violations de confiance."""
        # Pénalité pour les violations de confiance
        penalty = min(0.5, metrics.trust_violations * 0.1)
        return 1.0 - penalty
    
    def get_reputation_score(self, agent_id: str) -> float:
        """Récupère le score de réputation d'un agent."""
        if agent_id not in self.reputation_metrics:
            return 0.5  # Score neutre par défaut
        
        # Recalcul pour s'assurer que le score est à jour
        self._recalculate_reputation(agent_id)
        
        metrics = self.reputation_metrics[agent_id]
        reputation_score = 0.0
        
        for rule in self.reputation_rules:
            score_component = rule(metrics)
            reputation_score += score_component
        
        return max(0.0, min(1.0, reputation_score / len(self.reputation_rules)))


class ProvenanceTracker:
    """Gestionnaire de provenance des données."""
    
    def __init__(self):
        self.provenance_records: Dict[str, ProvenanceRecord] = {}
        self.data_lineage: Dict[str, List[str]] = {}  # data_id -> list of record_ids
    
    def create_provenance_record(self, data_id: str, provenance_type: ProvenanceType,
                                source_agent: str, input_data_ids: List[str] = None,
                                transformation: str = None) -> str:
        """Crée un enregistrement de provenance."""
        record_id = str(uuid.uuid4())
        
        record = ProvenanceRecord(
            record_id=record_id,
            data_id=data_id,
            provenance_type=provenance_type,
            source_agent=source_agent,
            transformation_applied=transformation,
            input_data_ids=input_data_ids or [],
            timestamp=time.time(),
            confidence=0.9,
            validation_status="pending",
            metadata={}
        )
        
        self.provenance_records[record_id] = record
        
        # Mise à jour de la lignée
        if data_id not in self.data_lineage:
            self.data_lineage[data_id] = []
        self.data_lineage[data_id].append(record_id)
        
        return record_id
    
    def get_data_lineage(self, data_id: str) -> List[ProvenanceRecord]:
        """Récupère la lignée complète d'une donnée."""
        if data_id not in self.data_lineage:
            return []
        
        record_ids = self.data_lineage[data_id]
        return [self.provenance_records[rid] for rid in record_ids if rid in self.provenance_records]
    
    def trace_data_origin(self, data_id: str, max_depth: int = 10) -> Dict[str, Any]:
        """Trace l'origine d'une donnée jusqu'à sa source."""
        visited = set()
        trace_path = []
        
        def _trace_recursive(current_data_id: str, depth: int):
            if depth >= max_depth or current_data_id in visited:
                return
            
            visited.add(current_data_id)
            lineage = self.get_data_lineage(current_data_id)
            
            for record in lineage:
                trace_path.append({
                    "data_id": current_data_id,
                    "record_id": record.record_id,
                    "source_agent": record.source_agent,
                    "provenance_type": record.provenance_type.value,
                    "timestamp": record.timestamp,
                    "depth": depth
                })
                
                # Traçage récursif des données d'entrée
                for input_data_id in record.input_data_ids:
                    _trace_recursive(input_data_id, depth + 1)
        
        _trace_recursive(data_id, 0)
        
        return {
            "data_id": data_id,
            "trace_path": trace_path,
            "total_steps": len(trace_path),
            "max_depth_reached": max(step["depth"] for step in trace_path) if trace_path else 0
        }
    
    def validate_provenance(self, record_id: str, validator_agent: str) -> bool:
        """Valide un enregistrement de provenance."""
        if record_id not in self.provenance_records:
            return False
        
        record = self.provenance_records[record_id]
        
        # Simulation de validation
        # Dans un vrai système, ceci impliquerait des vérifications cryptographiques
        validation_success = True
        
        if validation_success:
            record.validation_status = "validated"
            record.metadata["validated_by"] = validator_agent
            record.metadata["validation_timestamp"] = time.time()
        else:
            record.validation_status = "invalid"
        
        return validation_success


class MessageServiceArchitecture:
    """Architecture de service de messages (MSA)."""
    
    def __init__(self):
        self.crypto_manager = CryptographicManager()
        self.identity_manager = IdentityManager(self.crypto_manager)
        self.reputation_engine = ReputationEngine()
        self.provenance_tracker = ProvenanceTracker()
        
        # Files de messages
        self.message_queues: Dict[str, List[MessageEnvelope]] = {}
        self.message_history: List[Dict[str, Any]] = []
        
        # Politiques de gouvernance
        self.governance_policies: Dict[str, Callable] = {}
        self._setup_governance_policies()
    
    def _setup_governance_policies(self):
        """Configure les politiques de gouvernance."""
        self.governance_policies = {
            "trust_level_check": self._policy_trust_level_check,
            "rate_limiting": self._policy_rate_limiting,
            "message_size_limit": self._policy_message_size_limit,
            "encryption_required": self._policy_encryption_required
        }
    
    def register_agent(self, agent_id: str, agent_type: str, 
                      capabilities: List[str]) -> AgentIdentity:
        """Enregistre un agent dans le MSA."""
        identity = self.identity_manager.register_agent(agent_id, agent_type, capabilities)
        self.reputation_engine.initialize_agent_reputation(agent_id)
        
        # Création de la file de messages
        self.message_queues[agent_id] = []
        
        return identity
    
    def send_message(self, sender_id: str, receiver_id: str, 
                    message_type: MessageType, payload: MessagePayload,
                    priority: int = 5) -> Dict[str, Any]:
        """Envoie un message via le MSA."""
        start_time = time.time()
        
        # Vérification de l'identité de l'expéditeur
        sender_identity = self.identity_manager.get_agent_identity(sender_id)
        if not sender_identity:
            return {"status": "failed", "error": "Expéditeur non authentifié"}
        
        # Vérification de l'existence du destinataire
        receiver_identity = self.identity_manager.get_agent_identity(receiver_id)
        if not receiver_identity:
            return {"status": "failed", "error": "Destinataire non trouvé"}
        
        # Application des politiques de gouvernance
        for policy_name, policy_func in self.governance_policies.items():
            policy_result = policy_func(sender_identity, receiver_identity, payload)
            if not policy_result["allowed"]:
                return {
                    "status": "blocked",
                    "policy": policy_name,
                    "reason": policy_result["reason"]
                }
        
        # Création de l'enveloppe de message
        message_id = str(uuid.uuid4())
        
        # Signature du message
        message_content = json.dumps(asdict(payload), sort_keys=True)
        signature = self.crypto_manager.sign_message(message_content, sender_id)
        
        # Chiffrement si nécessaire
        encryption_key = None
        if receiver_identity.trust_level.value >= TrustLevel.MEDIUM.value:
            encrypted_content, encryption_key = self.crypto_manager.encrypt_message(
                message_content, receiver_id
            )
        
        envelope = MessageEnvelope(
            message_id=message_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            timestamp=time.time(),
            ttl=time.time() + 3600,  # 1 heure de TTL
            priority=priority,
            signature=signature,
            encryption_key=encryption_key,
            routing_path=[sender_id, receiver_id],
            metadata={"governance_validated": True}
        )
        
        # Ajout à la file du destinataire
        if receiver_id not in self.message_queues:
            self.message_queues[receiver_id] = []
        
        self.message_queues[receiver_id].append(envelope)
        
        # Enregistrement dans l'historique
        self.message_history.append({
            "message_id": message_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "timestamp": envelope.timestamp,
            "message_type": message_type.value,
            "status": "delivered"
        })
        
        # Mise à jour des métriques de réputation
        response_time = time.time() - start_time
        self.reputation_engine.update_message_metrics(sender_id, True, response_time)
        
        # Création de l'enregistrement de provenance
        self.provenance_tracker.create_provenance_record(
            data_id=message_id,
            provenance_type=ProvenanceType.ORIGINAL,
            source_agent=sender_id
        )
        
        return {
            "status": "delivered",
            "message_id": message_id,
            "delivery_time": response_time
        }
    
    def receive_messages(self, agent_id: str, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Récupère les messages pour un agent."""
        if agent_id not in self.message_queues:
            return []
        
        messages = []
        queue = self.message_queues[agent_id]
        
        # Tri par priorité et timestamp
        queue.sort(key=lambda msg: (-msg.priority, msg.timestamp))
        
        # Récupération des messages (jusqu'à max_messages)
        for _ in range(min(max_messages, len(queue))):
            if queue:
                envelope = queue.pop(0)
                
                # Vérification du TTL
                if envelope.ttl < time.time():
                    continue  # Message expiré
                
                # Déchiffrement si nécessaire
                # (Simulation - dans un vrai système, implémenter le déchiffrement)
                
                messages.append({
                    "message_id": envelope.message_id,
                    "sender_id": envelope.sender_id,
                    "message_type": envelope.message_type.value,
                    "timestamp": envelope.timestamp,
                    "priority": envelope.priority,
                    "routing_path": envelope.routing_path
                })
        
        return messages
    
    def _policy_trust_level_check(self, sender: AgentIdentity, receiver: AgentIdentity,
                                 payload: MessagePayload) -> Dict[str, Any]:
        """Politique de vérification du niveau de confiance."""
        if sender.trust_level.value < TrustLevel.LOW.value:
            return {
                "allowed": False,
                "reason": "Niveau de confiance de l'expéditeur insuffisant"
            }
        
        return {"allowed": True}
    
    def _policy_rate_limiting(self, sender: AgentIdentity, receiver: AgentIdentity,
                            payload: MessagePayload) -> Dict[str, Any]:
        """Politique de limitation du taux de messages."""
        # Simulation de limitation de taux
        recent_messages = [
            msg for msg in self.message_history
            if msg["sender_id"] == sender.agent_id and 
               time.time() - msg["timestamp"] < 60  # Dernière minute
        ]
        
        if len(recent_messages) > 100:  # Limite de 100 messages par minute
            return {
                "allowed": False,
                "reason": "Limite de taux de messages dépassée"
            }
        
        return {"allowed": True}
    
    def _policy_message_size_limit(self, sender: AgentIdentity, receiver: AgentIdentity,
                                  payload: MessagePayload) -> Dict[str, Any]:
        """Politique de limitation de la taille des messages."""
        message_size = len(json.dumps(asdict(payload)))
        
        if message_size > 1024 * 1024:  # Limite de 1MB
            return {
                "allowed": False,
                "reason": "Taille du message trop importante"
            }
        
        return {"allowed": True}
    
    def _policy_encryption_required(self, sender: AgentIdentity, receiver: AgentIdentity,
                                   payload: MessagePayload) -> Dict[str, Any]:
        """Politique de chiffrement requis."""
        if (sender.trust_level.value >= TrustLevel.HIGH.value or 
            receiver.trust_level.value >= TrustLevel.HIGH.value):
            # Le chiffrement sera appliqué automatiquement
            pass
        
        return {"allowed": True}


class Aura:
    """Agent principal de gouvernance des messages inter-agents et de provenance."""
    
    def __init__(self):
        self.msa = MessageServiceArchitecture()
        self.governance_metrics: Dict[str, Any] = {
            "total_messages_processed": 0,
            "blocked_messages": 0,
            "trust_violations": 0,
            "average_reputation_score": 0.0
        }
        
        logger.info("Agent Aura initialisé avec gouvernance complète")
    
    def register_agent(self, agent_id: str, agent_type: str, 
                      capabilities: List[str]) -> Dict[str, Any]:
        """Enregistre un agent dans le système de gouvernance."""
        try:
            identity = self.msa.register_agent(agent_id, agent_type, capabilities)
            
            return {
                "status": "registered",
                "agent_id": agent_id,
                "trust_level": identity.trust_level.value,
                "public_key": identity.public_key
            }
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de {agent_id}: {e}")
            return {"status": "failed", "error": str(e)}
    
    def route_message(self, sender_id: str, receiver_id: str, 
                     message_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """Route un message avec gouvernance complète."""
        # Création du payload
        payload = MessagePayload(
            content=content,
            content_type="application/json",
            encoding="utf-8",
            checksum=hashlib.sha256(json.dumps(content).encode()).hexdigest(),
            provenance={"created_by": sender_id, "timestamp": time.time()}
        )
        
        # Envoi via MSA
        result = self.msa.send_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=MessageType(message_type),
            payload=payload
        )
        
        # Mise à jour des métriques
        self.governance_metrics["total_messages_processed"] += 1
        
        if result["status"] == "blocked":
            self.governance_metrics["blocked_messages"] += 1
        
        return result
    
    def get_agent_reputation(self, agent_id: str) -> Dict[str, Any]:
        """Récupère la réputation d'un agent."""
        reputation_score = self.msa.reputation_engine.get_reputation_score(agent_id)
        identity = self.msa.identity_manager.get_agent_identity(agent_id)
        
        if not identity:
            return {"error": "Agent non trouvé"}
        
        return {
            "agent_id": agent_id,
            "reputation_score": reputation_score,
            "trust_level": identity.trust_level.value,
            "last_seen": identity.last_seen,
            "registration_date": identity.created_at
        }
    
    def trace_data_provenance(self, data_id: str) -> Dict[str, Any]:
        """Trace la provenance complète d'une donnée."""
        return self.msa.provenance_tracker.trace_data_origin(data_id)
    
    def audit_agent_activity(self, agent_id: str, 
                           time_range: Tuple[float, float]) -> Dict[str, Any]:
        """Effectue un audit de l'activité d'un agent."""
        start_time, end_time = time_range
        
        # Filtrage des messages dans la plage temporelle
        agent_messages = [
            msg for msg in self.msa.message_history
            if (msg["sender_id"] == agent_id or msg["receiver_id"] == agent_id) and
               start_time <= msg["timestamp"] <= end_time
        ]
        
        # Analyse de l'activité
        sent_messages = [msg for msg in agent_messages if msg["sender_id"] == agent_id]
        received_messages = [msg for msg in agent_messages if msg["receiver_id"] == agent_id]
        
        # Calcul des métriques
        message_types = {}
        for msg in sent_messages:
            msg_type = msg["message_type"]
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
        
        return {
            "agent_id": agent_id,
            "audit_period": {"start": start_time, "end": end_time},
            "total_activity": len(agent_messages),
            "messages_sent": len(sent_messages),
            "messages_received": len(received_messages),
            "message_types_sent": message_types,
            "reputation_score": self.msa.reputation_engine.get_reputation_score(agent_id),
            "trust_level": self.msa.identity_manager.get_agent_identity(agent_id).trust_level.value if self.msa.identity_manager.get_agent_identity(agent_id) else None
        }
    
    def get_governance_status(self) -> Dict[str, Any]:
        """Retourne le statut de la gouvernance."""
        # Calcul de la réputation moyenne
        all_agents = list(self.msa.identity_manager.identities.keys())
        if all_agents:
            total_reputation = sum(
                self.msa.reputation_engine.get_reputation_score(agent_id)
                for agent_id in all_agents
            )
            avg_reputation = total_reputation / len(all_agents)
        else:
            avg_reputation = 0.0
        
        self.governance_metrics["average_reputation_score"] = avg_reputation
        
        return {
            "registered_agents": len(self.msa.identity_manager.identities),
            "active_message_queues": len(self.msa.message_queues),
            "governance_metrics": self.governance_metrics,
            "provenance_records": len(self.msa.provenance_tracker.provenance_records),
            "policy_violations": self.governance_metrics["blocked_messages"],
            "system_health": "healthy" if avg_reputation > 0.7 else "degraded"
        }

