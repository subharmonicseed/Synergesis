import asyncio
from typing import Dict, Any, List, Optional

class AgentContext:
    """
    Provides a shared context for all agents, including access to storage
    and shared application state.
    """
    def __init__(self, storage: Optional[Any] = None, shared_state: Optional[Dict[str, Any]] = None):
        self.storage = storage
        self.shared_state = shared_state if shared_state is not None else {}

class BaseAgent:
    """
    The fundamental building block for all agents in the Synergesis system.
    """
    def __init__(self, ctx: AgentContext):
        self.context = ctx

    async def perceive(self, glyph_bus: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        The core perception method for an agent. This method is called on each
        evolution cycle with the current state of the glyph bus.
        Subclasses must implement their own logic.
        """
        # Base implementation does nothing but acknowledge the perception.
        await asyncio.sleep(0) # Yield control to the event loop.
        return {"agent": self.__class__.__name__, "action": "perceived", "glyphs_count": len(glyph_bus)}
