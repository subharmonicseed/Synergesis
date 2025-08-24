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

    def _serialize_container(c):
        try:
            image_str = None
            # Try tags or image id from the Image object
            try:
                img = getattr(c, "image", None)
                if img is not None:
                    tags = getattr(img, "tags", None)
                    if tags:
                        image_str = tags[0]
                    else:
                        image_id = getattr(img, "id", None)
                        if image_id:
                            image_str = str(image_id)
            except Exception:
                image_str = None

            # Fallback to container attrs (inspect) if needed
            if not image_str:
                try:
                    attrs = getattr(c, "attrs", {}) or {}
                    image_id_full = attrs.get("Image")
                    if image_id_full:
                        if isinstance(image_id_full, str) and image_id_full.startswith("sha256:"):
                            image_str = image_id_full[:19]  # e.g., 'sha256:abcdef123456'
                        else:
                            image_str = str(image_id_full)
                except Exception:
                    pass

            return {
                "id": getattr(c, "short_id", None) or getattr(c, "id", None),
                "name": getattr(c, "name", None),
                "image": image_str or "<unknown>",
                "status": getattr(c, "status", None),
            }
        except Exception as e:
            logger.exception("Failed to serialize container: %s", e)
            return {
                "id": getattr(c, "short_id", None) or getattr(c, "id", None),
                "name": getattr(c, "name", None),
                "image": "<error>",
                "status": getattr(c, "status", None),
                "serialization_error": str(e),
            }

    @mcp.tool(name="docker_list_containers")
    def list_containers(show_all: bool = True, ctx: Context | None = None) -> dict:
        """
        List all Docker containers.

        Args:
            show_all (bool): Show all containers (default True), or only running ones.

        Returns:
            A dictionary containing a list of containers or an error message.
        """
        try:
            containers = client.containers.list(all=show_all)
            container_list = []
            for c in containers:
                try:
                    container_list.append(_serialize_container(c))
                except Exception as ce:
                    logger.exception("Error serializing container %s: %s", getattr(c, "id", "?"), ce)
            return {"containers": container_list}
        except DockerException as e:
            logger.error(f"Error listing containers: {e}")
            return {"error": str(e)}

    logger.info("[SUCCESS] Docker tools registered.")
