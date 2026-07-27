from types import SimpleNamespace
import time

import httpx

from litmonitor.config import Settings
from litmonitor.schemas import PaperCreate, SearchProfileCreate
from litmonitor.services.llm.openai_compatible import OpenAICompatibleBackend


def test_openai_compatible_backend_sends_zai_thinking_and_max_tokens(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "choices": [
                    {
                        "message": {
                            "content": '{"one_sentence_summary":"s","background":"b","main_finding":"m","method_or_data":"d","relevance_to_profile":"r","limitations_or_caution":"l","keywords":["k"],"confidence":"high"}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    settings = Settings(
        llm_api_base="https://api.z.ai/api/paas/v4",
        llm_api_key="secret",
        llm_model="glm-5.1",
        llm_temperature=1.0,
        llm_max_tokens=4096,
        llm_thinking_type="enabled",
        llm_reasoning_effort="high",
        llm_stream=False,
    )
    backend = OpenAICompatibleBackend(settings)

    analysis = backend.analyze_paper(
        PaperCreate(title="T", source="PubMed"), SearchProfileCreate(name="P", email_to="a@b.com")
    )

    assert analysis.status == "success"
    assert captured["url"] == "https://api.z.ai/api/paas/v4/chat/completions"
    assert captured["json"]["model"] == "glm-5.1"
    assert captured["json"]["temperature"] == 1.0
    assert captured["json"]["max_tokens"] == 4096
    assert captured["json"]["thinking"] == {"type": "enabled"}
    assert captured["json"]["reasoning_effort"] == "high"
    assert captured["json"]["stream"] is False


def test_openai_compatible_backend_retries_429(monkeypatch):
    calls = []
    sleeps = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        if len(calls) == 1:
            return httpx.Response(
                429,
                request=httpx.Request("POST", url),
                text="rate limited",
            )
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "choices": [
                    {
                        "message": {
                            "content": '{"one_sentence_summary":"s","background":"b","main_finding":"m","method_or_data":"d","relevance_to_profile":"r","limitations_or_caution":"l","keywords":["k"],"confidence":"high"}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    backend = OpenAICompatibleBackend(
        Settings(
            llm_api_key="secret",
            llm_retry_attempts=2,
            llm_retry_backoff_seconds=0.5,
        )
    )

    analysis = backend.analyze_paper(PaperCreate(title="T", source="PubMed"), None)

    assert analysis.status == "success"
    assert len(calls) == 2
    assert sleeps == [0.5]
