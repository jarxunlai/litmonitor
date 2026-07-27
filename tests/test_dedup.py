from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from litmonitor.models import Paper
from litmonitor.schemas import PaperCreate
from litmonitor.services.dedup import normalize_title, upsert_paper


def test_normalize_title_handles_punctuation_and_greek():
    assert normalize_title("β-Cell α response: PH!") == "beta cell alpha response ph"


def test_upsert_deduplicates_by_doi():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    first = PaperCreate(title="A study", doi="10.1/test", source="PubMed")
    second = PaperCreate(title="Different title", doi="10.1/test", source="PubMed")

    with Session(engine) as session:
        paper1 = upsert_paper(session, first)
        paper2 = upsert_paper(session, second)
        assert paper1.id == paper2.id
        assert len(session.query(Paper).all()) == 1


def test_upsert_deduplicates_by_normalized_title():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    first = PaperCreate(title="Single-cell PH Study.", source="PubMed")
    second = PaperCreate(
        title="single cell ph study", source="PubMed", publication_date=date(2026, 1, 1)
    )

    with Session(engine) as session:
        paper1 = upsert_paper(session, first)
        paper2 = upsert_paper(session, second)
        assert paper1.id == paper2.id
