import asyncio
import os
import sys
from pathlib import Path

# Add the project's 'python' directory to the path to allow imports
project_root = Path(__file__).resolve().parent
python_root = project_root / "python"
sys.path.insert(0, str(python_root))

# Set environment variables for local testing
os.environ['ARCHON_SERVER_PORT'] = '8181'
os.environ['ARCHON_MCP_PORT'] = '8051'
os.environ['ARCHON_AGENTS_PORT'] = '8052'

from src.agents.mcp_client import MCPClient  # noqa: E402

async def main():
    """Connects to the MCP server and calls the docker.list_containers tool."""
    print("Attempting to connect to MCP server...")
    try:
        # The MCPClient will automatically discover the server URL
        client = MCPClient()
        
        print("Calling 'docker.list_containers' tool...")
        # We need to use the generic 'call_tool' method for our custom tool
        result = await client.call_tool("docker.list_containers", show_all=True)
        
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
