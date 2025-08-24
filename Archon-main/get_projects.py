import os
import json
import requests
import uuid

# Temporarily add Syn to path to import ArchonClient
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Syn')))

try:
    from external_agent_orchestrator import ArchonClient
except ImportError:
    print("Error: Could not import ArchonClient. Make sure Syn directory is in PYTHONPATH.")
    sys.exit(1)

import time

def call_mcp_tool(client: ArchonClient, tool_name: str, arguments: dict):
    """Generic tool caller that uses the client's session management."""
    client._initialize_session()  # Handles session creation
    time.sleep(1)  # Give server a moment to process session
    params = {"name": tool_name, "arguments": arguments}
    call_data = {"jsonrpc": "2.0", "method": "tools/call", "params": params, "id": str(uuid.uuid4())}

    resp = requests.post(client.mcp_url, json=call_data, headers=client._headers(), timeout=60)
    resp.raise_for_status()
    body = resp.json()

    if "result" in body:
        # The actual result from the tool is often a JSON string itself
        result_data = body["result"]
        if isinstance(result_data, str):
            try:
                return json.loads(result_data)
            except json.JSONDecodeError:
                return result_data # Return as string if not JSON
        return result_data
    if "error" in body:
        raise RuntimeError(f"MCP tool error: {body['error']}")
    return body

def main():
    archon_base = os.getenv("ARCHON_MCP_BASE") or "http://localhost:8051"
    client = ArchonClient(archon_base)

    try:
        projects = call_mcp_tool(client, "manage_project", {"action": "list"})
        print(json.dumps(projects, indent=2))
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
