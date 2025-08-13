"""
Agent Symphony - Orchestration modulaire et hiérarchique des workflows d'agents.

Symphony gère l'orchestration des workflows d'agents selon les paradigmes
AgentMesh et AgentOrchestra, avec dispatch neuronal et gouvernance des protocoles.
"""

import json
import time
import uuid
import asyncio
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Rôles des agents dans l'orchestration."""
    COORDINATOR = "coordinator"
    PLANNER = "planner"
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"
    CODER = "coder"


class TaskStatus(Enum):
    """Statuts des tâches dans le workflow."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowTask:
    """Représente une tâche dans un workflow."""
    task_id: str
    task_type: str
    description: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    status: TaskStatus
    assigned_agent: Optional[str]
    dependencies: List[str]
    priority: float
    created_at: float
    started_at: Optional[float]
    completed_at: Optional[float]
    metadata: Dict[str, Any]


@dataclass
class AgentCapability:
    """Représente une capacité d'agent."""
    capability_id: str
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    performance_metrics: Dict[str, float]
    resource_requirements: Dict[str, Any]


@dataclass
class WorkflowDefinition:
    """Définition d'un workflow d'agents."""
    workflow_id: str
    name: str
    description: str
    stages: List[Dict[str, Any]]
    dependencies: Dict[str, List[str]]
    success_criteria: Dict[str, Any]
    timeout_seconds: int


class AgentInterface(ABC):
    """Interface abstraite pour les agents orchestrés."""
    
    @abstractmethod
    async def execute_task(self, task: WorkflowTask) -> Dict[str, Any]:
        """Exécute une tâche assignée."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[AgentCapability]:
        """Retourne les capacités de l'agent."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut actuel de l'agent."""
        pass


class NeuralDispatcher:
    """Dispatcher neuronal pour la sélection dynamique d'agents."""
    
    def __init__(self):
        self.agent_registry: Dict[str, AgentInterface] = {}
        self.routing_history: List[Dict[str, Any]] = []
        self.performance_cache: Dict[str, Dict[str, float]] = {}
        self.loop_detection: Dict[str, int] = {}
    
    def register_agent(self, agent_id: str, agent: AgentInterface):
        """Enregistre un agent dans le dispatcher."""
        self.agent_registry[agent_id] = agent
        self.performance_cache[agent_id] = {}
        
        logger.info(f"Agent {agent_id} enregistré dans le dispatcher")
    
    def select_agent(self, task: WorkflowTask, 
                    available_agents: List[str]) -> Optional[str]:
        """Sélectionne l'agent optimal pour une tâche via dispatch neuronal."""
        if not available_agents:
            return None
        
        # Vérification de la détection de boucles
        task_signature = f"{task.task_type}_{task.description[:50]}"
        if task_signature in self.loop_detection:
            self.loop_detection[task_signature] += 1
            if self.loop_detection[task_signature] > 3:
                logger.warning(f"Boucle détectée pour la tâche {task_signature}")
                return None
        else:
            self.loop_detection[task_signature] = 1
        
        # Calcul des scores pour chaque agent disponible
        agent_scores = {}
        
        for agent_id in available_agents:
            if agent_id not in self.agent_registry:
                continue
            
            agent = self.agent_registry[agent_id]
            score = self._calculate_agent_score(agent, task)
            agent_scores[agent_id] = score
        
        # Sélection de l'agent avec le meilleur score
        if agent_scores:
            best_agent = max(agent_scores.items(), key=lambda x: x[1])
            selected_agent_id = best_agent[0]
            
            # Enregistrement de la décision de routage
            routing_decision = {
                "task_id": task.task_id,
                "selected_agent": selected_agent_id,
                "score": best_agent[1],
                "all_scores": agent_scores,
                "timestamp": time.time()
            }
            self.routing_history.append(routing_decision)
            
            logger.info(f"Agent {selected_agent_id} sélectionné pour la tâche {task.task_id} (score: {best_agent[1]:.3f})")
            return selected_agent_id
        
        return None
    
    def _calculate_agent_score(self, agent: AgentInterface, task: WorkflowTask) -> float:
        """Calcule le score d'un agent pour une tâche donnée."""
        score = 0.0
        
        # Score basé sur les capacités
        capabilities = agent.get_capabilities()
        capability_match = 0.0
        
        for capability in capabilities:
            if task.task_type in capability.input_types:
                capability_match += 1.0
            
            # Bonus pour les performances passées
            if capability.capability_id in self.performance_cache.get(agent.__class__.__name__, {}):
                performance = self.performance_cache[agent.__class__.__name__][capability.capability_id]
                capability_match += performance * 0.5
        
        score += capability_match
        
        # Score basé sur la charge actuelle de l'agent
        agent_status = agent.get_status()
        current_load = agent_status.get("current_load", 0.0)
        score += (1.0 - current_load) * 0.3  # Préférence pour les agents moins chargés
        
        # Score basé sur la priorité de la tâche
        score += task.priority * 0.2
        
        return score
    
    def update_agent_performance(self, agent_id: str, task_type: str, 
                               performance_score: float):
        """Met à jour les métriques de performance d'un agent."""
        if agent_id not in self.performance_cache:
            self.performance_cache[agent_id] = {}
        
        self.performance_cache[agent_id][task_type] = performance_score
        
        # Nettoyage de l'historique de détection de boucles
        if performance_score > 0.8:  # Bonne performance
            keys_to_clean = [k for k in self.loop_detection.keys() if task_type in k]
            for key in keys_to_clean:
                if self.loop_detection[key] > 0:
                    self.loop_detection[key] -= 1


