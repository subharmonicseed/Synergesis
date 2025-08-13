"""Cognitive Core module."""

from __future__ import annotations
from pathlib import Path
import sys

# The local package may be run in-place; ensure root in `sys.path`
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# now safe to import
from .memory_system import MemorySystem

_MEMORY: MemorySystem | None = None

def get_memory() -> "MemorySystem":
    """Get singleton MemorySystem instance."""
    global _MEMORY
    if _MEMORY is None:
        _MEMORY = MemorySystem()
    return _MEMORY

def get_intention_generator() -> "IntentionGenerator":
    """Get singleton IntentionGenerator instance."""
    global _INTENTION_GENERATOR
    if _INTENTION_GENERATOR is None:
        from .intention_generator import IntentionGenerator
        _INTENTION_GENERATOR = IntentionGenerator()
    return _INTENTION_GENERATOR

# Re-export for convenience
__all__ = [
    "MemorySystem",
    "get_memory",
    "get_intention_generator"
]