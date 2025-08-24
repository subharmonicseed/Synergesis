import asyncio
import os
import sys
import json
from pathlib import Path

# Make 'src' importable when running from 'python/scripts'
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.mcp_client import MCPClient

# Ensure required environment variables are set for service discovery
os.environ.setdefault("ARCHON_SERVER_PORT", "8181")
os.environ.setdefault("ARCHON_MCP_PORT", os.environ.get("ARCHON_MCP_PORT", "8062"))
os.environ.setdefault("ARCHON_AGENTS_PORT", "8052")
os.environ.setdefault("ARCHON_ORIGIN", f"http://localhost:{os.environ.get('ARCHON_SERVER_PORT','8181')}")


async def run_check():
    result = {
        "success": False,
        "errors": [],
        "mcp_url": None,
        "tools_ok": False,
        "health_ok": False,
        "health": None,
    }
    client = MCPClient()
    result["mcp_url"] = client.mcp_url

    try:
        tools = await client.list_tools()
        # Basic sanity: required tools exist
        tool_names = {t.get("name") for t in tools.get("tools", [])}
        required = {"health_check", "session_info"}
        result["tools_ok"] = required.issubset(tool_names)
        if not result["tools_ok"]:
            missing = list(required - tool_names)
            result["errors"].append({"type": "MissingTools", "missing": missing})
    except Exception as e:
        result["errors"].append({"type": type(e).__name__, "message": str(e)})

    try:
        hc = await client.call_tool_raw("health_check", None)
        if isinstance(hc, dict) and hc.get("isError") is False:
            # Extract structured content if present
            payload = hc.get("structuredContent") or {}
            res = payload.get("result")
            if isinstance(res, str):
                try:
                    res = json.loads(res)
                except Exception:
                    pass
            result["health"] = res
            # consider ok if success true
            result["health_ok"] = bool(res and res.get("success"))
        else:
            result["errors"].append({"type": "HealthCheckError", "message": str(hc)})
    except Exception as e:
        result["errors"].append({"type": type(e).__name__, "message": str(e)})

    await client.close()

    result["success"] = result["tools_ok"] and result["health_ok"]
    return result


def main():
    try:
        result = asyncio.run(run_check())
    except KeyboardInterrupt:
        print(json.dumps({"success": False, "errors": [{"type": "KeyboardInterrupt"}]}))
        sys.exit(130)
    except Exception as e:
        print(json.dumps({"success": False, "errors": [{"type": type(e).__name__, "message": str(e)}]}))
        sys.exit(2)

    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 2)


if __name__ == "__main__":
    main()
