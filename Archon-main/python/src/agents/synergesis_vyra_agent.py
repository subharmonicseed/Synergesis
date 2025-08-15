#!/usr/bin/env python3
"""
Synergesis Vyra Agent for Archon
"""

from .base_agent import BaseAgent, ArchonDependencies
from pydantic_ai import Agent
from pydantic import BaseModel
from typing import Any

class VyraAgentOutput(BaseModel):
    """Output model for Vyra agent discoveries."""
    success: bool
    message: str
    data: dict[str, Any] = {}
    source: str = "vyra"
    timestamp: str = ""

class VyraAgent(BaseAgent):
    """Archon-native implementation of the Synergesis Vyra perception agent."""

    def _create_agent(self, **kwargs) -> Agent:
        """Create and configure the PydanticAI agent."""
        # Remove arguments that shouldn't be passed to Agent constructor
        kwargs.pop('mcp_client', None)
        
        return Agent(
            model=self.model,
            system_prompt=self.get_system_prompt(),
            **kwargs
        )

    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return """You are Vyra, a perception agent in the Synergesis system.
        
Your role is to:
1. Analyze incoming data and identify patterns
2. Extract meaningful insights from observations
3. Generate new knowledge through perception
4. Maintain awareness of system state

Format your response as a JSON object with:
- success: boolean indicating success
- message: descriptive message of what was discovered
- data: dictionary containing the actual insights/patterns
- source: always "vyra"
- timestamp: current timestamp

Focus on perceiving patterns, anomalies, and emergent behaviors."""

    async def run(self, user_prompt: str, deps: ArchonDependencies) -> VyraAgentOutput:
        """Run the Vyra agent's perception cycle."""
        try:
            # Run the agent with the provided prompt
            result = await self._agent.run(user_prompt, deps=deps)
            
            # Ensure we have the correct output format
            output_data = result.data
            if not isinstance(output_data, VyraAgentOutput):
                return VyraAgentOutput(
                    success=True,
                    message=f"Perceived: {user_prompt}",
                    data={"perception": user_prompt},
                    source="vyra"
                )
            
            return output_data
            
        except Exception as e:
            return VyraAgentOutput(
                success=False,
                message=f"Vyra agent error: {str(e)}",
                data={"error": str(e)},
                source="vyra"
            )
