"""Synergesis Cognitive Core package.

Exposes key helpers so that other modules can simply import
`synergesis.cognitive_core` and access memory helpers directly.
"""

from .memory_system import get_memory, MemorySystem

__all__: list[str] = [
    "get_memory",
    "MemorySystem",
]
