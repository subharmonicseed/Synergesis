"""
Docker MCP Module

Exposes Docker SDK functionality as MCP tools for local container management.
"""

import logging

import docker
from docker.errors import DockerException

from mcp.server.fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)

def register_docker_tools(mcp: FastMCP):
    """Register all Docker-related MCP tools."""

    try:
        client = docker.from_env()
        client.ping()  # Check connection
        logger.info("[SUCCESS] Docker client connected successfully.")
    except DockerException as e:
        logger.error(f"[FAILURE] Failed to connect to Docker daemon: {e}")
        logger.error("  Docker tools will not be available.")
        return

    @mcp.tool(name="docker.list_containers")
    def list_containers(ctx: Context, show_all: bool = True) -> dict:
        """
        List all Docker containers.

        Args:
            all (bool): Show all containers (default True), or only running ones.

        Returns:
            A dictionary containing a list of containers or an error message.
        """
        try:
            containers = client.containers.list(all=show_all)
            container_list = [
                {
                    "id": c.short_id,
                    "name": c.name,
                    "image": str(c.image),
                    "status": c.status,
                }
                for c in containers
            ]
            return {"containers": container_list}
        except DockerException as e:
            logger.error(f"Error listing containers: {e}")
            return {"error": str(e)}

    logger.info("[SUCCESS] Docker tools registered.")
