import json
import logging
import os
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RedditInput(BaseModel):
    subreddits: str = Field(
        default="startups,SideProject,programming,MachineLearning",
        description="Comma-separated list of subreddits to scrape",
    )
    limit: int = Field(default=10, description="Posts per subreddit")


class RedditTool(BaseTool):
    name: str = "Reddit Trends"
    description: str = "Fetches hot posts from tech/startup subreddits via PRAW."
    args_schema: Type[BaseModel] = RedditInput

    def _run(self, subreddits: str = "startups,SideProject,programming,MachineLearning", limit: int = 10) -> str:
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "trend_to_product/0.1")

        if not client_id or not client_secret:
            return json.dumps([{"error": "REDDIT_CLIENT_ID/SECRET not set", "source": "reddit"}])

        try:
            import praw

            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            results = []
            for sub in subreddits.split(","):
                sub = sub.strip()
                try:
                    for post in reddit.subreddit(sub).hot(limit=limit):
                        results.append({
                            "source": f"reddit/r/{sub}",
                            "title": post.title,
                            "url": post.url,
                            "score": post.score,
                            "comments": post.num_comments,
                        })
                except Exception as sub_exc:
                    logger.warning("Reddit r/%s failed: %s", sub, sub_exc)
            return json.dumps(results)
        except Exception as exc:
            logger.warning("Reddit scraper failed: %s", exc)
            return json.dumps([{"error": str(exc), "source": "reddit"}])
