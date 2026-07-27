from datetime import datetime, timezone

from sqlmodel import Session, select

from litmonitor.config import Settings, get_settings
from litmonitor.models import Paper, PaperLLMAnalysis, PaperSearchResult, SearchProfile, SearchRun
from litmonitor.schemas import PaperCreate, SearchProfileCreate
from litmonitor.services.dedup import upsert_paper
from litmonitor.services.digest import save_digest
from litmonitor.services.llm.factory import get_llm_backend
from litmonitor.services.mailer import send_digest_email
from litmonitor.services.pubmed import search_pubmed
from litmonitor.services.ranking import score_paper


def profile_to_schema(profile: SearchProfile) -> SearchProfileCreate:
    return SearchProfileCreate(
        name=profile.name,
        description=profile.description,
        include_keywords=profile.include_keywords,
        exclude_keywords=profile.exclude_keywords,
        journals=profile.journals,
        source=profile.source,
        date_window=profile.date_window,
        schedule=profile.schedule,
        email_to=profile.email_to,
        enabled=profile.enabled,
        min_relevance_score=profile.min_relevance_score,
        llm_enabled=profile.llm_enabled,
    )


def paper_to_schema(paper: Paper) -> PaperCreate:
    return PaperCreate(
        title=paper.title,
        abstract=paper.abstract,
        authors=paper.authors,
        journal=paper.journal,
        publication_date=paper.publication_date,
        online_date=paper.online_date,
        doi=paper.doi,
        pmid=paper.pmid,
        pmcid=paper.pmcid,
        source=paper.source,
        url=paper.url,
    )


def run_profile(
    session: Session,
    profile: SearchProfile,
    use_llm: bool = False,
    send_email: bool = False,
    settings: Settings | None = None,
) -> SearchRun:
    settings = settings or get_settings()
    run = SearchRun(profile_id=profile.id)
    session.add(run)
    session.commit()
    session.refresh(run)
    profile_schema = profile_to_schema(profile)
    try:
        papers = search_pubmed(
            " ".join(profile.include_keywords),
            journals=profile.journals,
            since=profile.date_window,
            limit=100,
        )
        run.result_count = len(papers)
        for candidate in papers:
            paper = upsert_paper(session, candidate)
            was_new = is_new_to_profile(session, profile, paper)
            score = score_paper(candidate, profile_schema)
            result = PaperSearchResult(
                paper_id=paper.id,
                profile_id=profile.id,
                run_id=run.id,
                relevance_score=score.relevance_score,
                matched_keywords=score.matched_keywords,
                is_new=was_new,
            )
            session.add(result)
            if was_new:
                run.new_count += 1
        session.commit()

        if use_llm or profile.llm_enabled or settings.llm_enabled:
            backend = get_llm_backend(settings=settings)
            if backend:
                rows = session.exec(
                    select(PaperSearchResult, Paper)
                    .join(Paper, Paper.id == PaperSearchResult.paper_id)
                    .where(PaperSearchResult.run_id == run.id)
                    .where(PaperSearchResult.is_new.is_(True))
                    .where(PaperSearchResult.relevance_score >= profile.min_relevance_score)
                    .order_by(PaperSearchResult.relevance_score.desc())
                    .limit(settings.llm_max_papers_per_run)
                ).all()
                for result, paper in rows:
                    analysis = backend.analyze_paper(paper_to_schema(paper), profile_schema)
                    session.add(
                        PaperLLMAnalysis(
                            paper_id=paper.id,
                            profile_id=profile.id,
                            run_id=run.id,
                            **analysis.model_dump(),
                        )
                    )
                    if analysis.status == "success":
                        run.llm_analyzed_count += 1
                    else:
                        run.llm_failed_count += 1
                session.commit()

        digest = save_digest(session, profile, run)
        if send_email:
            digest = send_digest_email(session, digest, settings)
            if digest.status == "sent":
                sent_query = (
                    select(PaperSearchResult)
                    .where(PaperSearchResult.run_id == run.id)
                    .where(PaperSearchResult.is_new.is_(True))
                    .where(PaperSearchResult.relevance_score >= profile.min_relevance_score)
                    .order_by(PaperSearchResult.relevance_score.desc())
                )
                if settings.digest_max_papers_per_run > 0:
                    sent_query = sent_query.limit(settings.digest_max_papers_per_run)
                sent_results = session.exec(sent_query).all()
                for result in sent_results:
                    result.is_sent = True
                run.sent_count = len(sent_results)
                session.commit()

        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    except Exception as exc:
        run.status = "failed"
        run.message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def is_new_to_profile(session: Session, profile: SearchProfile, paper: Paper) -> bool:
    previous = session.exec(
        select(PaperSearchResult)
        .where(PaperSearchResult.profile_id == profile.id)
        .where(PaperSearchResult.paper_id == paper.id)
    ).first()
    return previous is None
