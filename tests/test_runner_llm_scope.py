from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine

from litmonitor.config import Settings
from litmonitor.models import Paper, PaperSearchResult, SearchProfile
from litmonitor.schemas import PaperCreate
from litmonitor.services import runner
from litmonitor.services.llm.schemas import PaperLLMAnalysisCreate


class RecordingBackend:
    def __init__(self):
        self.titles = []

    def analyze_paper(self, paper, profile):
        self.titles.append(paper.title)
        return PaperLLMAnalysisCreate(
            one_sentence_summary=f"summary {paper.title}",
            background="b",
            main_finding="m",
            method_or_data="d",
            relevance_to_profile="r",
            limitations_or_caution="l",
            keywords=["k"],
            confidence="medium",
            backend="test",
            model="test",
        )


def test_run_profile_analyzes_only_digest_eligible_papers(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    backend = RecordingBackend()

    candidates = [
        PaperCreate(title="send me", source="PubMed", doi="10.1/send"),
        PaperCreate(title="below threshold", source="PubMed", doi="10.1/low"),
        PaperCreate(title="already known", source="PubMed", doi="10.1/old"),
    ]

    scores = {
        "send me": 9.0,
        "below threshold": 3.0,
        "already known": 9.0,
    }

    monkeypatch.setattr(runner, "search_pubmed", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(
        runner,
        "score_paper",
        lambda paper, profile: SimpleNamespace(
            relevance_score=scores[paper.title],
            matched_keywords=["pulmonary hypertension"],
        ),
    )
    monkeypatch.setattr(runner, "get_llm_backend", lambda settings: backend)

    with Session(engine) as session:
        profile = SearchProfile(
            name="PH",
            include_keywords=["pulmonary hypertension"],
            email_to="user@example.com",
            min_relevance_score=5,
            llm_enabled=True,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        old_paper = Paper(title="already known", source="PubMed", doi="10.1/old")
        session.add(old_paper)
        session.commit()
        session.refresh(old_paper)
        session.add(
            PaperSearchResult(
                paper_id=old_paper.id,
                profile_id=profile.id,
                relevance_score=9,
                is_new=True,
            )
        )
        session.commit()

        run = runner.run_profile(
            session,
            profile,
            use_llm=True,
            send_email=False,
            settings=Settings(
                llm_enabled=True,
                llm_min_relevance_score=1,
                llm_max_papers_per_run=20,
            ),
        )

    assert run.status == "success"
    assert backend.titles == ["send me"]
    assert run.llm_analyzed_count == 1
    assert run.llm_failed_count == 0
