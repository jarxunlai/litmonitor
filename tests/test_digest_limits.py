from sqlmodel import Session, SQLModel, create_engine, select

from litmonitor.config import Settings, get_settings
from litmonitor.models import Paper, PaperSearchResult, SearchProfile, SearchRun
from litmonitor.schemas import PaperCreate
from litmonitor.services import runner
from litmonitor.services.digest import build_digest


def test_build_digest_respects_max_papers_per_run(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr(
        "litmonitor.config.Settings",
        lambda: Settings(digest_max_papers_per_run=2),
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        profile = SearchProfile(name="Weekly", email_to="user@example.com", min_relevance_score=1)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        run = SearchRun(profile_id=profile.id)
        session.add(run)
        session.commit()
        session.refresh(run)

        for index in range(3):
            paper = Paper(title=f"Paper {index}", source="PubMed", pmid=str(index))
            session.add(paper)
            session.commit()
            session.refresh(paper)
            session.add(
                PaperSearchResult(
                    paper_id=paper.id,
                    profile_id=profile.id,
                    run_id=run.id,
                    relevance_score=10 - index,
                    is_new=True,
                )
            )
        session.commit()

        built = build_digest(session, profile, run)

    get_settings.cache_clear()
    assert built.paper_count == 2
    assert "Paper 0" in built.body_text
    assert "Paper 1" in built.body_text
    assert "Paper 2" not in built.body_text


def test_run_profile_marks_only_sent_digest_limited_papers(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    candidates = [
        PaperCreate(title="Paper 0", source="PubMed", pmid="0"),
        PaperCreate(title="Paper 1", source="PubMed", pmid="1"),
        PaperCreate(title="Paper 2", source="PubMed", pmid="2"),
    ]
    monkeypatch.setattr(runner, "search_pubmed", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(
        runner,
        "score_paper",
        lambda paper, profile: type(
            "Score",
            (),
            {"relevance_score": 10 - int(paper.pmid or 0), "matched_keywords": ["PH"]},
        )(),
    )

    def fake_send_digest_email(session, digest, settings):
        digest.status = "sent"
        session.add(digest)
        session.commit()
        return digest

    monkeypatch.setattr(runner, "send_digest_email", fake_send_digest_email)

    with Session(engine) as session:
        profile = SearchProfile(name="Weekly", email_to="user@example.com", min_relevance_score=1)
        session.add(profile)
        session.commit()
        session.refresh(profile)

        run = runner.run_profile(
            session,
            profile,
            send_email=True,
            settings=Settings(digest_max_papers_per_run=2),
        )
        rows = session.exec(
            select(PaperSearchResult).where(PaperSearchResult.run_id == run.id)
        ).all()

    assert run.sent_count == 2
    assert sum(1 for row in rows if row.is_sent) == 2
