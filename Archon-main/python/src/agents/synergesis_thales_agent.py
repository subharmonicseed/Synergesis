#!/usr/bin/env python3
"""
Synergesis Thales Agent for Archon
"""

from .base_agent import BaseAgent, ArchonDependencies
from pydantic_ai import Agent
from pydantic import BaseModel
from typing import Dict, Any

class ThalesAgentOutput(BaseModel):
    """Output model for Thales agent actions."""
    success: bool
    message: str
    data: Dict[str, Any] = {}
    source: str = "thales"
    timestamp: str = ""
    action: str = ""
    result: str = ""

class ThalesAgent(BaseAgent):
    """Archon-native implementation of the Synergesis Thales action agent."""

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
        return """You are Thales, an action agent in the Synergesis system.
        
Your role is to:
1. Execute actions based on decisions and insights
2. Implement solutions and changes
3. Document outcomes and results
4. Provide feedback on action effectiveness

Format your response as a JSON object with:
- success: boolean indicating success
- message: descriptive message of the action taken
- data: dictionary containing action details and results
- source: always "thales"
- action: the specific action executed
- result: the outcome of the action

Focus on taking concrete actions that produce measurable results."""

    async def run(self, user_prompt: str, deps: ArchonDependencies) -> ThalesAgentOutput:
        """Run the Thales agent's action cycle."""
        try:
            # Run the agent with the provided prompt
            result = await self._agent.run(user_prompt, deps=deps)
            
            # Ensure we have the correct output format
            output_data = result.data
            if not isinstance(output_data, ThalesAgentOutput):
                output_data = ThalesAgentOutput(
                    success=True,
                    message=f"Action executed: {user_prompt}",
                    data={"action": user_prompt, "result": "completed"},
                    source="thales",
                    action=user_prompt,
                    result="success"
                )
            
            return output_data
            
        except Exception as e:
            return ThalesAgentOutput(
                success=False,
                message=f"Thales agent error: {str(e)}",
                data={"error": str(e)},
                source="thales",
                action="error",
                result=str(e)
            )
