from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Paper(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    abstract: Optional[str] = None
    authors: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[date] = None
    online_date: Optional[date] = None
    doi: Optional[str] = Field(default=None, index=True)
    pmid: Optional[str] = Field(default=None, index=True)
    pmcid: Optional[str] = Field(default=None, index=True)
    source: str = "PubMed"
    url: Optional[str] = None
    normalized_title: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class SearchProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, sa_column_kwargs={"unique": True})
    description: str = ""
    include_keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    exclude_keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    journals: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: str = "pubmed"
    date_window: str = "7d"
    schedule: str = "weekly"
    email_to: str = ""
    enabled: bool = True
    min_relevance_score: float = 5
    llm_enabled: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class SearchRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="searchprofile.id", index=True)
    started_at: datetime = Field(default_factory=now_utc)
    finished_at: Optional[datetime] = None
    status: str = "running"
    message: str = ""
    result_count: int = 0
    new_count: int = 0
    sent_count: int = 0
    llm_analyzed_count: int = 0
    llm_failed_count: int = 0


class PaperSearchResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="searchprofile.id", index=True)
    run_id: Optional[int] = Field(default=None, foreign_key="searchrun.id", index=True)
    relevance_score: float = 0
    matched_keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_new: bool = True
    is_sent: bool = False
    created_at: datetime = Field(default_factory=now_utc)


class PaperLLMAnalysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="searchprofile.id", index=True)
    run_id: Optional[int] = Field(default=None, foreign_key="searchrun.id", index=True)
    backend: str = ""
    model: str = ""
    one_sentence_summary: str = ""
    background: str = ""
    main_finding: str = ""
    method_or_data: str = ""
    relevance_to_profile: str = ""
    limitations_or_caution: str = ""
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    confidence: str = "low"
    raw_response: str = ""
    status: str = "success"
    error_message: str = ""
    created_at: datetime = Field(default_factory=now_utc)


class Digest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="searchprofile.id", index=True)
    run_id: Optional[int] = Field(default=None, foreign_key="searchrun.id", index=True)
    subject: str
    body_html: str
    body_text: str
    email_to: str = ""
    paper_count: int = 0
    sent_at: Optional[datetime] = None
    status: str = "draft"
    error_message: str = ""
