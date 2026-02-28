from crewai import Agent


def make_architect_agent(config: dict) -> Agent:
    return Agent(
        role=config["role"],
        goal=config["goal"],
        backstory=config["backstory"],
        llm="anthropic/claude-sonnet-4-6",
        verbose=True,
        max_iter=3,
    )
