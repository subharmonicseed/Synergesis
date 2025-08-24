"""
MCP Server for Archon (Microservices Version)

This is the MCP server that uses HTTP calls to other services
instead of importing heavy dependencies directly. This significantly reduces
the container size from 1.66GB to ~150MB.

Modules:
- RAG Module: RAG queries, search, and source management via HTTP
- Project Module: Task and project management via HTTP
- Health & Session: Local operations

Note: Crawling and document upload operations are handled directly by the
API service and frontend, not through MCP tools.
"""

# Standard library imports
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Third-party imports
from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

# First-party (local) imports
from ..server.config.logfire_config import mcp_logger, setup_logfire
from ..server.services.mcp_service_client import get_mcp_service_client
from ..server.services.mcp_session_manager import get_session_manager

# Load environment variables from the project root .env file
# The project root is four levels up from this script's location
project_root = Path(__file__).resolve().parent.parent.parent.parent
dotenv_path = project_root / ".env"
# IMPORTANT: Do not override pre-set env vars (e.g., when launching with custom ports)
load_dotenv(dotenv_path, override=False)

# Configure logging FIRST before any imports that might use it
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/mcp_server.log", mode="a")
        if os.path.exists("/tmp")
        else logging.NullHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Global state
_initialization_event = asyncio.Event()
_shared_context = None
_initialization_complete = False

server_host = "0.0.0.0"  # Listen on all interfaces

# Require ARCHON_MCP_PORT to be set
mcp_port = os.getenv("ARCHON_MCP_PORT")
if not mcp_port:
    raise ValueError(
        "ARCHON_MCP_PORT environment variable is required. "
        "Please set it in your .env file or environment. "
        "Default value: 8061"
    )
server_port = int(mcp_port)


@dataclass
class ArchonContext:
    """
    Context for MCP server.
    No heavy dependencies - just service client for HTTP calls.
    """

    service_client: Any
    health_status: dict = None
    startup_time: float = None

    def __post_init__(self):
        if self.health_status is None:
            self.health_status = {
                "status": "healthy",
                "api_service": False,
                "agents_service": False,
                "last_health_check": None,
            }
        if self.startup_time is None:
            self.startup_time = time.time()


async def perform_health_checks(context: ArchonContext):
    """Perform health checks on dependent services via HTTP."""
    logger.info("--- Starting MCP Health Checks ---")
    try:
        logger.info("Checking Archon API service...")
        api_health = await context.service_client.check_api_service()
        logger.info(f"Archon API service health: {api_health}")
        context.health_status["api_service"] = api_health.get("healthy", False)
    except TimeoutError:
        logger.error("Health check for API service timed out.")
        context.health_status["api_service"] = False
    except Exception as e:
        logger.error(f"Health check for API service failed: {e}")
        context.health_status["api_service"] = False

    try:
        logger.info("Checking Archon Agents service...")
        agents_health = await context.service_client.check_agents_service()
        logger.info(f"Archon Agents service health: {agents_health}")
        context.health_status["agents_service"] = agents_health.get("healthy", False)
    except TimeoutError:
        logger.error("Health check for Agents service timed out.")
        context.health_status["agents_service"] = False
    except Exception as e:
        logger.error(f"Health check for Agents service failed: {e}")
        context.health_status["agents_service"] = False

    # Mark overall status as healthy to allow startup, but log the details
    context.health_status["status"] = "healthy"
    context.health_status["last_health_check"] = datetime.now().isoformat()
    logger.info(f"--- Health check completed --- API: {context.health_status['api_service']}, Agents: {context.health_status['agents_service']}")
    return True


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[ArchonContext]:
    """
    Lifecycle manager for the MCP server.
    Handles initialization and graceful shutdown, including Uvicorn hot-reloads.
    """
    global _initialization_event, _shared_context, _initialization_complete

    # On reload, Uvicorn re-runs lifespan. We need to handle this gracefully.
    if _initialization_complete and _shared_context:
        logger.info("♻️ Reusing existing context for new SSE connection")
        yield _shared_context
        return

    # Reset the event for the current (re)start
    _initialization_event.clear()

    # Use the async event to signal completion
    try:
        logger.info("🚀 Starting MCP server initialization...")

        # Initialize session manager
        logger.info("🔐 Initializing session manager...")
        get_session_manager()
        logger.info("✓ Session manager initialized")

        # Initialize service client for HTTP calls
        logger.info("🌐 Initializing service client...")
        service_client = get_mcp_service_client()
        logger.info("✓ Service client initialized")

        # Create the shared context for this server instance
        context = ArchonContext(service_client=service_client)

        # Perform initial health checks for dependent services
        await perform_health_checks(context)

        logger.info("✓ MCP server ready")

        # Set global state and signal that initialization is complete
        _shared_context = context
        _initialization_complete = True
        _initialization_event.set()

        # Yield the context to the application
        yield context

    except Exception as e:
        logger.error(f"💥 Critical error during MCP server startup: {e}")
        logger.error(traceback.format_exc())
        # Ensure the event is set even on failure to unblock any waiting requests.
        if not _initialization_event.is_set():
            _initialization_event.set()
        raise  # Re-raise the exception to halt server startup

    finally:
        # This block will run on server shutdown.
        logger.info("🛑 Shutting down MCP server...")
        # Reset global state for a clean restart on reload.
        _initialization_complete = False
        _shared_context = None
        logger.info("✓ MCP server shutdown complete.")


