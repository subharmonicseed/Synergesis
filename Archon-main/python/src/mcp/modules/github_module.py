"""
GitHub Module for Archon MCP Server

Tools exposed:
- github_list_repos: List repositories for the authenticated user or an org
- github_get_file: Get file contents from a repository (optionally decoded)
- github_list_dir: List directory contents in a repository

Authentication:
- Uses environment variable GITHUB_TOKEN (fine-grained or classic) if available.
- No tokens are stored or logged. If absent, public-only endpoints may work but
  private repositories won't be accessible.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _github_headers() -> dict[str, str]:
    """Prepare GitHub API headers, decoding token from env if necessary."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        token_b64 = os.getenv("GITHUB_TOKEN_B64")
        if token_b64:
            try:
                token = base64.b64decode(token_b64).decode("utf-8").strip()
            except Exception as e:
                logger.warning(f"Failed to decode GITHUB_TOKEN_B64: {e}")
                token = None

    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.info("No GITHUB_TOKEN or GITHUB_TOKEN_B64 found. Using unauthenticated requests.")

    return headers


async def _http_get(url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """HTTP GET with graceful 401 fallback.

    If a GITHUB_TOKEN is present but invalid (401), retry once without
    Authorization so public endpoints still work without storing secrets.
    """
    headers = _github_headers()
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=headers) as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 401 and "Authorization" in headers:
            # Retry unauthenticated to allow public access
            try:
                retry_headers = headers.copy()
                retry_headers.pop("Authorization", None)
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=retry_headers) as client2:
                    retry_resp = await client2.get(url, params=params)
                    return retry_resp
            except Exception:
                # Fall through to original response if retry fails
                pass
        return resp


def register_github_tools(mcp: FastMCP) -> None:
    """Register GitHub-related tools with the MCP server."""

    @mcp.tool()
    async def github_list_repos(
        org: str | None = None,
        visibility: str = "all",
        per_page: int = 30,
        page: int = 1,
        ctx: Context | None = None,
    ) -> str:
        """
        List repositories for the authenticated user or a specific org.

        Args:
            org: Organization login to list repos for. If omitted, lists authenticated user's repos.
            visibility: For user repos: one of 'all','public','private'. For org repos, treated as type 'all'.
            per_page: Results per page (max 100)
            page: Page number
        Returns:
            JSON string with { success, repos, count | error }
        """
        try:
            token = os.getenv("GITHUB_TOKEN")
            if not token and not org:
                # /user/repos requires auth to include private repos
                logger.warning("GITHUB_TOKEN not set; listing user repos may be limited to public")
            params = {"per_page": min(max(per_page, 1), 100), "page": max(page, 1)}

            if org:
                # Org repos endpoint
                url = f"{GITHUB_API}/orgs/{org}/repos"
                params["type"] = "all" if visibility not in ("public", "private") else visibility
            else:
                # Authenticated user's repos
                url = f"{GITHUB_API}/user/repos"
                params["visibility"] = visibility if visibility in ("all", "public", "private") else "all"
                params["affiliation"] = "owner,collaborator,organization_member"

            resp = await _http_get(url, params=params)
            if resp.status_code != 200:
                return json.dumps({
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                }, indent=2)

            repos = resp.json()
            # Trim fields to keep responses light
            trimmed = [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "private": r.get("private"),
                    "owner": r.get("owner", {}).get("login"),
                    "default_branch": r.get("default_branch"),
                    "html_url": r.get("html_url"),
                    "description": r.get("description"),
                    "updated_at": r.get("updated_at"),
                }
                for r in repos
            ]
            return json.dumps({"success": True, "repos": trimmed, "count": len(trimmed)}, indent=2)
        except Exception as e:
            logger.error("github_list_repos failed: %s", e)
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def github_get_file(
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
        decode: bool = True,
        ctx: Context | None = None,
    ) -> str:
        """
        Get file content from a repository using the Contents API.

        Args:
            owner: Owner login
            repo: Repository name
            path: File path within the repo
            ref: Branch, tag, or commit SHA
            decode: If true, base64 content is decoded to text (UTF-8 with replacement)
        Returns:
            JSON string with { success, content, encoding, size, sha, download_url | error }
        """
        try:
            url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
            params = {"ref": ref} if ref else None
            resp = await _http_get(url, params=params)
            if resp.status_code != 200:
                return json.dumps({
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                }, indent=2)

            data = resp.json()
            if isinstance(data, list):
                return json.dumps({
                    "success": False,
                    "error": "Requested path is a directory. Use github_list_dir instead.",
                }, indent=2)

            content = data.get("content")
            encoding = data.get("encoding")
            text: str | None = None

            if decode and content and encoding == "base64":
                try:
                    raw = base64.b64decode(content)
                    text = raw.decode("utf-8", errors="replace")
                except Exception as e:
                    logger.warning("Failed to decode base64 content: %s", e)

            result: dict[str, Any] = {
                "success": True,
                "path": data.get("path"),
                "sha": data.get("sha"),
                "size": data.get("size"),
                "download_url": data.get("download_url"),
                "encoding": encoding,
            }
            if decode:
                result["content"] = text if text is not None else content
            else:
                result["content"] = content

            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error("github_get_file failed: %s", e)
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def github_list_dir(
        owner: str,
        repo: str,
        path: str = "",
        ref: str | None = None,
        ctx: Context | None = None,
    ) -> str:
        """
        List directory contents in a repository using the Contents API.

        Args:
            owner: Owner login
            repo: Repository name
            path: Directory path (empty string for repo root)
            ref: Branch, tag, or commit SHA
        Returns:
            JSON string with { success, items, count | error }
        """
        try:
            url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}" if path else f"{GITHUB_API}/repos/{owner}/{repo}/contents"
            params = {"ref": ref} if ref else None
            resp = await _http_get(url, params=params)
            if resp.status_code != 200:
                return json.dumps({
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                }, indent=2)

            data = resp.json()
            if not isinstance(data, list):
                return json.dumps({
                    "success": False,
                    "error": "Requested path is not a directory. Use github_get_file for files.",
                }, indent=2)

            items = [
                {
                    "name": it.get("name"),
                    "path": it.get("path"),
                    "type": it.get("type"),
                    "size": it.get("size"),
                    "sha": it.get("sha"),
                    "download_url": it.get("download_url"),
                    "html_url": it.get("html_url"),
                }
                for it in data
            ]
            return json.dumps({"success": True, "items": items, "count": len(items)}, indent=2)
        except Exception as e:
            logger.error("github_list_dir failed: %s", e)
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    logger.info("[SUCCESS] GitHub tools registered")
