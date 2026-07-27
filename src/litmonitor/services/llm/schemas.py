from typing import Literal

from pydantic import BaseModel


class PaperLLMAnalysisResult(BaseModel):
    one_sentence_summary: str
    background: str
    main_finding: str
    method_or_data: str
    relevance_to_profile: str
    limitations_or_caution: str
    keywords: list[str]
    confidence: Literal["low", "medium", "high"]


class PaperLLMAnalysisCreate(PaperLLMAnalysisResult):
    backend: str
    model: str = ""
    raw_response: str = ""
    status: Literal["success", "failed"] = "success"
    error_message: str = ""


def failed_analysis(
    backend: str, model: str, message: str, raw_response: str = ""
) -> PaperLLMAnalysisCreate:
    return PaperLLMAnalysisCreate(
        backend=backend,
        model=model,
        one_sentence_summary="",
        background="",
        main_finding="",
        method_or_data="",
        relevance_to_profile="",
        limitations_or_caution=message,
        keywords=[],
        confidence="low",
        raw_response=raw_response,
        status="failed",
        error_message=message,
    )
