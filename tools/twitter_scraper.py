import json
import logging
import subprocess
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TwitterInput(BaseModel):
    query: str = Field(default="#buildinpublic OR #indiehacker", description="Twitter search query")
    limit: int = Field(default=20, description="Max number of tweets")


def _fetch_via_module(query: str, limit: int) -> list[dict]:
    import snscrape.modules.twitter as sntwitter

    results = []
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
        if i >= limit:
            break
        results.append({
            "source": "twitter",
            "title": tweet.rawContent[:280],
            "url": tweet.url,
            "score": tweet.likeCount,
            "retweets": tweet.retweetCount,
        })
    return results


def _fetch_via_subprocess(query: str, limit: int) -> list[dict]:
    cmd = [
        "python", "-m", "snscrape",
        "--jsonl", f"--max-results={limit}",
        "twitter-search", query,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    results = []
    for line in proc.stdout.splitlines():
        try:
            data = json.loads(line)
            results.append({
                "source": "twitter",
                "title": data.get("content", "")[:280],
                "url": data.get("url", ""),
                "score": data.get("likeCount", 0),
                "retweets": data.get("retweetCount", 0),
            })
        except Exception:
            continue
    return results


class TwitterTool(BaseTool):
    name: str = "Twitter Trends"
    description: str = "Searches Twitter for trending tech/startup content via snscrape."
    args_schema: Type[BaseModel] = TwitterInput

    def _run(self, query: str = "#buildinpublic OR #indiehacker", limit: int = 20) -> str:
        try:
            results = _fetch_via_module(query, limit)
            return json.dumps(results)
        except ImportError:
            logger.warning("snscrape module import failed, trying subprocess fallback")
        except Exception as exc:
            logger.warning("snscrape module failed: %s", exc)

        try:
            results = _fetch_via_subprocess(query, limit)
            return json.dumps(results)
        except Exception as exc:
            logger.warning("Twitter subprocess fallback failed: %s", exc)
            return json.dumps([{"error": str(exc), "source": "twitter"}])
