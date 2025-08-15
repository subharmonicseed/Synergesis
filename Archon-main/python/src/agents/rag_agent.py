from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from .base_agent import BaseAgent
from .mcp_client import get_mcp_client

logger = logging.getLogger(__name__)


class RagDependencies(BaseModel):
    """Dependencies for the RAG agent, allowing for source filtering."""

    source_filter: str | None = Field(
        None, description="Filter search by a specific source document"
    )


class RagOutput(BaseModel):
    """Output model for the RAG agent, including the answer and citations."""

    answer: str = Field(..., description="The synthesized answer to the user's query")
    citations: list[str] = Field(
        ..., description="A list of source documents used to generate the answer"
    )


class RagAgent(BaseAgent[RagDependencies, RagOutput]):
    """
    Conversational agent for RAG-based document search and retrieval.

    Capabilities:
    - Search documents using natural language queries
    - Filter by specific sources
    - Search code examples
    - Provide synthesized answers with citations
    - Explain concepts found in documentation
    """


    def _create_agent(self, **kwargs) -> "Agent":
        from pydantic_ai import Agent

        system_prompt = """You are a specialized RAG agent. Your role is to answer questions by querying a knowledge base.

Available Tools:
- `perform_rag_query(query: str, source: str | None = None, match_count: int = 5)`: Search the knowledge base. `source` can be used to filter by a specific document source.
- `get_available_sources()`: List all available document sources to filter by."""

        mcp_client = kwargs.get("mcp_client")

        if not mcp_client:
            raise ValueError("MCPClient not provided to RagAgent")

        agent = Agent(
            model=self.model,
            output_type=RagOutput,
            deps_type=RagDependencies,
            system_prompt=system_prompt,
            tools=[
                mcp_client.perform_rag_query,
                mcp_client.get_available_sources,
            ],
            **kwargs,
        )
        return agent

    def get_system_prompt(self) -> str:
        return """
        You are a Retrieval-Augmented Generation (RAG) agent.
        Your primary function is to search a knowledge base and use the retrieved information
        to answer user queries accurately and concisely.

        **Core Directives:**
        - **Answer from Sources:** Base all answers strictly on the information found in the provided source documents.
        - **Cite Everything:** Every piece of information in your answer must be attributed to its source.
        - **Be Concise:** Provide clear and direct answers. Avoid speculation or information not present in the sources.
        - **Admit Ignorance:** If the answer cannot be found in the sources, state that clearly. Do not invent answers.

        **Workflow:**
        1. **Analyze Query:** Deconstruct the user's request to identify key entities and intent.
        2. **Formulate Search:** Use the identified keys to perform a targeted search of the knowledge base.
        3. **Synthesize Answer:** Construct a response using only the retrieved information.
        4. **Cite Sources:** Append the source citations to your answer.
        """
