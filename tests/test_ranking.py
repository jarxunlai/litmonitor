from datetime import date, timedelta

from litmonitor.schemas import PaperCreate, SearchProfileCreate
from litmonitor.services.ranking import score_paper


def test_title_match_scores_higher_than_abstract_match():
    profile = SearchProfileCreate(
        name="PH", include_keywords=["endothelial"], email_to="a@example.com"
    )
    title_hit = PaperCreate(
        title="Endothelial pulmonary hypertension", abstract="", source="PubMed"
    )
    abstract_hit = PaperCreate(
        title="Pulmonary hypertension", abstract="endothelial cell", source="PubMed"
    )

    assert (
        score_paper(title_hit, profile).relevance_score
        > score_paper(abstract_hit, profile).relevance_score
    )


def test_exclude_keyword_reduces_score():
    profile = SearchProfileCreate(
        name="PH",
        include_keywords=["pulmonary hypertension"],
        exclude_keywords=["case report"],
        email_to="a@example.com",
    )
    paper = PaperCreate(
        title="Pulmonary hypertension case report",
        abstract="case report",
        source="PubMed",
    )

    result = score_paper(paper, profile)

    assert result.relevance_score < 0
    assert "case report" in result.matched_keywords


def test_recent_publication_gets_freshness_bonus():
    profile = SearchProfileCreate(name="PH", include_keywords=[], email_to="a@example.com")
    paper = PaperCreate(
        title="Paper", source="PubMed", publication_date=date.today() - timedelta(days=3)
    )

    assert score_paper(paper, profile).relevance_score == 2


def test_high_impact_journal_scores_higher_than_default_journal():
    profile = SearchProfileCreate(
        name="Top journals",
        include_keywords=[],
        journals=["Nature", "Other Journal"],
        email_to="a@example.com",
    )

    assert (
        score_paper(PaperCreate(title="Paper", journal="Nature", source="PubMed"), profile)
        .relevance_score
        > score_paper(PaperCreate(title="Paper", journal="Other Journal", source="PubMed"), profile)
        .relevance_score
    )
