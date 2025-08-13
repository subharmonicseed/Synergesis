"""
Memory factory to provide singleton access to the MemorySystem.
"""

from __future__ import annotations
from typing import Optional
from .memory_system import MemorySystem

_MEMORY: Optional[MemorySystem] = None

def get_memory() -> MemorySystem:
    """
    Get the global MemorySystem instance.
    
    Returns:
        MemorySystem: Singleton instance of MemorySystem
    """
    global _MEMORY
    if _MEMORY is None:
        _MEMORY = MemorySystem()
    return _MEMORY
