from datetime import date

from litmonitor.schemas import PaperCreate
from litmonitor.services.reports import build_weekly_big_papers_report, digest_paper


def test_digest_paper_writes_manifest_and_markdown(tmp_path):
    paper = PaperCreate(
        title="Single-cell atlas of pulmonary vascular remodeling.",
        abstract=(
            "Pulmonary hypertension involves vascular remodeling. "
            "We analyzed single-cell RNA-seq data and identified endothelial changes. "
            "BMPR2 expression was decreased two fold."
        ),
        journal="Nature Medicine",
        doi="10.1/example",
        pmid="123",
        source="PubMed",
    )

    result = digest_paper(
        paper,
        output_dir=tmp_path,
        output_format="markdown",
        topic_keywords=["pulmonary hypertension", "single-cell"],
    )

    paths = {file.path.name for file in result.files}
    assert "paper_metadata_123.json" in paths
    assert "paper_digest_123.json" in paths
    assert "paper_digest_123.md" in paths
    assert "manifest.json" in paths
    assert "BMPR2" in (tmp_path / "paper_digest_123.md").read_text()


def test_weekly_report_filters_interest_keywords_and_writes_outputs(tmp_path):
    records = [
        {
            "doi": "10.1/keep",
            "title": "Spatial single-cell atlas of pulmonary hypertension.",
            "journal": "Nature",
            "pub_date": "2026-04-22",
            "abstract": "This atlas maps pulmonary hypertension vascular remodeling.",
            "subjects": "bioinformatics",
            "citation_count": 4,
            "type": "journal-article",
            "url": "https://example.test/keep",
        },
        {
            "doi": "10.1/drop",
            "title": "Unrelated crystallography report.",
            "journal": "Nature",
            "pub_date": "2026-04-22",
            "abstract": "No relevant biology.",
            "subjects": "",
            "citation_count": 2,
            "type": "journal-article",
            "url": "https://example.test/drop",
        },
    ]

    result = build_weekly_big_papers_report(
        records,
        output_dir=tmp_path,
        date_from=date(2026, 4, 19),
        date_to=date(2026, 4, 26),
        interest_keywords=["pulmonary hypertension"],
    )

    assert [paper["doi"] for paper in result.papers] == ["10.1/keep"]
    assert (tmp_path / "weekly_big_papers.tsv").exists()
    assert (tmp_path / "weekly_big_papers.json").exists()
    assert (tmp_path / "weekly_big_papers.md").exists()
    assert (tmp_path / "manifest.json").exists()
