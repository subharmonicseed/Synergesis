import asyncio
import os
import json
import sys
from pathlib import Path

# Make 'src' importable when running from 'python/scripts'
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.mcp_client import MCPClient

# Ensure required environment variables are set for service discovery
os.environ.setdefault("ARCHON_SERVER_PORT", "8181")
os.environ.setdefault("ARCHON_MCP_PORT", "8051")
os.environ.setdefault("ARCHON_AGENTS_PORT", "8052")
os.environ.setdefault("ARCHON_ORIGIN", f"http://localhost:{os.environ.get('ARCHON_SERVER_PORT','8181')}")


async def main():
    client = MCPClient()
    print(f"MCP base URL: {client.mcp_url}")
    print(f"Origin header: {client.origin}")

    # List tools
    try:
        tools = await client.list_tools()
        print("tools/list ->", json.dumps(tools)[:2000])
    except Exception as e:
        print("tools/list error:", type(e).__name__, str(e))

    # Health check (zero-arg tool)
    try:
        hc = await client.call_tool_raw("health_check", None)
        print("health_check ->", hc)
    except Exception as e:
        print("health_check error:", type(e).__name__, str(e))

    # Session info (zero-arg tool)
    try:
        si = await client.call_tool_raw("session_info", None)
        print("session_info ->", si)
    except Exception as e:
        print("session_info error:", type(e).__name__, str(e))

    # Optional RAG sources (may fail if API service not running)
    try:
        sources = await client.get_available_sources()
        print("get_available_sources ->", sources[:2000])
    except Exception as e:
        print("get_available_sources error:", type(e).__name__, str(e))

    # Glyph: analyze and generate (ASCII)
    try:
        text = "The river flows across the valley."
        ga = await client.call_tool("glyph_analyze", text=text)
        print("glyph_analyze ->", json.dumps(ga)[:1000])
    except Exception as e:
        print("glyph_analyze error:", type(e).__name__, str(e))

    try:
        gg_ascii = await client.call_tool("glyph_generate", text="Hello World", format="ascii")
        print("glyph_generate (ascii) ->", json.dumps(gg_ascii)[:1000])
    except Exception as e:
        print("glyph_generate (ascii) error:", type(e).__name__, str(e))

    # Glyph: generate (SVG) - may require svgwrite; allow failure
    try:
        gg_svg = await client.call_tool("glyph_generate", text="Hello World", format="svg")
        # Avoid printing full SVG
        if isinstance(gg_svg, dict):
            preview = (gg_svg.get("glyph") or "")[:200]
            gg_svg["glyph_preview"] = preview
            gg_svg.pop("glyph", None)
        print("glyph_generate (svg) ->", json.dumps(gg_svg)[:1000])
    except Exception as e:
        print("glyph_generate (svg) error:", type(e).__name__, str(e))

    # GitHub: list org repos (works without token for public orgs)
    try:
        gh_repos = await client.call_tool("github_list_repos", org="github", per_page=5)
        print("github_list_repos(org=github) ->", json.dumps(gh_repos)[:1000])
    except Exception as e:
        print("github_list_repos error:", type(e).__name__, str(e))

    # GitHub: list user private repos (requires GITHUB_TOKEN)
    if os.getenv("GITHUB_TOKEN"):
        try:
            gh_user_private = await client.call_tool("github_list_repos", visibility="private", per_page=5)
            print("github_list_repos(user/private) ->", json.dumps(gh_user_private)[:1000])
        except Exception as e:
            print("github_list_repos(user/private) error:", type(e).__name__, str(e))
    else:
        print("github_list_repos(user/private) skipped: GITHUB_TOKEN not set")

    # Docker: list containers (validates Docker MCP tool)
    try:
        docker_list = await client.call_tool("docker_list_containers", show_all=True)
        print("docker_list_containers ->", json.dumps(docker_list)[:1000])
    except Exception as e:
        print("docker_list_containers error:", type(e).__name__, str(e))

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
