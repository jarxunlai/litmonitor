from litmonitor.config import Settings, get_settings
from litmonitor.services.llm.base import LLMBackend
from litmonitor.services.llm.cli_backend import CLILLMBackend
from litmonitor.services.llm.openai_compatible import OpenAICompatibleBackend
from litmonitor.services.llm.schemas import PaperLLMAnalysisCreate


class FallbackLLMBackend(LLMBackend):
    def __init__(self, primary: LLMBackend, fallback: LLMBackend):
        self.primary = primary
        self.fallback = fallback

    def analyze_paper(self, paper, profile) -> PaperLLMAnalysisCreate:
        analysis = self.primary.analyze_paper(paper, profile)
        if analysis.status == "success":
            return analysis
        fallback_analysis = self.fallback.analyze_paper(paper, profile)
        if fallback_analysis.status == "success":
            fallback_analysis.raw_response = (
                f"Primary backend failed: {analysis.error_message}\n\n"
                f"{fallback_analysis.raw_response}"
            )
        return fallback_analysis


def get_llm_backend(
    backend: str | None = None, settings: Settings | None = None
) -> LLMBackend | None:
    settings = settings or get_settings()
    name = backend or settings.llm_backend
    if name == "none":
        return None
    primary = _build_backend(name, settings)
    fallback_name = settings.llm_fallback_backend
    if backend is None and fallback_name and fallback_name != "none" and fallback_name != name:
        return FallbackLLMBackend(primary, _build_backend(fallback_name, settings))
    return primary


def _build_backend(name: str, settings: Settings) -> LLMBackend:
    if name == "cli":
        return CLILLMBackend(settings)
    if name == "openai-compatible":
        return OpenAICompatibleBackend(settings)
    raise ValueError(f"Unsupported LLM backend: {name}")
