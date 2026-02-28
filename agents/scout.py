import os

from crewai import Agent

from tools.github_scraper import GitHubTrendingTool
from tools.hn_scraper import HackerNewsTool
from tools.producthunt_scraper import ProductHuntTool
from tools.reddit_scraper import RedditTool
from tools.twitter_scraper import TwitterTool


def make_scout_agent(config: dict) -> Agent:
    return Agent(
        role=config["role"],
        goal=config["goal"],
        backstory=config["backstory"],
        tools=[
            HackerNewsTool(),
            GitHubTrendingTool(),
            RedditTool(),
            ProductHuntTool(),
            TwitterTool(),
        ],
        llm="anthropic/claude-sonnet-4-6",
        verbose=True,
        max_iter=15,
    )
