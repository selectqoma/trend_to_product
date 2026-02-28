#!/usr/bin/env python3
"""CLI entry point for the Trend-to-Product pipeline."""

import patches  # noqa: F401 — must import before any crewai usage
import argparse
import json
import logging
import os
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
STORAGE = Path("storage")


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f)


def _parse_json(text: str):
    """Extract the first valid JSON object or array from arbitrary text."""
    import json as _json
    decoder = _json.JSONDecoder()
    for start_char in ("{", "["):
        idx = text.find(start_char)
        if idx == -1:
            continue
        try:
            obj, _ = decoder.raw_decode(text, idx)
            return obj
        except _json.JSONDecodeError:
            continue
    return None


def _parse_json_file(path: Path):
    text = path.read_text().strip()
    return _parse_json(text) if text else None


def _check_api_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Error: ANTHROPIC_API_KEY is not set. Add it to .env or your environment.")


def _run_crew(*args, **kwargs) -> None:
    Crew(*args, **kwargs, process=Process.sequential, verbose=True).kickoff()


# ── pipeline stages ───────────────────────────────────────────────────────────

def _stage_scout(topic: str | None, agents_cfg: dict, tasks_cfg: dict) -> None:
    topic_hint = f"Pay special attention to trends related to: {topic}." if topic else ""
    scout = make_scout_agent(agents_cfg["scout"])
    task = Task(
        description=tasks_cfg["scout_task"]["description"].format(topic_hint=topic_hint),
        expected_output=tasks_cfg["scout_task"]["expected_output"],
        agent=scout,
        output_file=tasks_cfg["scout_task"]["output_file"],
    )
    _run_crew(agents=[scout], tasks=[task])


def _stage_critic(agents_cfg: dict, tasks_cfg: dict) -> list[dict]:
    critic = make_critic_agent(agents_cfg["critic"])
    task = Task(
        description=tasks_cfg["critic_task"]["description"],
        expected_output=tasks_cfg["critic_task"]["expected_output"],
        agent=critic,
        output_file=tasks_cfg["critic_task"]["output_file"],
    )
    _run_crew(agents=[critic], tasks=[task])

    raw = _parse_json_file(STORAGE / "critic_top3.json")
    if not raw:
        sys.exit("Critic produced no parseable output.")
    top3 = raw.get("top3") if isinstance(raw, dict) else raw
    if not top3:
        sys.exit("Critic output missing 'top3' list.")
    return top3


def _prompt_idea_choice(top3: list[dict]) -> dict:
    SEP = "─" * 60
    print(f"\n{SEP}")
    print("  CRITIC'S TOP 3 — you pick which one to build")
    print(SEP)
    for idea in top3:
        print(f"\n  [{idea['rank']}]  {idea['trend_title']}")
        print(f"       {idea['one_liner']}")
        print(f"       Feasibility: {idea['feasibility_score']}/10")
        print(f"       Target: {idea['target_user']}")
    print(f"\n{SEP}")
    while True:
        choice = input("  Your choice (1 / 2 / 3): ").strip()
        if choice in ("1", "2", "3"):
            chosen = next(x for x in top3 if x["rank"] == int(choice))
            print(f"\n  → Building: {chosen['trend_title']}\n")
            (STORAGE / "chosen_idea.json").write_text(json.dumps(chosen, indent=2))
            return chosen
        print("  Please enter 1, 2, or 3.")


def _stage_architect(chosen: dict, agents_cfg: dict, tasks_cfg: dict) -> None:
    architect = make_architect_agent(agents_cfg["architect"])
    task = Task(
        description=tasks_cfg["architect_task"]["description"].format(
            chosen_idea=json.dumps(chosen, indent=2)
        ),
        expected_output=tasks_cfg["architect_task"]["expected_output"],
        agent=architect,
        output_file=tasks_cfg["architect_task"]["output_file"],
    )
    _run_crew(agents=[architect], tasks=[task])


def _prompt_design_approval() -> bool:
    design_path = STORAGE / "design_sheet.md"
    text = design_path.read_text() if design_path.exists() else "(design sheet not found)"
    SEP = "─" * 60
    print(f"\n{SEP}")
    print("  ARCHITECT'S DESIGN SHEET (preview)")
    print(SEP)
    preview = text[:2500]
    print(preview)
    if len(text) > 2500:
        print(f"\n  ... ({len(text) - 2500} more chars — full file: storage/design_sheet.md)")
    print(f"\n{SEP}")
    while True:
        choice = input("  Approve and run Builder? [y/n]: ").strip().lower()
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print("  Please enter y or n.")


