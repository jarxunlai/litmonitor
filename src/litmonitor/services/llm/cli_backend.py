import shlex
import subprocess
import json

from pydantic import ValidationError

from litmonitor.config import Settings
from litmonitor.schemas import PaperCreate, SearchProfileCreate
from litmonitor.services.llm.base import LLMBackend
from litmonitor.services.llm.json_utils import parse_json_object
from litmonitor.services.llm.prompt import build_full_prompt
from litmonitor.services.llm.schemas import (
    PaperLLMAnalysisCreate,
    PaperLLMAnalysisResult,
    failed_analysis,
)


class CLILLMBackend(LLMBackend):
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze_paper(
        self, paper: PaperCreate, profile: SearchProfileCreate | None
    ) -> PaperLLMAnalysisCreate:
        command = [self.settings.llm_cli_command, *shlex.split(self.settings.llm_cli_args)]
        try:
            completed = subprocess.run(
                command,
                input=build_full_prompt(paper, profile),
                text=True,
                capture_output=True,
                timeout=self.settings.llm_cli_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return failed_analysis(
                "cli", self.settings.llm_cli_command, "CLI LLM command timed out"
            )
        except FileNotFoundError:
            return failed_analysis(
                "cli", self.settings.llm_cli_command, "CLI LLM command not found"
            )

        if completed.returncode != 0:
            return failed_analysis(
                "cli",
                self.settings.llm_cli_command,
                f"CLI LLM command failed with exit code {completed.returncode}",
                completed.stdout,
            )
        try:
            parsed = parse_json_object(extract_cli_content(completed.stdout))
            result = PaperLLMAnalysisResult.model_validate(parsed)
            return PaperLLMAnalysisCreate(
                **result.model_dump(),
                backend="cli",
                model=self.settings.llm_cli_command,
                raw_response=completed.stdout,
            )
        except (ValueError, ValidationError) as exc:
            return failed_analysis("cli", self.settings.llm_cli_command, str(exc), completed.stdout)


def extract_cli_content(stdout: str) -> str:
    agent_messages = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if text:
                agent_messages.append(text)
    if agent_messages:
        return "\n".join(agent_messages)
    return stdout
