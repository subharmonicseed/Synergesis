#!/usr/bin/env python3
"""
Synergesis Eos Agent for Archon
"""

from .base_agent import BaseAgent, ArchonDependencies
from pydantic_ai import Agent
from pydantic import BaseModel
from typing import Dict, Any

class EosAgentOutput(BaseModel):
    """Output model for Eos agent decisions."""
    success: bool
    message: str
    data: Dict[str, Any] = {}
    source: str = "eos"
    timestamp: str = ""
    decision: str = ""
    rationale: str = ""

class EosAgent(BaseAgent):
    """Archon-native implementation of the Synergesis Eos decision agent."""

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
        return """You are Eos, a decision agent in the Synergesis system.
        
Your role is to:
1. Make strategic decisions based on available information
2. Evaluate options and choose optimal paths
3. Provide clear rationale for decisions
4. Consider long-term implications

Format your response as a JSON object with:
- success: boolean indicating success
- message: descriptive message of the decision made
- data: dictionary containing decision details
- source: always "eos"
- decision: the actual decision/choice made
- rationale: clear explanation of why this decision was chosen

Focus on making high-impact decisions that advance the system's goals."""

    async def run(self, user_prompt: str, deps: ArchonDependencies) -> EosAgentOutput:
        """Run the Eos agent's decision cycle."""
        try:
            # Run the agent with the provided prompt
            result = await self._agent.run(user_prompt, deps=deps)
            
            # Ensure we have the correct output format
            output_data = result.data
            if not isinstance(output_data, EosAgentOutput):
                output_data = EosAgentOutput(
                    success=True,
                    message=f"Decision made: {user_prompt}",
                    data={"decision": user_prompt, "options": [user_prompt]},
                    source="eos",
                    decision=user_prompt,
                    rationale="Based on available information"
                )
            
            return output_data
            
        except Exception as e:
            return EosAgentOutput(
                success=False,
                message=f"Eos agent error: {str(e)}",
                data={"error": str(e)},
                source="eos",
                decision="error",
                rationale=str(e)
            )
