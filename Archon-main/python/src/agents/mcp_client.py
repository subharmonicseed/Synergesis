"""
MCP Client for Agents

This lightweight client allows PydanticAI agents to call MCP tools via HTTP.
Agents use this client to access all data operations through the MCP protocol
instead of direct database access or service imports.
"""

import asyncio
import json
import logging
import os
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
            except Exception as e:
                # Fallback when service discovery is unavailable or misconfigured
                logger.warning(f"Service discovery failed: {type(e).__name__}: {e}. Falling back to defaults.")
                mcp_port = os.getenv("ARCHON_MCP_PORT", "8051")
                if os.getenv("DOCKER_CONTAINER"):
                    self.mcp_url = f"http://archon-mcp:{mcp_port}"
                else:
                    self.mcp_url = f"http://localhost:{mcp_port}"

        # Compute Origin header (required by some servers/proxies during initialize)
        # Prefer explicit ARCHON_ORIGIN, otherwise default to API server port
        self.origin = os.getenv("ARCHON_ORIGIN") or f"http://localhost:{os.getenv('ARCHON_SERVER_PORT','8181')}"

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
                    "protocolVersion": "2025-03-26",
                    # Declare basic client capabilities for maximum compatibility
                    "capabilities": {
                        "tools": {"listChanged": True}
                    },
                    "clientInfo": {
                        "name": "archon-mcp-client",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            }
            
            logger.debug(f"Sending MCP request: {json.dumps(init_data)}")
            last_error: Exception | None = None
            session_id: str | None = None

            # Attempt 1: Prefer SSE (SSE-first Accept) and stream; parse response to complete handshake
            try:
                async with self.client.stream(
                    "POST",
                    f"{self.mcp_url}/mcp",
                    json=init_data,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream, application/json",
                        "Origin": self.origin,
                    },
                ) as response:
                    session_id = response.headers.get("mcp-session-id")
                    if response.status_code in (200, 206):
                        ctype = response.headers.get("content-type", "")
                        # If JSON, read and parse once
                        if "application/json" in ctype:
                            raw = await response.aread()
                            try:
                                text = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
                                data = json.loads(text)
                                if "error" in data:
                                    logger.warning(f"Initialize returned error: {data['error']}")
                                else:
                                    logger.debug("Initialize JSON response parsed successfully")
                            except Exception as ex:
                                logger.debug(f"Initialize JSON parse failed: {type(ex).__name__}: {ex}")
                        else:
                            # Treat as SSE and consume until we see a response object
                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                if line.startswith("data: "):
                                    payload = line[6:].strip()
                                    try:
                                        data = json.loads(payload)
                                    except json.JSONDecodeError:
                                        continue
                                    # Expect a single response with result or error
                                    if "result" in data or "error" in data:
                                        logger.debug("Initialize SSE response received")
                                        break
                    else:
                        # Read a small body (best effort) for diagnostics
                        body = b""
                        try:
                            body = await response.aread()
                        except Exception:
                            pass
                        preview = body.decode("utf-8", errors="ignore")[:300]
                        logger.warning(
                            f"Initialize returned status {response.status_code}. Body: {preview}"
                        )
            except Exception as e1:
                last_error = e1
                logger.warning(f"Initialize attempt (SSE-first) failed: {type(e1).__name__}: {e1}")

            # If no session yet, Attempt 2: Accept JSON only (some servers return 406 but include session id)
            if not session_id:
                try:
                    async with self.client.stream(
                        "POST",
                        f"{self.mcp_url}/mcp",
                        json=init_data,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Origin": self.origin,
                        },
                    ) as response2:
                        session_id = response2.headers.get("mcp-session-id")
                        if response2.status_code not in (200, 206):
                            body = b""
                            try:
                                body = await response2.aread()
                            except Exception:
                                pass
                            preview = body.decode("utf-8", errors="ignore")[:300]
                            logger.warning(
                                f"Initialize (JSON only) status {response2.status_code}. Body: {preview}"
                            )
                except Exception as e2:
                    last_error = e2
                    logger.warning(f"Initialize fallback (JSON only) failed: {type(e2).__name__}: {e2}")

            if session_id:
                self._session_id = session_id
                logger.info(f"New MCP session initialized with ID: {self._session_id}")
                # Give the server time to finalize initialization before next call
                await asyncio.sleep(1.0)
                # Send a follow-up 'initialized' notification for compatibility with some servers
                try:
                    notify_headers = {
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream, application/json",
                        "mcp-session-id": self._session_id,
                        "Origin": self.origin,
                    }
                    # Correct method name per MCP spec
                    notify_data = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
                    async with self.client.stream(
                        "POST",
                        f"{self.mcp_url}/mcp",
                        json=notify_data,
                        headers=notify_headers,
                    ) as _notify_resp:
                        # Best-effort: consume any payload then move on
                        try:
                            await _notify_resp.aread()
                        except Exception:
                            pass
                except Exception as ne:
                    logger.debug(f"Initialized notification failed: {type(ne).__name__}: {ne}")
                self.session_initialized = True
                return
            
            # If we reached here, no session could be obtained
            if last_error:
                logger.warning(f"Proceeding without session id due to init error: {type(last_error).__name__}: {last_error}")
            else:
                logger.warning("Proceeding without session id: initialize returned no session header")
            return
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {type(e).__name__}: {e}")
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
            params = {"name": tool_name}
            # Include 'arguments' always; use empty object for no-arg tools per MCP spec
            params["arguments"] = kwargs or {}

            call_data = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": params,
                "id": str(uuid.uuid4()),
            }

            headers = {
                "Content-Type": "application/json",
                # Prefer SSE first per FastMCP streamable-http, still allow JSON
                "Accept": "text/event-stream, application/json",
                "Origin": self.origin,
            }

            if self._session_id:
                headers["mcp-session-id"] = self._session_id
            
            # Stream the response to handle SSE properly
            async with self.client.stream(
                "POST",
                f"{self.mcp_url}/mcp",
                json=call_data,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    text = ""
                    try:
                        text = await response.aread()
                        text = text.decode("utf-8", errors="ignore") if isinstance(text, (bytes, bytearray)) else str(text)
                    except Exception:
                        pass
                    raise Exception(f"MCP tool call failed: {response.status_code} - {text[:300]}")

                content_type = response.headers.get("content-type", "")

                # If JSON, read once
                if "application/json" in content_type:
                    raw = await response.aread()
                    try:
                        text = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
                        data = json.loads(text)
                    except Exception as ex:
                        logger.error(f"Failed to decode JSON response: {type(ex).__name__}: {ex}")
                        return {"error": "Failed to decode JSON response"}
                    if "result" in data:
                        return data["result"]
                    if "error" in data:
                        logger.error(f"MCP tool call returned an error: {data['error']}")
                        return data
                    return {"error": "Unexpected JSON response shape"}

                # Otherwise, treat as SSE and iterate lines
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        payload = line[6:].strip()
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if "result" in data:
                            return data["result"]
                        if "error" in data:
                            logger.error(f"MCP tool call returned an error: {data['error']}")
                            return data
                return {"error": "No result received over SSE"}
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise e

    async def call_tool_raw(self, tool_name: str, arguments: dict | None = None) -> dict[str, Any]:
        """Call an MCP tool but omit the 'arguments' field if None.

        Useful for zero-arg tools like `health_check` when the server rejects
        an explicit empty object for arguments.
        """
        try:
            await self._initialize_session()

            params: dict[str, Any] = {"name": tool_name}
            if arguments is not None:
                params["arguments"] = arguments

            call_data = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": params,
                "id": str(uuid.uuid4()),
            }

            headers = {
                "Content-Type": "application/json",
                # Prefer SSE first per FastMCP streamable-http, still allow JSON
                "Accept": "text/event-stream, application/json",
                "Origin": self.origin,
            }
            if self._session_id:
                headers["mcp-session-id"] = self._session_id

            async with self.client.stream(
                "POST",
                f"{self.mcp_url}/mcp",
                json=call_data,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    text = ""
                    try:
                        text = await response.aread()
                        text = text.decode("utf-8", errors="ignore") if isinstance(text, (bytes, bytearray)) else str(text)
                    except Exception:
                        pass
                    raise Exception(f"MCP tool call failed: {response.status_code} - {text[:300]}")

                content_type = response.headers.get("content-type", "")

                if "application/json" in content_type:
                    raw = await response.aread()
                    try:
                        text = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
                        data = json.loads(text)
                    except Exception as ex:
                        logger.error(f"Failed to decode JSON response: {type(ex).__name__}: {ex}")
                        return {"error": "Failed to decode JSON response"}
                    if "result" in data:
                        return data["result"]
                    if "error" in data:
                        logger.error(f"MCP tool call returned an error: {data['error']}")
                        return data
                    return {"error": "Unexpected JSON response shape"}

                # Otherwise treat as SSE
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        payload = line[6:].strip()
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if "result" in data:
                            return data["result"]
                        if "error" in data:
                            logger.error(f"MCP tool call returned an error: {data['error']}")
                            return data
                return {"error": "No result received over SSE"}
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise e

    async def list_tools(self) -> dict[str, Any]:
        """Call the MCP method 'tools/list' to enumerate registered tools."""
        try:
            await self._initialize_session()

            # Send empty params object per spec
            call_data = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": str(uuid.uuid4()),
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream, application/json",
                "Origin": self.origin,
            }
            if self._session_id:
                headers["mcp-session-id"] = self._session_id
            
            async with self.client.stream(
                "POST",
                f"{self.mcp_url}/mcp",
                json=call_data,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    text = ""
                    try:
                        text = await response.aread()
                        text = text.decode("utf-8", errors="ignore") if isinstance(text, (bytes, bytearray)) else str(text)
                    except Exception:
                        pass
                    raise Exception(f"MCP tool call failed: {response.status_code} - {text[:300]}")

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    raw = await response.aread()
                    try:
                        text = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
                        data = json.loads(text)
                    except Exception as ex:
                        logger.error(f"Failed to decode JSON response: {type(ex).__name__}: {ex}")
                        return {"error": "Failed to decode JSON response"}
                    if "result" in data:
                        return data["result"]
                    if "error" in data:
                        logger.error(f"MCP tool call returned an error: {data['error']}")
                        return data
                    return {"error": "Unexpected JSON response shape"}
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        payload = line[6:].strip()
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if "result" in data:
                            return data["result"]
                        if "error" in data:
                            logger.error(f"MCP tool call returned an error: {data['error']}")
                            return data
                return {"error": "No result received over SSE"}
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}")
            raise e
        # Removed duplicated definitions and stray triple-quoted block

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
