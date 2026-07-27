from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from litmonitor.database import get_session
from litmonitor.models import Paper, PaperLLMAnalysis, PaperSearchResult, SearchProfile
from litmonitor.schemas import LLMAnalyzePaperRequest, LLMAnalyzeRunRequest
from litmonitor.services.llm.factory import get_llm_backend
from litmonitor.services.runner import paper_to_schema, profile_to_schema

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/analyze-paper/{paper_id}")
def analyze_paper(
    paper_id: int, payload: LLMAnalyzePaperRequest, session: Session = Depends(get_session)
):
    paper = session.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    profile = session.get(SearchProfile, payload.profile_id) if payload.profile_id else None
    backend = get_llm_backend(payload.backend)
    if not backend:
        raise HTTPException(status_code=400, detail="LLM backend is disabled")
    result = backend.analyze_paper(
        paper_to_schema(paper), profile_to_schema(profile) if profile else None
    )
    row = PaperLLMAnalysis(
        paper_id=paper.id,
        profile_id=profile.id if profile else None,
        **result.model_dump(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.post("/analyze-run/{run_id}")
def analyze_run(
    run_id: int, payload: LLMAnalyzeRunRequest, session: Session = Depends(get_session)
):
    profile = session.get(SearchProfile, payload.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    backend = get_llm_backend()
    if not backend:
        raise HTTPException(status_code=400, detail="LLM backend is disabled")
    rows = session.exec(
        select(PaperSearchResult, Paper)
        .join(Paper, Paper.id == PaperSearchResult.paper_id)
        .where(PaperSearchResult.run_id == run_id)
        .where(PaperSearchResult.relevance_score >= payload.min_relevance_score)
        .limit(payload.limit)
    ).all()
    created = []
    for result_row, paper in rows:
        result = backend.analyze_paper(paper_to_schema(paper), profile_to_schema(profile))
        row = PaperLLMAnalysis(
            paper_id=paper.id,
            profile_id=profile.id,
            run_id=run_id,
            **result.model_dump(),
        )
        session.add(row)
        created.append(row)
    session.commit()
    return {"count": len(created)}
