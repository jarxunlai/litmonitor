import json
import time

import httpx
from pydantic import ValidationError

from litmonitor.config import Settings
from litmonitor.schemas import PaperCreate, SearchProfileCreate
from litmonitor.services.llm.base import LLMBackend
from litmonitor.services.llm.json_utils import parse_json_object
from litmonitor.services.llm.prompt import SYSTEM_PROMPT, build_user_prompt
from litmonitor.services.llm.schemas import (
    PaperLLMAnalysisCreate,
    PaperLLMAnalysisResult,
    failed_analysis,
)


class OpenAICompatibleBackend(LLMBackend):
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze_paper(
        self, paper: PaperCreate, profile: SearchProfileCreate | None
    ) -> PaperLLMAnalysisCreate:
        if not self.settings.llm_api_key:
            return failed_analysis(
                "openai-compatible", self.settings.llm_model, "LLM_API_KEY is not configured"
            )
        body = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(paper, profile)},
            ],
            "temperature": self.settings.llm_temperature,
            "stream": self.settings.llm_stream,
        }
        if self.settings.llm_max_tokens > 0:
            body["max_tokens"] = self.settings.llm_max_tokens
        if self.settings.llm_thinking_type:
            body["thinking"] = {"type": self.settings.llm_thinking_type}
        if self.settings.llm_reasoning_effort:
            body["reasoning_effort"] = self.settings.llm_reasoning_effort
        if self.settings.llm_force_json_mode:
            body["response_format"] = {"type": "json_object"}
        last_error = ""
        attempts = max(1, self.settings.llm_retry_attempts)
        for attempt in range(attempts):
            try:
                response = httpx.post(
                    f"{self.settings.llm_api_base.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                    json=body,
                    timeout=self.settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                parsed = parse_json_object(content)
                result = PaperLLMAnalysisResult.model_validate(parsed)
                return PaperLLMAnalysisCreate(
                    **result.model_dump(),
                    backend="openai-compatible",
                    model=self.settings.llm_model,
                    raw_response=json.dumps(payload, ensure_ascii=False),
                )
            except httpx.HTTPStatusError as exc:
                last_error = self._format_http_error(exc)
                if exc.response.status_code != 429 or attempt == attempts - 1:
                    break
                time.sleep(self.settings.llm_retry_backoff_seconds * (attempt + 1))
            except (httpx.HTTPError, KeyError, ValueError, ValidationError) as exc:
                last_error = str(exc)
                break
        return failed_analysis("openai-compatible", self.settings.llm_model, last_error)

    def _format_http_error(self, exc: httpx.HTTPStatusError) -> str:
        message = str(exc)
        body = exc.response.text.strip()
        if body:
            message = f"{message}; response body: {body[:500]}"
        return message
