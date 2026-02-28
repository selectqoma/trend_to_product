import logging
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")


class FileWriterInput(BaseModel):
    project_slug: str = Field(description="Top-level directory name, e.g. 'tradeflow-ai'")
    path: str = Field(description="Relative path inside the project, e.g. 'backend/src/main.ts'")
    content: str = Field(description="Complete file content as a string")


class FileWriterTool(BaseTool):
    name: str = "Write Project File"
    description: str = (
        "Write one file to the output project directory. "
        "Call this once per file. Use the same project_slug for every file."
    )
    args_schema: Type[BaseModel] = FileWriterInput

    def _run(self, project_slug: str, path: str, content: str) -> str:
        try:
            file_path = OUTPUT_DIR / project_slug / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.info("Wrote %s (%d chars)", file_path, len(content))
            return f"OK: wrote {file_path} ({len(content)} chars)"
        except Exception as exc:
            logger.warning("FileWriterTool error: %s", exc)
            return f"ERROR: {exc}"
