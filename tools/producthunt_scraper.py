import json
import logging
import os
from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

QUERY = """
query TrendingPosts($first: Int!) {
  posts(first: $first, order: VOTES) {
    edges {
      node {
        name
        tagline
        url
        votesCount
        commentsCount
        topics {
          edges { node { name } }
        }
      }
    }
  }
}
"""


class PHInput(BaseModel):
    limit: int = Field(default=10, description="Number of ProductHunt posts to fetch")


class ProductHuntTool(BaseTool):
    name: str = "ProductHunt Trends"
    description: str = "Fetches trending products from ProductHunt via GraphQL v2 API."
    args_schema: Type[BaseModel] = PHInput

    def _run(self, limit: int = 10) -> str:
        api_key = os.getenv("PRODUCTHUNT_API_KEY")
        if not api_key:
            return json.dumps([{"error": "PRODUCTHUNT_API_KEY not set", "source": "producthunt"}])

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {"query": QUERY, "variables": {"first": limit}}
            resp = httpx.post(PH_GRAPHQL_URL, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            edges = resp.json().get("data", {}).get("posts", {}).get("edges", [])
            results = []
            for edge in edges:
                node = edge["node"]
                topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]
                results.append({
                    "source": "producthunt",
                    "title": node["name"],
                    "tagline": node.get("tagline", ""),
                    "url": node.get("url", ""),
                    "votes": node.get("votesCount", 0),
                    "topics": topics,
                })
            return json.dumps(results)
        except Exception as exc:
            logger.warning("ProductHunt scraper failed: %s", exc)
            return json.dumps([{"error": str(exc), "source": "producthunt"}])