# Initialize the main FastMCP server with fixed configuration
try:
    logger.info("MCP SERVER INITIALIZATION:")
    logger.info("   Server Name: archon-mcp-server")
    logger.info("   Description: MCP server using HTTP calls")

    mcp = FastMCP(
        "archon-mcp-server",
        lifespan=lifespan,
        host=server_host,
        port=server_port,
    )

    # Expose the underlying ASGI app for Uvicorn
    # FastMCP API has changed across versions; try known accessors
    app = None
    tried = []
    try:
        # Preferred in newer implementation
        app = mcp.streamable_http_app()
        tried.append("streamable_http_app()")
    except Exception:
        tried.append("streamable_http_app() failed")

    if app is None:
        # Try common attribute names used in different FastMCP versions
        for attr in ("app", "asgi_app", "get_app", "asgi"):
            try:
                candidate = getattr(mcp, attr)
                # If it's callable, call to get the app
                if callable(candidate):
                    candidate = candidate()
                    tried.append(f"{attr}()")
                else:
                    tried.append(attr)

                # Basic validation: is callable (ASGI app or factory)
                if callable(candidate):
                    app = candidate
                    break
            except Exception:
                tried.append(f"{attr} failed")

    if app is None:
        raise RuntimeError(f"Unable to obtain ASGI app from FastMCP instance. Attempts: {tried}")


    # --- Smarter ASGI Middleware for Session Handling ---
    original_app = app

    async def smart_session_middleware(scope, receive, send):
        # For /mcp POST, wait for initialization to complete
        if scope.get('type') == 'http' and scope.get('path', '').endswith('/mcp'):
            try:
                await asyncio.wait_for(_initialization_event.wait(), timeout=180.0)
            except TimeoutError:
                logger.error("Server initialization timed out after 180s.")
                response = {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Server initialization timeout"}, "id": None}
                body = json.dumps(response).encode('utf-8')
                headers = [ (b'content-type', b'application/json'), (b'content-length', str(len(body)).encode('utf-8')) ]
                await send({'type': 'http.response.start', 'status': 503, 'headers': headers})
                await send({'type': 'http.response.body', 'body': body})
                return
        # Pass-through middleware: do NOT modify request headers or body.
        # The MCP SDK's StreamableHTTPSessionManager creates a new session when the
        # first request has no 'mcp-session-id' header. Injecting one here causes
        # a 400 "No valid session ID provided". We therefore avoid any injection
        # and let the SDK set the response header itself.
        if scope.get('type') != 'http' or scope.get('method') != 'POST':
            await original_app(scope, receive, send)
            return

        # Only apply to the MCP endpoint; otherwise pass through
        path = scope.get('path', '')
        if not path.endswith('/mcp'):
            await original_app(scope, receive, send)
            return

        # For /mcp POST, just pass through untouched
        await original_app(scope, receive, send)

    app = smart_session_middleware
    logger.info("✅ Session middleware: pass-through mode active (no request header injection).")
    # --- End of Middleware ---

    logger.info("FastMCP server instance created successfully using one of: %s", tried)

except Exception as e:
    logger.error(f"Failed to create FastMCP server: {e}")
    logger.error(traceback.format_exc())
    raise




# Health check endpoint
@mcp.tool()
async def health_check(ctx: Context | None = None) -> str:
    """
    Perform a health check on the MCP server and its dependencies.

    Returns:
        JSON string with current health status
    """
    try:
        # Try to get the lifespan context (ctx may be None if not injected)
        context = None
        if ctx is not None and hasattr(ctx, "request_context"):
            context = getattr(ctx.request_context, "lifespan_context", None)

        if context is None:
            # Server starting up
            return json.dumps({
                "success": True,
                "status": "starting",
                "message": "MCP server is initializing...",
                "timestamp": datetime.now().isoformat(),
            })

        # Server is ready - perform health checks
        if hasattr(context, "health_status") and context.health_status:
            await perform_health_checks(context)

            return json.dumps({
                "success": True,
                "health": context.health_status,
                "uptime_seconds": time.time() - context.startup_time,
                "timestamp": datetime.now().isoformat(),
            })
        else:
            return json.dumps({
                "success": True,
                "status": "ready",
                "message": "MCP server is running",
                "timestamp": datetime.now().isoformat(),
            })

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json.dumps({
            "success": False,
            "error": f"Health check failed: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        })


# Session management endpoint
@mcp.tool()
async def session_info(ctx: Context | None = None) -> str:
    """
    Get information about the current session and all active sessions.

    Returns:
        JSON string with session information
    """
    try:
        session_manager = get_session_manager()

        # Build session info
        session_info_data = {
            "active_sessions": session_manager.get_active_session_count(),
            "session_timeout": session_manager.timeout,
        }

        # Add server uptime (ctx may be None if not injected)
        context = None
        if ctx is not None and hasattr(ctx, "request_context"):
            context = getattr(ctx.request_context, "lifespan_context", None)
        if context and hasattr(context, "startup_time"):
            session_info_data["server_uptime_seconds"] = time.time() - context.startup_time

        return json.dumps({
            "success": True,
            "session_management": session_info_data,
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as e:
        logger.error(f"Session info failed: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to get session info: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        })


# Import and register modules
def register_modules():
    """Register all MCP tool modules."""
    logger.info("[+] Registering MCP tool modules...")

    modules_registered = 0

    # Import and register RAG module (HTTP-based version)
    try:
        from .modules.rag_module import register_rag_tools

        register_rag_tools(mcp)
        modules_registered += 1
        logger.info("[OK] RAG module registered (HTTP-based)")
    except ImportError as e:
        logger.warning(f"[WARN] RAG module not available: {e}")
    except Exception as e:
        logger.error(f"[FAIL] Error registering RAG module: {e}")
        logger.error(traceback.format_exc())

    # Import and register Project module - only if Projects are enabled
    projects_enabled = os.getenv("PROJECTS_ENABLED", "true").lower() == "true"
    if projects_enabled:
        try:
            from .modules.project_module import register_project_tools

            register_project_tools(mcp)
            modules_registered += 1
            logger.info("[OK] Project module registered (HTTP-based)")
        except ImportError as e:
            logger.warning(f"[WARN] Project module not available: {e}")
        except Exception as e:
            logger.error(f"[FAIL] Error registering Project module: {e}")
            logger.error(traceback.format_exc())
    else:
        logger.info("⚠ Project module skipped - Projects are disabled")

    # Import and register Docker module
    try:
        from .modules.docker_module import register_docker_tools

        register_docker_tools(mcp)
        modules_registered += 1
        logger.info("[OK] Docker module registered")
    except ImportError as e:
        logger.warning(f"[WARN] Docker module not available: {e}")
    except Exception as e:
        logger.error(f"[FAIL] Error registering Docker module: {e}")
        logger.error(traceback.format_exc())

    # Import and register Glyph module
    try:
        from .modules.glyph_module import register_glyph_tools

        register_glyph_tools(mcp)
        modules_registered += 1
        logger.info("[OK] Glyph module registered")
    except ImportError as e:
        logger.warning(f"[WARN] Glyph module not available: {e}")
    except Exception as e:
        logger.error(f"[FAIL] Error registering Glyph module: {e}")
        logger.error(traceback.format_exc())

    # Import and register GitHub module
    try:
        from .modules.github_module import register_github_tools

        register_github_tools(mcp)
        modules_registered += 1
        logger.info("[OK] GitHub module registered")
    except ImportError as e:
        logger.warning(f"[WARN] GitHub module not available: {e}")
    except Exception as e:
        logger.error(f"[FAIL] Error registering GitHub module: {e}")
        logger.error(traceback.format_exc())

    logger.info(f"[INFO] Total modules registered: {modules_registered}")

    if modules_registered == 0:
        logger.error("💥 No modules were successfully registered!")
        raise RuntimeError("No MCP modules available")


# Register all modules when this file is imported
try:
    register_modules()
except Exception as e:
    logger.error(f"💥 Critical error during module registration: {e}")
    logger.error(traceback.format_exc())
    raise


def main():
    """Main entry point for the MCP server."""
    try:
        # Initialize Logfire first
        setup_logfire(service_name="archon-mcp-server")

        logger.info("[>>] Starting Archon MCP Server")
        logger.info("    Mode: Streamable HTTP")
        logger.info(f"    URL: http://{server_host}:{server_port}/mcp")

        mcp_logger.info("!!! Logfire initialized for MCP server")
        mcp_logger.info(f"!!! Starting MCP server - host={server_host}, port={server_port}")

        # Run Uvicorn with our wrapped ASGI app to ensure middleware is active
        import uvicorn

        uvicorn.run(
            app,  # our wrapped app with session middleware
            host=server_host,
            port=server_port,
            log_level="info",
            reload=True,
        )

    except Exception as e:
        mcp_logger.error(f"💥 Fatal error in main - error={str(e)}, error_type={type(e).__name__}")
        logger.error(f"💥 Fatal error in main: {e}")
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 MCP server stopped by user")
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
