import json
import logging
from typing import Any, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HNInput(BaseModel):
    limit: int = Field(default=10, description="Number of HN stories to fetch")


class HackerNewsTool(BaseTool):
    name: str = "HackerNews Trends"
    description: str = "Fetches top stories from Hacker News via the Algolia API. No API key required."
    args_schema: Type[BaseModel] = HNInput

    def _run(self, limit: int = 10) -> str:
        try:
            url = "https://hn.algolia.com/api/v1/search"
            params = {
                "tags": "front_page",
                "hitsPerPage": limit,
            }
            resp = httpx.get(url, params=params, timeout=10)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            results = [
                {
                    "source": "hackernews",
                    "title": h.get("title", ""),
                    "url": h.get("url", ""),
                    "score": h.get("points", 0),
                    "comments": h.get("num_comments", 0),
                }
                for h in hits
            ]
            return json.dumps(results)
        except Exception as exc:
            logger.warning("HN scraper failed: %s", exc)
            return json.dumps([{"error": str(exc), "source": "hackernews"}])
