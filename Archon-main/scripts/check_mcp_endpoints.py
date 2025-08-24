import sys
import os

import requests


import uuid

def post_mcp(url: str, method: str, params: dict | None = None, timeout: int = 30, session_id: str | None = None):
    payload = {"jsonrpc": "2.0", "method": method, "id": str(uuid.uuid4())}
    if params is not None:
        payload["params"] = params
    # FastMCP streamable-http requires clients to accept both SSE and JSON
    origin = os.getenv("ARCHON_ORIGIN") or f"http://localhost:{os.getenv('ARCHON_SERVER_PORT','8181')}"
    headers = {
        "Accept": "text/event-stream, application/json",
        "Content-Type": "application/json",
        "Origin": origin,
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    r = requests.post(url, json=payload, timeout=timeout, headers=headers)
    return r


def call_tool_mcp(url: str, name: str, arguments: dict | None = None, timeout: int = 30, session_id: str | None = None):
    payload = {"jsonrpc": "2.0", "method": "tools/call", "id": str(uuid.uuid4()), "params": {"name": name}}
    if arguments is not None:
        payload["params"]["arguments"] = arguments
    origin = os.getenv("ARCHON_ORIGIN") or f"http://localhost:{os.getenv('ARCHON_SERVER_PORT','8181')}"
    headers = {
        "Accept": "text/event-stream, application/json",
        "Content-Type": "application/json",
        "Origin": origin,
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    r = requests.post(url, json=payload, timeout=timeout, headers=headers)
    return r

def check_mcp_health(url: str, session_id: str | None = None):
    try:
        # Use tools/call with empty arguments object
        r = call_tool_mcp(url, "health_check", arguments={}, timeout=30, session_id=session_id)
        print(f"MCP health_check {url} status: {r.status_code}")
        print("Response:", r.text)
    except Exception as e:
        print(f"MCP health_check failed for {url}: {e}")


def check_mcp_initialize(url: str) -> str | None:
    try:
        params = {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "archon-smoke", "version": "0.0.1"},
        }
        r = post_mcp(url, "initialize", params=params, timeout=30)
        print(f"MCP initialize {url} status: {r.status_code}")
        print("Response:", r.text)
        sid = r.headers.get("mcp-session-id") or r.headers.get("MCP-Session-Id")
        print("mcp-session-id header:", sid)
        return sid
    except Exception as e:
        print(f"MCP initialize failed for {url}: {e}")
        return None


if __name__ == '__main__':
    port = os.getenv("ARCHON_MCP_PORT", "8051")
    host = f'http://localhost:{port}'
    base_url = f"{host}/mcp"

    print('Running MCP endpoint smoke tests against', host)
    session_id = check_mcp_initialize(base_url)
    if not session_id:
        print("Failed to obtain MCP session. Exiting.")
        sys.exit(1)

    # Send 'initialized' notification per MCP handshake
    try:
        post_mcp(base_url, "notifications/initialized", params={}, timeout=10, session_id=session_id)
    except Exception as ne:
        print(f"Initialized notification failed: {ne}")

    # Health check using the session
    check_mcp_health(base_url, session_id)
    sys.exit(0)
