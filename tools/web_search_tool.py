# tools/web_search_tool.py
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

class WebSearchTool:
    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        if not self.api_key:
            raise ValueError("SERPAPI_KEY is required. Set it in .env or environment variables.")
        self.timeout = timeout

    def search(self, query: str) -> str:
        try:
            logger.info(f"Performing web search: {query}")
            
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google"
            }
            
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                # Extract key information from search results
                results = []
                if "organic_results" in data:
                    for result in data["organic_results"][:5]:  # Limit to top 5 results
                        title = result.get("title", "")
                        link = result.get("link", "")
                        snippet = result.get("snippet", "")
                        results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n")
                
                return "\n".join(results)
            else:
                return f"Error: Search failed with status code {response.status_code}"
                
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return f"Error performing web search: {str(e)}"
