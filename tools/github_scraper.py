import json
import logging
from typing import Any, Type

import httpx
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GHInput(BaseModel):
    language: str = Field(default="", description="Filter by programming language (optional)")
    since: str = Field(default="weekly", description="Time window: daily | weekly | monthly")


class GitHubTrendingTool(BaseTool):
    name: str = "GitHub Trending"
    description: str = "Scrapes GitHub Trending page to find popular repositories."
    args_schema: Type[BaseModel] = GHInput

    def _run(self, language: str = "", since: str = "weekly") -> str:
        try:
            url = f"https://github.com/trending/{language}"
            params = {"since": since}
            headers = {"User-Agent": "Mozilla/5.0 (compatible; trend_to_product/0.1)"}
            resp = httpx.get(url, params=params, headers=headers, timeout=15, follow_redirects=True)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            repos = soup.select("article.Box-row")
            results = []
            for repo in repos[:20]:
                name_tag = repo.select_one("h2 a")
                desc_tag = repo.select_one("p")
                stars_tag = repo.select_one("a[href$='/stargazers']")
                if not name_tag:
                    continue
                results.append({
                    "source": "github_trending",
                    "title": name_tag.get_text(strip=True).replace("\n", "").replace(" ", ""),
                    "description": desc_tag.get_text(strip=True) if desc_tag else "",
                    "stars": stars_tag.get_text(strip=True) if stars_tag else "0",
                    "url": "https://github.com" + name_tag["href"],
                })
            return json.dumps(results)
        except Exception as exc:
            logger.warning("GitHub scraper failed: %s", exc)
            return json.dumps([{"error": str(exc), "source": "github_trending"}])
