#!/usr/bin/env python3
"""CLI entry point for the Trend-to-Product pipeline."""

import patches  # noqa: F401 — must import before any crewai usage
import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

import yaml
from crewai import Crew, Process, Task
from dotenv import load_dotenv

from agents.architect import make_architect_agent
from agents.builder import _write_project_files, make_builder_agent
from agents.critic import make_critic_agent
from agents.scout import make_scout_agent
from storage.recorder import finish_run, start_run

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "pipeline.log"),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"


def _parse_json_file(path: Path):
    """Read an output file and extract JSON even when wrapped in markdown fences."""
    text = path.read_text().strip()
    if not text:
        return None
    # Try raw JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract from ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Last resort: find first [ or { and parse from there
    for start_char, end_char in (("[", "]"), ("{", "}")):
        idx = text.find(start_char)
        if idx != -1:
            try:
                return json.loads(text[idx:text.rfind(end_char) + 1])
            except json.JSONDecodeError:
                continue
    return None


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f)


def _build_crew(topic: str | None, dry_run: bool) -> tuple[Crew, list[Task]]:
    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")

    topic_hint = f"Pay special attention to trends related to: {topic}." if topic else ""

    scout = make_scout_agent(agents_cfg["scout"])
    critic = make_critic_agent(agents_cfg["critic"])
    architect = make_architect_agent(agents_cfg["architect"])
    builder = make_builder_agent(agents_cfg["builder"])

    scout_task = Task(
        description=tasks_cfg["scout_task"]["description"].format(topic_hint=topic_hint),
        expected_output=tasks_cfg["scout_task"]["expected_output"],
        agent=scout,
        output_file=tasks_cfg["scout_task"]["output_file"],
    )

    if dry_run:
        crew = Crew(agents=[scout], tasks=[scout_task], process=Process.sequential, verbose=True)
        return crew, [scout_task]

    critic_task = Task(
        description=tasks_cfg["critic_task"]["description"],
        expected_output=tasks_cfg["critic_task"]["expected_output"],
        agent=critic,
        context=[scout_task],
        output_file=tasks_cfg["critic_task"]["output_file"],
    )

    architect_task = Task(
        description=tasks_cfg["architect_task"]["description"],
        expected_output=tasks_cfg["architect_task"]["expected_output"],
        agent=architect,
        context=[critic_task],
        output_file=tasks_cfg["architect_task"]["output_file"],
    )

    builder_task = Task(
        description=tasks_cfg["builder_task"]["description"],
        expected_output=tasks_cfg["builder_task"]["expected_output"],
        agent=builder,
        context=[architect_task],
        callback=_write_project_files,
    )

    crew = Crew(
        agents=[scout, critic, architect, builder],
        tasks=[scout_task, critic_task, architect_task, builder_task],
        process=Process.sequential,
        verbose=True,
    )
    return crew, [scout_task, critic_task, architect_task, builder_task]


def _check_api_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Error: ANTHROPIC_API_KEY is not set. Add it to .env or your environment.")


def _run_pipeline(topic: str | None, dry_run: bool) -> None:
    _check_api_key()
    Path("logs").mkdir(exist_ok=True)
    Path("storage").mkdir(exist_ok=True)

    run_id = start_run(topic=topic)
    logger.info("Starting run #%d (dry_run=%s, topic=%s)", run_id, dry_run, topic)

    try:
        crew, tasks = _build_crew(topic=topic, dry_run=dry_run)
        crew.kickoff()

        if dry_run:
            trend_file = Path("storage/trend_list.json")
            if trend_file.exists():
                trends = _parse_json_file(trend_file)
                if trends:
                    print("\n=== TREND LIST ===")
                    for i, t in enumerate(trends, 1):
                        print(f"{i}. {t.get('title', '?')} — {t.get('why_trending', '')}")
                else:
                    print("Scout finished but produced no parseable JSON.")
                    print(trend_file.read_text()[:500])
            else:
                print("No trend_list.json produced yet.")
        else:
            winning_file = Path("storage/winning_idea.json")
            if winning_file.exists():
                idea = _parse_json_file(winning_file)
                if not idea:
                    logger.error("Critic rejected all ideas — no winner selected.")
                    finish_run(run_id, status="error", error="Critic rejected all ideas")
                    sys.exit("Pipeline ended: Critic rejected all ideas.")
                print(f"\n=== WINNING IDEA: {idea.get('trend_title', '?')} ===")
            print("\nPipeline complete. Check output/ for the generated project.")

        finish_run(run_id, status="success")

    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        finish_run(run_id, status="error", error=str(exc))
        sys.exit(f"Pipeline error: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trend-to-Product autonomous pipeline")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true", help="Run the full 4-agent pipeline")
    mode.add_argument("--dry-run", action="store_true", help="Scout only – print trends and exit")
    parser.add_argument("--topic", type=str, default=None, help="Optional topic focus for the Scout")

    args = parser.parse_args()
    _run_pipeline(topic=args.topic, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
