from litmonitor.config import Settings
from litmonitor.schemas import PaperCreate
from litmonitor.services.llm.base import LLMBackend
from litmonitor.services.llm.factory import FallbackLLMBackend, get_llm_backend
from litmonitor.services.llm.schemas import PaperLLMAnalysisCreate, failed_analysis


class FailingBackend(LLMBackend):
    def analyze_paper(self, paper, profile):
        return failed_analysis("primary", "primary-model", "rate limited")


class PassingBackend(LLMBackend):
    def analyze_paper(self, paper, profile):
        return PaperLLMAnalysisCreate(
            one_sentence_summary="fallback summary",
            background="b",
            main_finding="m",
            method_or_data="d",
            relevance_to_profile="r",
            limitations_or_caution="l",
            keywords=["k"],
            confidence="medium",
            backend="cli",
            model="codex",
        )


def test_fallback_backend_uses_secondary_when_primary_fails():
    backend = FallbackLLMBackend(FailingBackend(), PassingBackend())

    analysis = backend.analyze_paper(PaperCreate(title="T", source="PubMed"), None)

    assert analysis.status == "success"
    assert analysis.one_sentence_summary == "fallback summary"
    assert analysis.backend == "cli"


def test_factory_wraps_openai_backend_with_cli_fallback():
    backend = get_llm_backend(
        settings=Settings(
            llm_backend="openai-compatible",
            llm_fallback_backend="cli",
        )
    )

    assert isinstance(backend, FallbackLLMBackend)
