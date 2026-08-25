from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.env_loader import load_app_environment

load_app_environment(PROJECT_ROOT)

mcp = FastMCP("SearchServer")

TAVILY_API_BASE = "https://api.tavily.com/search"
API_KEY = os.getenv("TAVILY_API_KEY", "")
USER_AGENT = "search-agent/1.0"


async def fetch_search(query: str, max_results: int = 5) -> dict[str, Any]:
    params = {
        "api_key": API_KEY,
        "query": query,
        "max_results": max_results,
    }
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            TAVILY_API_BASE,
            json=params,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def search(query: str, max_results: int = 5) -> dict[str, Any]:
    """
    Run a web search using Tavily.
    :param query: search query string
    :param max_results: number of results to return
    """
    if not API_KEY:
        return {"error": "Missing TAVILY_API_KEY"}
    try:
        return await fetch_search(query, max_results=max_results)
    except httpx.HTTPStatusError as exc:
        return {"error": f"HTTP error: {exc.response.status_code}"}
    except Exception as exc:
        return {"error": f"Request failed: {exc}"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
