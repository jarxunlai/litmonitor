from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from litmonitor.database import engine
from litmonitor.models import Digest, Paper, SearchProfile, SearchRun
from litmonitor.services.dedup import upsert_paper
from litmonitor.services.pubmed import search_pubmed
from litmonitor.services.runner import run_profile

router = APIRouter()
templates = Jinja2Templates(directory="src/litmonitor/web/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    with Session(engine) as session:
        profiles = session.exec(select(SearchProfile).limit(20)).all()
        papers = session.exec(select(Paper).order_by(Paper.id.desc()).limit(10)).all()
    return templates.TemplateResponse(
        request, "base.html", {"profiles": profiles, "papers": papers}
    )


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request):
    return templates.TemplateResponse(request, "search.html", {"papers": []})


@router.post("/search", response_class=HTMLResponse)
def search_submit(
    request: Request, query: str = Form(...), journal: str = Form(""), since: str = Form("30d")
):
    journals = [item.strip() for item in journal.split(",") if item.strip()]
    papers = search_pubmed(query, journals=journals, since=since)
    with Session(engine) as session:
        saved = [upsert_paper(session, paper) for paper in papers]
    return templates.TemplateResponse(request, "search.html", {"papers": saved, "query": query})


@router.get("/profiles", response_class=HTMLResponse)
def profiles_page(request: Request):
    with Session(engine) as session:
        profiles = session.exec(select(SearchProfile)).all()
    return templates.TemplateResponse(request, "profiles.html", {"profiles": profiles})


@router.post("/profiles")
def profiles_create(
    name: str = Form(...),
    include_keywords: str = Form(...),
    exclude_keywords: str = Form(""),
    journals: str = Form(""),
    email_to: str = Form(...),
    date_window: str = Form("7d"),
):
    profile = SearchProfile(
        name=name,
        include_keywords=[x.strip() for x in include_keywords.split(",") if x.strip()],
        exclude_keywords=[x.strip() for x in exclude_keywords.split(",") if x.strip()],
        journals=[x.strip() for x in journals.split(",") if x.strip()],
        email_to=email_to,
        date_window=date_window,
    )
    with Session(engine) as session:
        session.add(profile)
        session.commit()
    return RedirectResponse("/profiles", status_code=303)


@router.post("/profiles/{profile_id}/run")
def profiles_run(profile_id: int):
    with Session(engine) as session:
        profile = session.get(SearchProfile, profile_id)
        if profile:
            run_profile(session, profile)
    return RedirectResponse("/profiles", status_code=303)


@router.get("/papers", response_class=HTMLResponse)
def papers_page(request: Request, q: str = "", journal: str = ""):
    with Session(engine) as session:
        statement = select(Paper).order_by(Paper.id.desc())
        if q:
            statement = statement.where(Paper.title.contains(q))
        if journal:
            statement = statement.where(Paper.journal == journal)
        papers = session.exec(statement.limit(100)).all()
    return templates.TemplateResponse(
        request, "papers.html", {"papers": papers, "q": q, "journal": journal}
    )


@router.get("/digests", response_class=HTMLResponse)
def digests_page(request: Request):
    with Session(engine) as session:
        digests = session.exec(select(Digest).order_by(Digest.id.desc())).all()
    return templates.TemplateResponse(
        request, "digest_preview.html", {"digests": digests, "digest": None}
    )


@router.get("/digests/preview/{run_id}", response_class=HTMLResponse)
def digest_preview_page(request: Request, run_id: int):
    with Session(engine) as session:
        digest = session.exec(
            select(Digest).where(Digest.run_id == run_id).order_by(Digest.id.desc())
        ).first()
        run = session.get(SearchRun, run_id)
    return templates.TemplateResponse(
        request, "digest_preview.html", {"digest": digest, "run": run, "digests": []}
    )
