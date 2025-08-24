import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Configure logging to display DEBUG level messages
logging.basicConfig(level=logging.DEBUG)

# Add the project's 'python' directory to the path to allow imports
project_root = Path(__file__).resolve().parent
python_root = project_root / "python"
sys.path.insert(0, str(python_root))

# Set environment variables for local testing
os.environ['ARCHON_SERVER_PORT'] = os.getenv('ARCHON_SERVER_PORT', '8181')
os.environ['ARCHON_MCP_PORT'] = os.getenv('ARCHON_MCP_PORT', '8051')
os.environ['ARCHON_AGENTS_PORT'] = os.getenv('ARCHON_AGENTS_PORT', '8052')

from src.agents.mcp_client import MCPClient  # noqa: E402

async def main():
    """Connects to the MCP server and calls the docker_list_containers tool."""
    print("Attempting to connect to MCP server...")
    try:
        # The MCPClient will automatically discover the server URL
        client = MCPClient()
        
        print("Listing registered tools via tools/list...")
        tools = await client.list_tools()
        print("tools/list =>", tools)

        print("Calling 'health_check' tool (no arguments field)...")
        hc = await client.call_tool_raw("health_check")
        print("health_check =>", hc)

        print("Calling 'docker_list_containers' tool...")

        # First, try without arguments (should default to show_all=True)
        result = await client.call_tool_raw("docker_list_containers")
        print("docker_list_containers (no args) =>", result)

        # Then, try with explicit argument to compare behavior
        result_explicit = await client.call_tool_raw("docker_list_containers", {"show_all": True})
        print("docker_list_containers (show_all=True) =>", result_explicit)
        
        print("\n--- MCP Tool Result ---")
        print(result)
        print("-----------------------\n")
        
        if result:
            print("Successfully received a response from the MCP server.")
        else:
            print("Received an empty response from the server.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'client' in locals() and client:
            await client.close()
            print("MCP client connection closed.")

if __name__ == "__main__":
    asyncio.run(main())
