from litmonitor.schemas import SearchRequest
from litmonitor.services.query_builder import build_pubmed_query


def test_builds_include_journal_exclude_and_date_query():
    request = SearchRequest(
        query="pulmonary hypertension endothelial",
        journals=["Nature Medicine", "Circulation"],
        since="30d",
    )

    query = build_pubmed_query(
        include_keywords=["pulmonary hypertension", "endothelial"],
        exclude_keywords=["case report", "editorial"],
        journals=request.journals,
        since=request.since,
    )

    assert '"pulmonary hypertension"[Title/Abstract]' in query
    assert "endothelial[Title/Abstract]" in query
    assert '"Nature Medicine"[Journal]' in query
    assert '"Circulation"[Journal]' in query
    assert 'NOT ("case report"[Title/Abstract] OR editorial[Title/Abstract])' in query
    assert '"last 30 days"[PDat]' in query
