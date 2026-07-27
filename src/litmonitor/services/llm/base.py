from abc import ABC, abstractmethod

from litmonitor.schemas import PaperCreate, SearchProfileCreate
from litmonitor.services.llm.schemas import PaperLLMAnalysisCreate


class LLMBackend(ABC):
    @abstractmethod
    def analyze_paper(
        self, paper: PaperCreate, profile: SearchProfileCreate | None
    ) -> PaperLLMAnalysisCreate:
        raise NotImplementedError
