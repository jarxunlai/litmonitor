import pytest
from pydantic import ValidationError

from litmonitor.services.llm.schemas import PaperLLMAnalysisResult


def test_llm_result_validates_expected_json():
    result = PaperLLMAnalysisResult(
        one_sentence_summary="A concise summary.",
        background="Background.",
        main_finding="Main finding.",
        method_or_data="Method.",
        relevance_to_profile="Relevant.",
        limitations_or_caution="Limited by abstract.",
        keywords=["PH", "endothelial"],
        confidence="medium",
    )

    assert result.confidence == "medium"


def test_llm_result_requires_fields():
    with pytest.raises(ValidationError):
        PaperLLMAnalysisResult(one_sentence_summary="Only one field")
