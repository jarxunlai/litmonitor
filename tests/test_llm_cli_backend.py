import subprocess
from types import SimpleNamespace

from litmonitor.config import Settings
from litmonitor.schemas import PaperCreate, SearchProfileCreate
from litmonitor.services.llm.cli_backend import CLILLMBackend


def test_cli_backend_parses_stdout_json(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout='{"one_sentence_summary":"s","background":"b","main_finding":"m","method_or_data":"d","relevance_to_profile":"r","limitations_or_caution":"l","keywords":["k"],"confidence":"high"}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CLILLMBackend(Settings(llm_cli_command="fake", llm_cli_args="--json"))

    analysis = backend.analyze_paper(
        PaperCreate(title="T", source="PubMed"), SearchProfileCreate(name="P", email_to="a@b.com")
    )

    assert analysis.status == "success"
    assert analysis.one_sentence_summary == "s"


def test_cli_backend_parses_codex_jsonl_agent_message(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="\n".join(
                [
                    '{"type":"thread.started","thread_id":"t"}',
                    '{"type":"item.completed","item":{"type":"agent_message","text":"{\\"one_sentence_summary\\":\\"s\\",\\"background\\":\\"b\\",\\"main_finding\\":\\"m\\",\\"method_or_data\\":\\"d\\",\\"relevance_to_profile\\":\\"r\\",\\"limitations_or_caution\\":\\"l\\",\\"keywords\\":[\\"k\\"],\\"confidence\\":\\"high\\"}"}}',
                    '{"type":"turn.completed"}',
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CLILLMBackend(Settings(llm_cli_command="fake", llm_cli_args="exec --json"))

    analysis = backend.analyze_paper(PaperCreate(title="T", source="PubMed"), None)

    assert analysis.status == "success"
    assert analysis.one_sentence_summary == "s"


def test_cli_backend_timeout_returns_failed(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="fake", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CLILLMBackend(Settings(llm_cli_command="fake", llm_cli_timeout_seconds=1))

    analysis = backend.analyze_paper(PaperCreate(title="T", source="PubMed"), None)

    assert analysis.status == "failed"
    assert "timed out" in analysis.error_message.lower()


def test_cli_backend_missing_command_returns_failed(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = CLILLMBackend(Settings(llm_cli_command="missing"))

    analysis = backend.analyze_paper(PaperCreate(title="T", source="PubMed"), None)

    assert analysis.status == "failed"
    assert "not found" in analysis.error_message.lower()
