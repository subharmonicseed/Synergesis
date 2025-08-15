"""
Agents module for PydanticAI-powered agents in the Archon system.

This module contains various specialized agents for different tasks:
- DocumentAgent: Processes and validates project documentation
- PlanningAgent: Generates feature plans and technical specifications
- ERDAgent: Creates entity relationship diagrams
- TaskAgent: Generates and manages project tasks
- SynergesisVyraAgent: Perception agent for pattern recognition
- SynergesisEosAgent: Decision agent for strategic choices
- SynergesisThalesAgent: Action agent for implementation

All agents are built using PydanticAI for type safety and structured outputs.
"""

from .base_agent import BaseAgent
from .document_agent import DocumentAgent
from .rag_agent import RagAgent
from .synergesis_vyra_agent import VyraAgent
from .synergesis_eos_agent import EosAgent
from .synergesis_thales_agent import ThalesAgent

__all__ = ["BaseAgent", "DocumentAgent", "RagAgent", "VyraAgent", "EosAgent", "ThalesAgent"]
