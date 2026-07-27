from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from litmonitor.database import get_session
from litmonitor.models import Paper, PaperLLMAnalysis
from litmonitor.schemas import SearchRequest
from litmonitor.services.dedup import upsert_paper
from litmonitor.services.pubmed import search_pubmed

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("")
def list_papers(
    q: str | None = None,
    journal: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    statement = select(Paper).offset(offset).limit(limit)
    if q:
        statement = statement.where(Paper.title.contains(q))
    if journal:
        statement = statement.where(Paper.journal == journal)
    return session.exec(statement).all()


@router.post("/search")
def search_papers(request: SearchRequest, session: Session = Depends(get_session)):
    papers = search_pubmed(request.query, journals=request.journals, since=request.since)
    saved = [upsert_paper(session, paper) for paper in papers]
    return {"results": saved, "count": len(saved)}


@router.get("/{paper_id}/analysis")
def get_paper_analysis(paper_id: int, session: Session = Depends(get_session)):
    return session.exec(select(PaperLLMAnalysis).where(PaperLLMAnalysis.paper_id == paper_id)).all()


@router.get("/{paper_id}")
def get_paper(paper_id: int, session: Session = Depends(get_session)):
    paper = session.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper
