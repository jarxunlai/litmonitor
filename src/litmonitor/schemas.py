from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class PaperCreate(BaseModel):
    title: str
    abstract: Optional[str] = None
    authors: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[date] = None
    online_date: Optional[date] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    source: str = "PubMed"
    url: Optional[str] = None


class PaperRead(PaperCreate):
    id: int
    normalized_title: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class SearchRequest(BaseModel):
    query: str
    journals: list[str] = []
    since: str = "30d"
    source: str = "pubmed"


class SearchProfileCreate(BaseModel):
    name: str
    description: str = ""
    include_keywords: list[str] = []
    exclude_keywords: list[str] = []
    journals: list[str] = []
    source: str = "pubmed"
    date_window: str = "7d"
    schedule: str = "weekly"
    email_to: str
    enabled: bool = True
    min_relevance_score: float = 5
    llm_enabled: bool = False


class SearchProfileUpdate(BaseModel):
    description: Optional[str] = None
    include_keywords: Optional[list[str]] = None
    exclude_keywords: Optional[list[str]] = None
    journals: Optional[list[str]] = None
    date_window: Optional[str] = None
    schedule: Optional[str] = None
    email_to: Optional[str] = None
    enabled: Optional[bool] = None
    min_relevance_score: Optional[float] = None
    llm_enabled: Optional[bool] = None


class SearchProfileRead(SearchProfileCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class RankingResult(BaseModel):
    relevance_score: float
    matched_keywords: list[str] = []
    exclusion_reason: Optional[str] = None


class DigestRequest(BaseModel):
    profile_id: int
    run_id: int
    email_to: Optional[str] = None
    use_llm: bool = False


class LLMAnalyzePaperRequest(BaseModel):
    profile_id: Optional[int] = None
    backend: Optional[Literal["openai-compatible", "cli"]] = None


class LLMAnalyzeRunRequest(BaseModel):
    profile_id: int
    limit: int = 20
    min_relevance_score: float = 5
