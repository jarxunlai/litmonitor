import re
import string
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from litmonitor.models import Paper
from litmonitor.schemas import PaperCreate

GREEK = {"β": "beta", "α": "alpha", "γ": "gamma", "κ": "kappa"}


def normalize_title(title: str) -> str:
    value = title.lower()
    for char, word in GREEK.items():
        value = value.replace(char, f" {word} ")
    value = value.translate(str.maketrans({ch: " " for ch in string.punctuation}))
    return re.sub(r"\s+", " ", value).strip()


def _first_author(authors: str | None) -> str:
    if not authors:
        return ""
    return authors.split(";")[0].strip().lower()


def _year(paper: PaperCreate | Paper) -> int | None:
    return paper.publication_date.year if paper.publication_date else None


def find_existing_paper(session: Session, paper_candidate: PaperCreate) -> Optional[Paper]:
    checks = [
        (Paper.doi, paper_candidate.doi),
        (Paper.pmid, paper_candidate.pmid),
        (Paper.pmcid, paper_candidate.pmcid),
    ]
    for column, value in checks:
        if value:
            existing = session.exec(select(Paper).where(column == value)).first()
            if existing:
                return existing

    normalized = normalize_title(paper_candidate.title)
    existing = session.exec(select(Paper).where(Paper.normalized_title == normalized)).first()
    if existing:
        return existing

    author = _first_author(paper_candidate.authors)
    year = _year(paper_candidate)
    if author and year:
        candidates = session.exec(select(Paper).where(Paper.publication_date.is_not(None))).all()
        for candidate in candidates:
            if (
                normalize_title(candidate.title) == normalized
                and _first_author(candidate.authors) == author
                and _year(candidate) == year
            ):
                return candidate
    return None


def upsert_paper(session: Session, paper_candidate: PaperCreate) -> Paper:
    existing = find_existing_paper(session, paper_candidate)
    if existing:
        return existing
    paper = Paper(
        **paper_candidate.model_dump(),
        normalized_title=normalize_title(paper_candidate.title),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(paper)
    session.commit()
    session.refresh(paper)
    return paper
