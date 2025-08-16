"""
MCP Client for Agents

This lightweight client allows PydanticAI agents to call MCP tools via HTTP.
Agents use this client to access all data operations through the MCP protocol
instead of direct database access or service imports.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for calling MCP tools via HTTP."""

    def __init__(self, mcp_url: str = None):
        """
        Initialize MCP client.

        Args:
            mcp_url: MCP server URL (defaults to service discovery)
        """
        if mcp_url:
            self.mcp_url = mcp_url
        else:
            # Use service discovery to find MCP server
            try:
                from ..server.config.service_discovery import get_mcp_url

                self.mcp_url = get_mcp_url()
            except ImportError:
                # Fallback for when running in agents container
                import os

                mcp_port = os.getenv("ARCHON_MCP_PORT", "8051")
                if os.getenv("DOCKER_CONTAINER"):
                    self.mcp_url = f"http://archon-mcp:{mcp_port}"
                else:
                    self.mcp_url = f"http://localhost:{mcp_port}"

        self.client = httpx.AsyncClient(timeout=30.0)
        self._session_id = None
        self.session_initialized = False
        logger.info(f"MCP Client initialized with URL: {self.mcp_url}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _initialize_session(self):
        """Initialize MCP session if not already done."""
        if self._session_id:
            logger.info(f"Using existing MCP session: {self._session_id}")
            return
            
        try:
            # Initialize MCP session
            init_data = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "archon-mcp-client",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            }
            
            logger.debug(f"Sending MCP request: {json.dumps(init_data)}")
            response = await self.client.post(
                f"{self.mcp_url}/mcp",
                json=init_data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            
            if response.status_code == 200:
                session_id = response.headers.get("mcp-session-id")
                if session_id:
                    self._session_id = session_id
                    logger.info(f"New MCP session initialized with ID: {self._session_id}")
                    await asyncio.sleep(0.1)  # Add a small delay to prevent race conditions
                    self.session_initialized = True
                else:
                    logger.error("MCP session initialization failed: 'mcp-session-id' header not found in response.")
            else:
                logger.error(f"Failed to initialize MCP session. Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {e}")
            raise e

    async def call_tool(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """
        Call an MCP tool via HTTP.

        Args:
            tool_name: Name of the MCP tool to call
            **kwargs: Arguments to pass to the tool

        Returns:
            dict: Tool execution result
        """
        try:
            await self._initialize_session()

            params = {
                "name": tool_name,
                "arguments": kwargs
            }

            call_data = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": kwargs},
                "id": str(uuid.uuid4())
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }

            if self._session_id:
                headers["mcp-session-id"] = self._session_id

            response = await self.client.post(
                f"{self.mcp_url}/mcp",
                json=call_data,
                headers=headers,
            )

            if response.status_code == 200:
                # Parse SSE format response
                lines = response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            # The actual result is inside the 'result' field of the JSON-RPC response
                            if 'result' in data:
                                return data['result']
                            elif 'error' in data:
                                logger.error(f"MCP tool call returned an error: {data['error']}")
                                return data
                        except json.JSONDecodeError:
                            pass
                return {"error": "Failed to parse or find data in response"}
            else:
                raise Exception(f"MCP tool call failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise e

    # Convenience methods for common MCP tools

    async def perform_rag_query(self, query: str, source: str = None, match_count: int = 5) -> str:
        """Perform a RAG query through MCP."""
        result = await self.call_tool(
            "perform_rag_query", query=query, source=source, match_count=match_count
        )
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def get_available_sources(self) -> str:
        """Get available sources through MCP."""
        result = await self.call_tool("get_available_sources")
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def search_code_examples(
        self, query: str, source_id: str = None, match_count: int = 5
    ) -> str:
        """Search code examples through MCP."""
        result = await self.call_tool(
            "search_code_examples", query=query, source_id=source_id, match_count=match_count
        )
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def manage_project(self, action: str, **kwargs) -> str:
        """Manage projects through MCP."""
        result = await self.call_tool("manage_project", action=action, **kwargs)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def manage_document(self, action: str, project_id: str, **kwargs) -> str:
        """Manage documents through MCP."""
        result = await self.call_tool(
            "manage_document", action=action, project_id=project_id, **kwargs
        )
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def manage_task(self, action: str, project_id: str, **kwargs) -> str:
        """Manage tasks through MCP."""
        result = await self.call_tool("manage_task", action=action, project_id=project_id, **kwargs)
        return json.dumps(result) if isinstance(result, dict) else str(result)


# Global MCP client instance (created on first use)
_mcp_client: MCPClient | None = None


async def get_mcp_client() -> MCPClient:
    """
    Get or create the global MCP client instance.

    Returns:
        MCPClient instance
    """
    global _mcp_client

    if _mcp_client is None:
        _mcp_client = MCPClient()

    return _mcp_client