def _stage_builder(agents_cfg: dict, tasks_cfg: dict) -> None:
    builder = make_builder_agent(agents_cfg["builder"])
    design = (STORAGE / "design_sheet.md").read_text() if (STORAGE / "design_sheet.md").exists() else ""
    task = Task(
        description=tasks_cfg["builder_task"]["description"] + f"\n\nDESIGN SHEET:\n{design}",
        expected_output=tasks_cfg["builder_task"]["expected_output"],
        agent=builder,
        output_file="storage/builder_output.txt",
        callback=_write_project_files,
    )
    _run_crew(agents=[builder], tasks=[task])


# ── entry points ──────────────────────────────────────────────────────────────

def _check_api_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Error: ANTHROPIC_API_KEY is not set. Add it to .env or your environment.")


def _run_pipeline(topic: str | None, dry_run: bool) -> None:
    _check_api_key()
    Path("logs").mkdir(exist_ok=True)
    STORAGE.mkdir(exist_ok=True)

    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")

    if dry_run:
        _stage_scout(topic, agents_cfg, tasks_cfg)
        trend_file = STORAGE / "trend_list.json"
        trends = _parse_json_file(trend_file) if trend_file.exists() else None
        if trends:
            print("\n=== TREND LIST ===")
            for i, t in enumerate(trends, 1):
                print(f"{i}. {t.get('title', '?')} — {t.get('why_trending', '')}")
        else:
            print("Scout finished — see storage/trend_list.json")
        return

    run_id = start_run(topic=topic)
    logger.info("Starting run #%d (topic=%s)", run_id, topic)

    try:
        # Stage 1: Scout
        logger.info("Stage 1/3 — Scout")
        _stage_scout(topic, agents_cfg, tasks_cfg)

        # Stage 2: Critic → user picks
        logger.info("Stage 2/3 — Critic")
        top3 = _stage_critic(agents_cfg, tasks_cfg)
        chosen = _prompt_idea_choice(top3)

        # Stage 3: Architect → user approves
        logger.info("Stage 3a — Architect")
        _stage_architect(chosen, agents_cfg, tasks_cfg)
        if not _prompt_design_approval():
            logger.info("User rejected design — pipeline aborted")
            finish_run(run_id, status="error", error="Aborted by user after design review")
            sys.exit("Aborted. Edit storage/design_sheet.md or re-run to get a new design.")

        # Stage 4: Builder
        logger.info("Stage 3b — Builder")
        _stage_builder(agents_cfg, tasks_cfg)
        print("\nPipeline complete. Check output/ for the generated project.")
        finish_run(run_id, status="success")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        finish_run(run_id, status="error", error="KeyboardInterrupt")
        sys.exit("\nInterrupted.")
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        finish_run(run_id, status="error", error=str(exc))
        sys.exit(f"Pipeline error: {exc}")


def _recover() -> None:
    """Replay storage/builder_output.txt through the file-writing callback."""
    from agents.builder import _extract_manifest
    from crewai.tasks.task_output import TaskOutput

    builder_file = STORAGE / "builder_output.txt"
    if not builder_file.exists():
        sys.exit("No storage/builder_output.txt found. Run the full pipeline first.")

    raw = builder_file.read_text()
    manifest = _extract_manifest(raw)
    if not manifest:
        sys.exit("Could not parse JSON manifest from builder_output.txt.")

    task_output = TaskOutput(description="recover", raw=raw, agent="builder")
    _write_project_files(task_output)
    print(f"Recovered {len(manifest)} files into output/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trend-to-Product autonomous pipeline")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true", help="Run the full interactive pipeline")
    mode.add_argument("--dry-run", action="store_true", help="Scout only – print trends and exit")
    mode.add_argument("--recover", action="store_true", help="Replay builder_output.txt without re-running")
    parser.add_argument("--topic", type=str, default=None, help="Optional topic focus for the Scout")

    args = parser.parse_args()
    if args.recover:
        _recover()
    else:
        _run_pipeline(topic=args.topic, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