class WorkflowEngine:
    """Moteur d'exécution des workflows d'agents."""
    
    def __init__(self, dispatcher: NeuralDispatcher):
        self.dispatcher = dispatcher
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.workflow_definitions: Dict[str, WorkflowDefinition] = {}
        self.task_queue: List[WorkflowTask] = []
        self._setup_default_workflows()
    
    def _setup_default_workflows(self):
        """Configure les workflows par défaut."""
        # Workflow AgentMesh: Planner -> Coder -> Debugger -> Reviewer
        agent_mesh_workflow = WorkflowDefinition(
            workflow_id="agent_mesh",
            name="Agent Mesh Pipeline",
            description="Pipeline structuré Planificateur -> Codeur -> Débogueur -> Réviseur",
            stages=[
                {"stage": "planning", "role": AgentRole.PLANNER, "timeout": 300},
                {"stage": "coding", "role": AgentRole.CODER, "timeout": 600},
                {"stage": "debugging", "role": AgentRole.DEBUGGER, "timeout": 300},
                {"stage": "reviewing", "role": AgentRole.REVIEWER, "timeout": 300}
            ],
            dependencies={
                "coding": ["planning"],
                "debugging": ["coding"],
                "reviewing": ["debugging"]
            },
            success_criteria={"all_stages_completed": True, "no_critical_errors": True},
            timeout_seconds=1800
        )
        
        # Workflow AgentOrchestra: Coordinator -> Planner -> Specialist
        agent_orchestra_workflow = WorkflowDefinition(
            workflow_id="agent_orchestra",
            name="Agent Orchestra Hierarchy",
            description="Coordination hiérarchique Coordinateur -> Planificateur -> Spécialiste",
            stages=[
                {"stage": "coordination", "role": AgentRole.COORDINATOR, "timeout": 180},
                {"stage": "planning", "role": AgentRole.PLANNER, "timeout": 300},
                {"stage": "specialization", "role": AgentRole.SPECIALIST, "timeout": 600}
            ],
            dependencies={
                "planning": ["coordination"],
                "specialization": ["planning"]
            },
            success_criteria={"coordination_success": True, "specialization_quality": 0.8},
            timeout_seconds=1200
        )
        
        self.workflow_definitions["agent_mesh"] = agent_mesh_workflow
        self.workflow_definitions["agent_orchestra"] = agent_orchestra_workflow
    
    async def execute_workflow(self, workflow_id: str, 
                             input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute un workflow complet."""
        if workflow_id not in self.workflow_definitions:
            raise ValueError(f"Workflow {workflow_id} non trouvé")
        
        workflow_def = self.workflow_definitions[workflow_id]
        execution_id = str(uuid.uuid4())
        
        # Initialisation de l'exécution
        workflow_execution = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "status": "running",
            "start_time": time.time(),
            "stages_completed": [],
            "current_stage": None,
            "results": {},
            "errors": []
        }
        
        self.active_workflows[execution_id] = workflow_execution
        
        try:
            # Exécution séquentielle des stages
            current_data = input_data.copy()
            
            for stage_def in workflow_def.stages:
                stage_name = stage_def["stage"]
                stage_role = stage_def["role"]
                stage_timeout = stage_def["timeout"]
                
                # Vérification des dépendances
                dependencies = workflow_def.dependencies.get(stage_name, [])
                if not all(dep in workflow_execution["stages_completed"] for dep in dependencies):
                    raise Exception(f"Dépendances non satisfaites pour le stage {stage_name}")
                
                workflow_execution["current_stage"] = stage_name
                
                # Création de la tâche pour ce stage
                task = WorkflowTask(
                    task_id=f"{execution_id}_{stage_name}",
                    task_type=stage_name,
                    description=f"Exécution du stage {stage_name} dans le workflow {workflow_id}",
                    input_data=current_data,
                    output_data={},
                    status=TaskStatus.PENDING,
                    assigned_agent=None,
                    dependencies=dependencies,
                    priority=0.8,
                    created_at=time.time(),
                    started_at=None,
                    completed_at=None,
                    metadata={"workflow_execution_id": execution_id, "stage_role": stage_role.value}
                )
                
                # Exécution du stage
                stage_result = await self._execute_stage(task, stage_role, stage_timeout)
                
                if stage_result["status"] == "success":
                    workflow_execution["stages_completed"].append(stage_name)
                    workflow_execution["results"][stage_name] = stage_result["output"]
                    current_data.update(stage_result["output"])
                else:
                    workflow_execution["errors"].append(stage_result["error"])
                    workflow_execution["status"] = "failed"
                    break
            
            # Vérification des critères de succès
            if workflow_execution["status"] != "failed":
                success = self._check_success_criteria(workflow_def, workflow_execution)
                workflow_execution["status"] = "completed" if success else "failed"
            
        except Exception as e:
            workflow_execution["status"] = "failed"
            workflow_execution["errors"].append(str(e))
            logger.error(f"Erreur dans l'exécution du workflow {workflow_id}: {e}")
        
        finally:
            workflow_execution["end_time"] = time.time()
            workflow_execution["duration"] = workflow_execution["end_time"] - workflow_execution["start_time"]
            workflow_execution["current_stage"] = None
        
        return workflow_execution
    
    async def _execute_stage(self, task: WorkflowTask, role: AgentRole, 
                           timeout: int) -> Dict[str, Any]:
        """Exécute un stage spécifique du workflow."""
        # Sélection des agents disponibles pour ce rôle
        available_agents = self._get_agents_by_role(role)
        
        if not available_agents:
            return {
                "status": "failed",
                "error": f"Aucun agent disponible pour le rôle {role.value}",
                "output": {}
            }
        
        # Sélection de l'agent optimal
        selected_agent_id = self.dispatcher.select_agent(task, available_agents)
        
        if not selected_agent_id:
            return {
                "status": "failed",
                "error": f"Impossible de sélectionner un agent pour le rôle {role.value}",
                "output": {}
            }
        
        # Exécution de la tâche
        task.assigned_agent = selected_agent_id
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = time.time()
        
        try:
            agent = self.dispatcher.agent_registry[selected_agent_id]
            
            # Exécution avec timeout
            result = await asyncio.wait_for(
                agent.execute_task(task),
                timeout=timeout
            )
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.output_data = result
            
            # Mise à jour des performances
            execution_time = task.completed_at - task.started_at
            performance_score = min(1.0, max(0.0, 1.0 - (execution_time / timeout)))
            self.dispatcher.update_agent_performance(
                selected_agent_id, task.task_type, performance_score
            )
            
            return {
                "status": "success",
                "output": result,
                "execution_time": execution_time,
                "agent_id": selected_agent_id
            }
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            error_msg = f"Timeout lors de l'exécution de la tâche {task.task_id}"
            logger.error(error_msg)
            return {"status": "failed", "error": error_msg, "output": {}}
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            error_msg = f"Erreur lors de l'exécution de la tâche {task.task_id}: {str(e)}"
            logger.error(error_msg)
            return {"status": "failed", "error": error_msg, "output": {}}
    
    def _get_agents_by_role(self, role: AgentRole) -> List[str]:
        """Récupère les agents disponibles pour un rôle donné."""
        available_agents = []
        
        for agent_id, agent in self.dispatcher.agent_registry.items():
            capabilities = agent.get_capabilities()
            
            # Vérification si l'agent peut remplir ce rôle
            for capability in capabilities:
                if self._capability_matches_role(capability, role):
                    available_agents.append(agent_id)
                    break
        
        return available_agents
    
    def _capability_matches_role(self, capability: AgentCapability, role: AgentRole) -> bool:
        """Vérifie si une capacité correspond à un rôle."""
        role_mappings = {
            AgentRole.COORDINATOR: ["coordination", "orchestration", "management"],
            AgentRole.PLANNER: ["planning", "strategy", "analysis"],
            AgentRole.SPECIALIST: ["execution", "processing", "generation"],
            AgentRole.REVIEWER: ["review", "validation", "quality_check"],
            AgentRole.DEBUGGER: ["debugging", "error_detection", "troubleshooting"],
            AgentRole.CODER: ["coding", "implementation", "development"]
        }
        
        role_keywords = role_mappings.get(role, [])
        capability_name_lower = capability.name.lower()
        
        return any(keyword in capability_name_lower for keyword in role_keywords)
    
    def _check_success_criteria(self, workflow_def: WorkflowDefinition, 
                              execution: Dict[str, Any]) -> bool:
        """Vérifie les critères de succès du workflow."""
        criteria = workflow_def.success_criteria
        
        # Vérification de la complétion de tous les stages
        if criteria.get("all_stages_completed", False):
            expected_stages = [stage["stage"] for stage in workflow_def.stages]
            if not all(stage in execution["stages_completed"] for stage in expected_stages):
                return False
        
        # Vérification de l'absence d'erreurs critiques
        if criteria.get("no_critical_errors", False):
            if execution["errors"]:
                return False
        
        # Vérification de la qualité de spécialisation (pour AgentOrchestra)
        if "specialization_quality" in criteria:
            required_quality = criteria["specialization_quality"]
            actual_quality = execution["results"].get("specialization", {}).get("quality_score", 0.0)
            if actual_quality < required_quality:
                return False
        
        return True


class ProtocolGovernance:
    """Système de gouvernance des protocoles MCP/A2A."""
    
    def __init__(self):
        self.protocol_rules: Dict[str, Callable] = {}
        self.message_history: List[Dict[str, Any]] = []
        self.identity_registry: Dict[str, Dict[str, Any]] = {}
        self._setup_default_protocols()
    
    def _setup_default_protocols(self):
        """Configure les protocoles par défaut."""
        self.protocol_rules = {
            "MCP": self._validate_mcp_message,
            "A2A": self._validate_a2a_message,
            "identity": self._validate_identity,
            "authorization": self._validate_authorization
        }
    
    def validate_message(self, message: Dict[str, Any], 
                        protocol: str) -> Dict[str, Any]:
        """Valide un message selon un protocole donné."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "timestamp": time.time()
        }
        
        if protocol in self.protocol_rules:
            try:
                result = self.protocol_rules[protocol](message)
                validation_result.update(result)
            except Exception as e:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Erreur de validation {protocol}: {str(e)}")
        else:
            validation_result["warnings"].append(f"Protocole {protocol} non reconnu")
        
        # Enregistrement du message
        self.message_history.append({
            "message": message,
            "protocol": protocol,
            "validation": validation_result
        })
        
        return validation_result
    
    def _validate_mcp_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Valide un message selon le protocole MCP."""
        result = {"valid": True, "errors": [], "warnings": []}
        
        # Vérifications MCP basiques
        required_fields = ["id", "method", "params"]
        for field in required_fields:
            if field not in message:
                result["valid"] = False
                result["errors"].append(f"Champ MCP requis manquant: {field}")
        
        # Validation de l'ID
        if "id" in message and not isinstance(message["id"], (str, int)):
            result["valid"] = False
            result["errors"].append("L'ID MCP doit être une chaîne ou un entier")
        
        return result
    
    def _validate_a2a_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Valide un message selon le protocole A2A."""
        result = {"valid": True, "errors": [], "warnings": []}
        
        # Vérifications A2A basiques
        required_fields = ["sender", "receiver", "message_type", "payload"]
        for field in required_fields:
            if field not in message:
                result["valid"] = False
                result["errors"].append(f"Champ A2A requis manquant: {field}")
        
        # Validation de l'identité du sender
        if "sender" in message:
            sender_id = message["sender"]
            if sender_id not in self.identity_registry:
                result["warnings"].append(f"Sender {sender_id} non enregistré")
        
        return result
    
    def _validate_identity(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Valide l'identité dans un message."""
        result = {"valid": True, "errors": [], "warnings": []}
        
        if "sender" in message:
            sender_id = message["sender"]
            if sender_id in self.identity_registry:
                # Vérification de la cohérence de l'identité
                registered_info = self.identity_registry[sender_id]
                message_info = message.get("sender_info", {})
                
                if registered_info.get("agent_type") != message_info.get("agent_type"):
                    result["warnings"].append("Incohérence dans le type d'agent")
            else:
                result["warnings"].append(f"Agent {sender_id} non enregistré")
        
        return result
    
    def _validate_authorization(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Valide l'autorisation dans un message."""
        result = {"valid": True, "errors": [], "warnings": []}
        
        # Vérifications d'autorisation basiques
        if "authorization" in message:
            auth_info = message["authorization"]
            if not isinstance(auth_info, dict):
                result["valid"] = False
                result["errors"].append("Les informations d'autorisation doivent être un dictionnaire")
            elif "token" not in auth_info:
                result["warnings"].append("Token d'autorisation manquant")
        
        return result
    
    def register_agent_identity(self, agent_id: str, identity_info: Dict[str, Any]):
        """Enregistre l'identité d'un agent."""
        self.identity_registry[agent_id] = {
            "agent_id": agent_id,
            "registered_at": time.time(),
            **identity_info
        }
        
        logger.info(f"Identité enregistrée pour l'agent {agent_id}")


class Symphony:
    """Agent principal d'orchestration modulaire et hiérarchique."""
    
    def __init__(self):
        self.dispatcher = NeuralDispatcher()
        self.workflow_engine = WorkflowEngine(self.dispatcher)
        self.protocol_governance = ProtocolGovernance()
        
        # Métriques et monitoring
        self.execution_metrics: Dict[str, Any] = {
            "total_workflows_executed": 0,
            "successful_workflows": 0,
            "failed_workflows": 0,
            "avg_execution_time": 0.0,
            "agent_utilization": {}
        }
        
        logger.info("Agent Symphony initialisé")
    
    def register_agent(self, agent_id: str, agent: AgentInterface, 
                      identity_info: Dict[str, Any]):
        """Enregistre un agent dans l'orchestrateur."""
        self.dispatcher.register_agent(agent_id, agent)
        self.protocol_governance.register_agent_identity(agent_id, identity_info)
        
        # Initialisation des métriques d'utilisation
        self.execution_metrics["agent_utilization"][agent_id] = {
            "tasks_executed": 0,
            "success_rate": 0.0,
            "avg_execution_time": 0.0
        }
    
    async def orchestrate_workflow(self, workflow_type: str, 
                                 input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestre l'exécution d'un workflow complet."""
        start_time = time.time()
        
        try:
            # Validation du message d'entrée
            message_validation = self.protocol_governance.validate_message(
                {"workflow_type": workflow_type, "input_data": input_data},
                "MCP"
            )
            
            if not message_validation["valid"]:
                return {
                    "status": "failed",
                    "error": "Validation du message d'entrée échouée",
                    "validation_errors": message_validation["errors"]
                }
            
            # Exécution du workflow
            result = await self.workflow_engine.execute_workflow(workflow_type, input_data)
            
            # Mise à jour des métriques
            self.execution_metrics["total_workflows_executed"] += 1
            
            if result["status"] == "completed":
                self.execution_metrics["successful_workflows"] += 1
            else:
                self.execution_metrics["failed_workflows"] += 1
            
            # Calcul de la moyenne du temps d'exécution
            execution_time = time.time() - start_time
            total_executions = self.execution_metrics["total_workflows_executed"]
            current_avg = self.execution_metrics["avg_execution_time"]
            self.execution_metrics["avg_execution_time"] = (
                (current_avg * (total_executions - 1) + execution_time) / total_executions
            )
            
            return result
            
        except Exception as e:
            self.execution_metrics["failed_workflows"] += 1
            logger.error(f"Erreur dans l'orchestration du workflow {workflow_type}: {e}")
            
            return {
                "status": "failed",
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    def create_custom_workflow(self, workflow_def: WorkflowDefinition):
        """Crée un workflow personnalisé."""
        self.workflow_engine.workflow_definitions[workflow_def.workflow_id] = workflow_def
        logger.info(f"Workflow personnalisé {workflow_def.workflow_id} créé")
    
    def get_orchestration_status(self) -> Dict[str, Any]:
        """Retourne le statut de l'orchestration."""
        return {
            "registered_agents": len(self.dispatcher.agent_registry),
            "active_workflows": len(self.workflow_engine.active_workflows),
            "available_workflows": list(self.workflow_engine.workflow_definitions.keys()),
            "execution_metrics": self.execution_metrics,
            "routing_accuracy": self._calculate_routing_accuracy(),
            "protocol_compliance": self._calculate_protocol_compliance()
        }
    
    def _calculate_routing_accuracy(self) -> float:
        """Calcule la précision du routage neuronal."""
        if not self.dispatcher.routing_history:
            return 0.0
        
        # Simulation de calcul de précision basée sur les scores
        recent_decisions = self.dispatcher.routing_history[-100:]  # 100 dernières décisions
        avg_score = sum(decision["score"] for decision in recent_decisions) / len(recent_decisions)
        
        return min(1.0, avg_score)
    
    def _calculate_protocol_compliance(self) -> float:
        """Calcule le taux de conformité aux protocoles."""
        if not self.protocol_governance.message_history:
            return 1.0
        
        recent_messages = self.protocol_governance.message_history[-100:]  # 100 derniers messages
        valid_messages = sum(1 for msg in recent_messages if msg["validation"]["valid"])
        
        return valid_messages / len(recent_messages) if recent_messages else 1.0


# Agents de démonstration pour tester Symphony

class PlannerAgent(AgentInterface):
    """Agent planificateur de démonstration."""
    
    async def execute_task(self, task: WorkflowTask) -> Dict[str, Any]:
        """Exécute une tâche de planification."""
        await asyncio.sleep(0.5)  # Simulation du temps de traitement
        
        return {
            "plan": f"Plan généré pour {task.description}",
            "steps": ["Étape 1", "Étape 2", "Étape 3"],
            "estimated_duration": 300,
            "resources_needed": ["agent_specialist", "data_access"]
        }
    
    def get_capabilities(self) -> List[AgentCapability]:
        """Retourne les capacités du planificateur."""
        return [
            AgentCapability(
                capability_id="planning_001",
                name="Strategic Planning",
                description="Planification stratégique de tâches complexes",
                input_types=["planning", "strategy"],
                output_types=["plan", "strategy"],
                performance_metrics={"accuracy": 0.85, "speed": 0.9},
                resource_requirements={"cpu": "low", "memory": "medium"}
            )
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut du planificateur."""
        return {
            "status": "active",
            "current_load": 0.3,
            "last_activity": time.time()
        }


class SpecialistAgent(AgentInterface):
    """Agent spécialiste de démonstration."""
    
    async def execute_task(self, task: WorkflowTask) -> Dict[str, Any]:
        """Exécute une tâche spécialisée."""
        await asyncio.sleep(1.0)  # Simulation du temps de traitement
        
        return {
            "result": f"Résultat spécialisé pour {task.description}",
            "quality_score": 0.9,
            "processing_time": 1.0,
            "artifacts": ["output_file.json", "analysis_report.md"]
        }
    
    def get_capabilities(self) -> List[AgentCapability]:
        """Retourne les capacités du spécialiste."""
        return [
            AgentCapability(
                capability_id="specialist_001",
                name="Specialized Processing",
                description="Traitement spécialisé de données complexes",
                input_types=["specialization", "processing"],
                output_types=["result", "analysis"],
                performance_metrics={"accuracy": 0.92, "speed": 0.8},
                resource_requirements={"cpu": "high", "memory": "high"}
            )
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut du spécialiste."""
        return {
            "status": "active",
            "current_load": 0.6,
            "last_activity": time.time()
        }




class MetaOrchestrator:
    """Orchestrateur méta avec dispatch neuronal avancé et suppression de boucles."""
    
    def __init__(self):
        self.neural_router = NeuralRouter()
        self.loop_suppressor = LoopSuppressor()
        self.context_analyzer = ContextAnalyzer()
        self.decision_history: List[Dict[str, Any]] = []
    
    async def route_task(self, task: WorkflowTask, 
                        context: Dict[str, Any]) -> Dict[str, Any]:
        """Route une tâche via dispatch neuronal avec analyse contextuelle."""
        # Analyse du contexte
        context_analysis = self.context_analyzer.analyze_context(task, context)
        
        # Vérification des boucles
        loop_check = self.loop_suppressor.check_for_loops(task, context_analysis)
        if loop_check["loop_detected"]:
            return {
                "status": "suppressed",
                "reason": "Boucle récursive détectée",
                "loop_info": loop_check
            }
        
        # Routage neuronal
        routing_decision = await self.neural_router.route(task, context_analysis)
        
        # Enregistrement de la décision
        decision_record = {
            "task_id": task.task_id,
            "context_analysis": context_analysis,
            "routing_decision": routing_decision,
            "timestamp": time.time()
        }
        self.decision_history.append(decision_record)
        
        return routing_decision


class NeuralRouter:
    """Routeur neuronal pour la sélection dynamique d'agents."""
    
    def __init__(self):
        self.routing_weights: Dict[str, Dict[str, float]] = {}
        self.performance_history: Dict[str, List[float]] = {}
        self.learning_rate = 0.1
    
    async def route(self, task: WorkflowTask, 
                   context_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Effectue le routage neuronal d'une tâche."""
        # Extraction des features du contexte
        features = self._extract_features(task, context_analysis)
        
        # Calcul des scores pour chaque agent disponible
        available_agents = context_analysis.get("available_agents", [])
        agent_scores = {}
        
        for agent_id in available_agents:
            score = self._calculate_neural_score(agent_id, features)
            agent_scores[agent_id] = score
        
        # Sélection de l'agent optimal
        if agent_scores:
            best_agent = max(agent_scores.items(), key=lambda x: x[1])
            selected_agent_id = best_agent[0]
            confidence = best_agent[1]
            
            return {
                "status": "routed",
                "selected_agent": selected_agent_id,
                "confidence": confidence,
                "all_scores": agent_scores,
                "features_used": features
            }
        
        return {
            "status": "failed",
            "reason": "Aucun agent disponible",
            "features_used": features
        }
    
    def _extract_features(self, task: WorkflowTask, 
                         context_analysis: Dict[str, Any]) -> Dict[str, float]:
        """Extrait les features pour le routage neuronal."""
        features = {}
        
        # Features basées sur la tâche
        features["task_priority"] = task.priority
        features["task_complexity"] = len(task.description) / 100.0  # Normalisation
        features["dependency_count"] = len(task.dependencies)
        
        # Features basées sur le contexte
        features["context_urgency"] = context_analysis.get("urgency_score", 0.5)
        features["resource_availability"] = context_analysis.get("resource_score", 0.8)
        features["historical_success"] = context_analysis.get("success_rate", 0.7)
        
        # Features temporelles
        current_hour = time.localtime().tm_hour
        features["time_of_day"] = current_hour / 24.0
        features["workload_factor"] = context_analysis.get("current_workload", 0.5)
        
        return features
    
    def _calculate_neural_score(self, agent_id: str, features: Dict[str, float]) -> float:
        """Calcule le score neuronal pour un agent donné."""
        if agent_id not in self.routing_weights:
            # Initialisation des poids pour un nouvel agent
            self.routing_weights[agent_id] = {
                feature: random.uniform(-0.5, 0.5) for feature in features.keys()
            }
        
        # Calcul du score pondéré
        score = 0.0
        weights = self.routing_weights[agent_id]
        
        for feature, value in features.items():
            weight = weights.get(feature, 0.0)
            score += weight * value
        
        # Activation sigmoïde
        return 1.0 / (1.0 + math.exp(-score))
    
    def update_weights(self, agent_id: str, features: Dict[str, float], 
                      performance_score: float):
        """Met à jour les poids neuraux basés sur la performance."""
        if agent_id not in self.routing_weights:
            return
        
        # Enregistrement de la performance
        if agent_id not in self.performance_history:
            self.performance_history[agent_id] = []
        self.performance_history[agent_id].append(performance_score)
        
        # Mise à jour des poids via gradient descent simplifié
        error = performance_score - 0.5  # Cible de 0.5
        
        for feature, value in features.items():
            if feature in self.routing_weights[agent_id]:
                gradient = error * value
                self.routing_weights[agent_id][feature] += self.learning_rate * gradient


class LoopSuppressor:
    """Système de suppression des boucles récursives."""
    
    def __init__(self, max_loop_depth: int = 5):
        self.execution_stack: List[str] = []
        self.loop_patterns: Dict[str, int] = {}
        self.max_loop_depth = max_loop_depth
    
    def check_for_loops(self, task: WorkflowTask, 
                       context: Dict[str, Any]) -> Dict[str, Any]:
        """Vérifie la présence de boucles récursives."""
        task_signature = self._generate_task_signature(task)
        
        # Vérification de la profondeur de la pile
        if len(self.execution_stack) >= self.max_loop_depth:
            return {
                "loop_detected": True,
                "loop_type": "depth_exceeded",
                "stack_depth": len(self.execution_stack),
                "task_signature": task_signature
            }
        
        # Vérification des patterns répétitifs
        if task_signature in self.execution_stack:
            loop_start = self.execution_stack.index(task_signature)
            loop_length = len(self.execution_stack) - loop_start
            
            return {
                "loop_detected": True,
                "loop_type": "recursive_pattern",
                "loop_length": loop_length,
                "loop_start_index": loop_start,
                "task_signature": task_signature
            }
        
        # Vérification des patterns fréquents
        if task_signature in self.loop_patterns:
            self.loop_patterns[task_signature] += 1
            if self.loop_patterns[task_signature] > 10:  # Seuil de fréquence
                return {
                    "loop_detected": True,
                    "loop_type": "frequent_pattern",
                    "frequency": self.loop_patterns[task_signature],
                    "task_signature": task_signature
                }
        else:
            self.loop_patterns[task_signature] = 1
        
        # Aucune boucle détectée
        self.execution_stack.append(task_signature)
        return {
            "loop_detected": False,
            "task_signature": task_signature,
            "stack_depth": len(self.execution_stack)
        }
    
    def _generate_task_signature(self, task: WorkflowTask) -> str:
        """Génère une signature unique pour une tâche."""
        signature_data = f"{task.task_type}_{task.description[:30]}_{task.priority}"
        return hashlib.md5(signature_data.encode()).hexdigest()[:12]
    
    def pop_execution_stack(self, task_signature: str):
        """Retire une tâche de la pile d'exécution."""
        if task_signature in self.execution_stack:
            self.execution_stack.remove(task_signature)
    
    def clear_execution_stack(self):
        """Vide la pile d'exécution."""
        self.execution_stack.clear()


class ContextAnalyzer:
    """Analyseur de contexte pour le dispatch neuronal."""
    
    def __init__(self):
        self.context_cache: Dict[str, Dict[str, Any]] = {}
        self.analysis_history: List[Dict[str, Any]] = []
    
    def analyze_context(self, task: WorkflowTask, 
                       context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse le contexte d'une tâche pour le routage."""
        analysis = {
            "task_id": task.task_id,
            "timestamp": time.time(),
            "urgency_score": self._calculate_urgency(task, context),
            "resource_score": self._calculate_resource_availability(context),
            "success_rate": self._calculate_historical_success_rate(task.task_type),
            "complexity_score": self._calculate_complexity(task),
            "available_agents": context.get("available_agents", []),
            "system_load": context.get("system_load", 0.5)
        }
        
        # Mise en cache de l'analyse
        self.context_cache[task.task_id] = analysis
        self.analysis_history.append(analysis)
        
        # Nettoyage du cache (garde les 1000 dernières analyses)
        if len(self.analysis_history) > 1000:
            old_analysis = self.analysis_history.pop(0)
            self.context_cache.pop(old_analysis["task_id"], None)
        
        return analysis
    
    def _calculate_urgency(self, task: WorkflowTask, context: Dict[str, Any]) -> float:
        """Calcule le score d'urgence d'une tâche."""
        urgency = task.priority
        
        # Facteurs d'urgence additionnels
        if context.get("deadline"):
            time_remaining = context["deadline"] - time.time()
            if time_remaining < 3600:  # Moins d'une heure
                urgency += 0.3
            elif time_remaining < 86400:  # Moins d'un jour
                urgency += 0.1
        
        # Urgence basée sur les dépendances
        if task.dependencies:
            urgency += len(task.dependencies) * 0.05
        
        return min(1.0, urgency)
    
    def _calculate_resource_availability(self, context: Dict[str, Any]) -> float:
        """Calcule la disponibilité des ressources."""
        # Simulation de calcul de disponibilité des ressources
        cpu_usage = context.get("cpu_usage", 0.5)
        memory_usage = context.get("memory_usage", 0.5)
        network_load = context.get("network_load", 0.3)
        
        resource_score = 1.0 - ((cpu_usage + memory_usage + network_load) / 3.0)
        return max(0.0, resource_score)
    
    def _calculate_historical_success_rate(self, task_type: str) -> float:
        """Calcule le taux de succès historique pour un type de tâche."""
        relevant_analyses = [
            a for a in self.analysis_history
            if a.get("task_type") == task_type
        ]
        
        if not relevant_analyses:
            return 0.7  # Valeur par défaut
        
        # Simulation du calcul de taux de succès
        return sum(a.get("success", 0.7) for a in relevant_analyses) / len(relevant_analyses)
    
    def _calculate_complexity(self, task: WorkflowTask) -> float:
        """Calcule la complexité d'une tâche."""
        complexity = 0.0
        
        # Complexité basée sur la description
        complexity += len(task.description) / 500.0  # Normalisation
        
        # Complexité basée sur les dépendances
        complexity += len(task.dependencies) * 0.1
        
        # Complexité basée sur les données d'entrée
        if task.input_data:
            complexity += len(str(task.input_data)) / 1000.0
        
        return min(1.0, complexity)


class MCPProtocolHandler:
    """Gestionnaire du protocole MCP (Model Context Protocol)."""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.message_queue: List[Dict[str, Any]] = []
        self.protocol_version = "1.0"
    
    def create_session(self, client_id: str, capabilities: List[str]) -> str:
        """Crée une session MCP."""
        session_id = str(uuid.uuid4())
        
        session = {
            "session_id": session_id,
            "client_id": client_id,
            "capabilities": capabilities,
            "created_at": time.time(),
            "last_activity": time.time(),
            "message_count": 0,
            "status": "active"
        }
        
        self.active_sessions[session_id] = session
        return session_id
    
    def handle_message(self, session_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Traite un message MCP."""
        if session_id not in self.active_sessions:
            return {
                "error": "Session non trouvée",
                "code": "SESSION_NOT_FOUND"
            }
        
        session = self.active_sessions[session_id]
        session["last_activity"] = time.time()
        session["message_count"] += 1
        
        # Validation du message MCP
        validation = self._validate_mcp_message(message)
        if not validation["valid"]:
            return {
                "error": "Message MCP invalide",
                "code": "INVALID_MESSAGE",
                "details": validation["errors"]
            }
        
        # Traitement du message selon le type
        message_type = message.get("method", "unknown")
        
        if message_type == "initialize":
            return self._handle_initialize(session, message)
        elif message_type == "request":
            return self._handle_request(session, message)
        elif message_type == "notification":
            return self._handle_notification(session, message)
        else:
            return {
                "error": f"Type de message non supporté: {message_type}",
                "code": "UNSUPPORTED_METHOD"
            }
    
    def _validate_mcp_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Valide un message selon le protocole MCP."""
        validation = {"valid": True, "errors": []}
        
        # Vérifications de base
        if "jsonrpc" not in message or message["jsonrpc"] != "2.0":
            validation["valid"] = False
            validation["errors"].append("Version JSON-RPC invalide")
        
        if "method" not in message:
            validation["valid"] = False
            validation["errors"].append("Méthode manquante")
        
        if "id" not in message:
            validation["valid"] = False
            validation["errors"].append("ID de message manquant")
        
        return validation
    
    def _handle_initialize(self, session: Dict[str, Any], 
                          message: Dict[str, Any]) -> Dict[str, Any]:
        """Traite un message d'initialisation MCP."""
        params = message.get("params", {})
        
        return {
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "protocolVersion": self.protocol_version,
                "capabilities": {
                    "orchestration": True,
                    "neural_routing": True,
                    "loop_suppression": True
                },
                "serverInfo": {
                    "name": "Symphony Orchestrator",
                    "version": "1.0.0"
                }
            }
        }
    
    def _handle_request(self, session: Dict[str, Any], 
                       message: Dict[str, Any]) -> Dict[str, Any]:
        """Traite une requête MCP."""
        method = message.get("method")
        params = message.get("params", {})
        
        if method == "orchestrate_workflow":
            # Simulation d'orchestration de workflow
            workflow_id = params.get("workflow_id")
            input_data = params.get("input_data", {})
            
            return {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {
                    "execution_id": str(uuid.uuid4()),
                    "status": "started",
                    "workflow_id": workflow_id
                }
            }
        
        return {
            "jsonrpc": "2.0",
            "id": message["id"],
            "error": {
                "code": "METHOD_NOT_FOUND",
                "message": f"Méthode {method} non trouvée"
            }
        }
    
    def _handle_notification(self, session: Dict[str, Any], 
                           message: Dict[str, Any]) -> Dict[str, Any]:
        """Traite une notification MCP."""
        # Les notifications ne nécessitent pas de réponse
        method = message.get("method")
        params = message.get("params", {})
        
        # Enregistrement de la notification
        self.message_queue.append({
            "type": "notification",
            "method": method,
            "params": params,
            "session_id": session["session_id"],
            "timestamp": time.time()
        })
        
        return {"status": "notification_received"}


class A2AProtocolHandler:
    """Gestionnaire du protocole A2A (Agent-to-Agent)."""
    
    def __init__(self):
        self.agent_directory: Dict[str, Dict[str, Any]] = {}
        self.message_routing_table: Dict[str, str] = {}
        self.delivery_confirmations: Dict[str, Dict[str, Any]] = {}
    
    def register_agent(self, agent_id: str, agent_info: Dict[str, Any]) -> bool:
        """Enregistre un agent dans le protocole A2A."""
        self.agent_directory[agent_id] = {
            "agent_id": agent_id,
            "registered_at": time.time(),
            "last_seen": time.time(),
            "message_count": 0,
            "capabilities": agent_info.get("capabilities", []),
            "endpoint": agent_info.get("endpoint"),
            "status": "active"
        }
        
        return True
    
    def route_message(self, sender_id: str, receiver_id: str, 
                     message: Dict[str, Any]) -> Dict[str, Any]:
        """Route un message entre agents via A2A."""
        # Validation des agents
        if sender_id not in self.agent_directory:
            return {
                "status": "failed",
                "error": f"Agent expéditeur {sender_id} non enregistré"
            }
        
        if receiver_id not in self.agent_directory:
            return {
                "status": "failed",
                "error": f"Agent destinataire {receiver_id} non enregistré"
            }
        
        # Création du message A2A
        a2a_message = {
            "message_id": str(uuid.uuid4()),
            "sender": sender_id,
            "receiver": receiver_id,
            "timestamp": time.time(),
            "message_type": message.get("type", "general"),
            "payload": message,
            "routing_info": {
                "hops": 0,
                "route": [sender_id, receiver_id]
            }
        }
        
        # Enregistrement du routage
        self.message_routing_table[a2a_message["message_id"]] = receiver_id
        
        # Mise à jour des statistiques
        self.agent_directory[sender_id]["message_count"] += 1
        self.agent_directory[sender_id]["last_seen"] = time.time()
        
        # Simulation de la livraison
        delivery_result = self._simulate_message_delivery(a2a_message)
        
        return {
            "status": "routed",
            "message_id": a2a_message["message_id"],
            "delivery_result": delivery_result
        }
    
    def _simulate_message_delivery(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Simule la livraison d'un message A2A."""
        message_id = message["message_id"]
        receiver_id = message["receiver"]
        
        # Simulation de la livraison
        delivery_success = random.random() > 0.05  # 95% de succès
        
        delivery_result = {
            "message_id": message_id,
            "receiver_id": receiver_id,
            "delivered": delivery_success,
            "delivery_time": time.time(),
            "attempts": 1
        }
        
        if not delivery_success:
            delivery_result["error"] = "Échec de livraison simulé"
        
        self.delivery_confirmations[message_id] = delivery_result
        return delivery_result
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Récupère le statut d'un agent."""
        return self.agent_directory.get(agent_id)
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """Récupère les statistiques de routage."""
        total_messages = len(self.delivery_confirmations)
        successful_deliveries = sum(
            1 for delivery in self.delivery_confirmations.values()
            if delivery["delivered"]
        )
        
        return {
            "total_messages": total_messages,
            "successful_deliveries": successful_deliveries,
            "delivery_rate": successful_deliveries / total_messages if total_messages > 0 else 0.0,
            "registered_agents": len(self.agent_directory),
            "active_agents": sum(
                1 for agent in self.agent_directory.values()
                if agent["status"] == "active"
            )
        }


# Importations nécessaires pour les nouvelles fonctionnalités
import math
import random


class SymphonyAdvanced(Symphony):
    """Version avancée de Symphony avec protocoles de dispatch et gouvernance neuronale."""
    
    def __init__(self):
        super().__init__()
        
        # Composants avancés
        self.meta_orchestrator = MetaOrchestrator()
        self.mcp_handler = MCPProtocolHandler()
        self.a2a_handler = A2AProtocolHandler()
        
        # Intégration des protocoles dans le workflow engine
        self._integrate_advanced_protocols()
        
        logger.info("Symphony Advanced initialisé avec protocoles de gouvernance neuronale")
    
    def _integrate_advanced_protocols(self):
        """Intègre les protocoles avancés dans le moteur de workflow."""
        # Remplacement du dispatcher par le meta-orchestrateur
        original_select_agent = self.dispatcher.select_agent
        
        async def enhanced_select_agent(task: WorkflowTask, available_agents: List[str]) -> Optional[str]:
            # Utilisation du meta-orchestrateur pour le routage
            context = {
                "available_agents": available_agents,
                "system_load": 0.5,  # Simulation
                "cpu_usage": 0.4,
                "memory_usage": 0.6
            }
            
            routing_result = await self.meta_orchestrator.route_task(task, context)
            
            if routing_result["status"] == "routed":
                return routing_result["selected_agent"]
            elif routing_result["status"] == "suppressed":
                logger.warning(f"Tâche {task.task_id} supprimée: {routing_result['reason']}")
                return None
            else:
                # Fallback vers l'ancien système
                return original_select_agent(task, available_agents)
        
        # Remplacement de la méthode de sélection
        self.dispatcher.select_agent = enhanced_select_agent
    
    async def orchestrate_with_protocols(self, workflow_type: str, 
                                       input_data: Dict[str, Any],
                                       protocol: str = "MCP") -> Dict[str, Any]:
        """Orchestre un workflow avec validation des protocoles."""
        # Validation du protocole
        if protocol == "MCP":
            # Création d'une session MCP
            session_id = self.mcp_handler.create_session(
                client_id="symphony_client",
                capabilities=["orchestration", "workflow_management"]
            )
            
            # Traitement via MCP
            mcp_message = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "orchestrate_workflow",
                "params": {
                    "workflow_id": workflow_type,
                    "input_data": input_data
                }
            }
            
            mcp_result = self.mcp_handler.handle_message(session_id, mcp_message)
            
            if "error" in mcp_result:
                return {
                    "status": "failed",
                    "error": "Erreur de protocole MCP",
                    "details": mcp_result
                }
        
        # Exécution du workflow standard
        result = await self.orchestrate_workflow(workflow_type, input_data)
        
        # Ajout des informations de protocole
        result["protocol_info"] = {
            "protocol_used": protocol,
            "session_id": session_id if protocol == "MCP" else None,
            "governance_validated": True
        }
        
        return result
    
    def send_agent_message(self, sender_id: str, receiver_id: str, 
                          message: Dict[str, Any]) -> Dict[str, Any]:
        """Envoie un message entre agents via A2A."""
        return self.a2a_handler.route_message(sender_id, receiver_id, message)
    
    def get_advanced_status(self) -> Dict[str, Any]:
        """Retourne le statut avancé de Symphony."""
        base_status = self.get_orchestration_status()
        
        advanced_status = {
            **base_status,
            "meta_orchestrator": {
                "decisions_made": len(self.meta_orchestrator.decision_history),
                "neural_routing_accuracy": self.meta_orchestrator.neural_router.learning_rate,
                "loops_suppressed": len(self.meta_orchestrator.loop_suppressor.loop_patterns)
            },
            "mcp_protocol": {
                "active_sessions": len(self.mcp_handler.active_sessions),
                "messages_processed": len(self.mcp_handler.message_queue),
                "protocol_version": self.mcp_handler.protocol_version
            },
            "a2a_protocol": self.a2a_handler.get_routing_statistics()
        }
        
        return advanced_status

