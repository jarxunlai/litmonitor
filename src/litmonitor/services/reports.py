from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import csv
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import httpx

from litmonitor.config import get_settings
from litmonitor.schemas import PaperCreate
from litmonitor.services.pubmed import EUTILS, parse_pubmed_xml

CROSSREF_WORKS = "https://api.crossref.org/works"

DEFAULT_BIG_PAPER_JOURNALS = [
    "Nature",
    "Science",
    "Cell",
    "Nature Biotechnology",
    "Nature Methods",
    "Nature Genetics",
    "Nature Medicine",
    "Nature Machine Intelligence",
    "Nature Computational Science",
    "Cell Systems",
    "Cell Genomics",
]

JOURNAL_WEIGHTS = {
    "Nature": 10.0,
    "Science": 10.0,
    "Cell": 10.0,
    "Nature Biotechnology": 9.5,
    "Nature Methods": 9.5,
    "Nature Genetics": 9.2,
    "Nature Medicine": 8.8,
    "Nature Machine Intelligence": 8.2,
    "Nature Computational Science": 8.4,
    "Cell Systems": 8.4,
    "Cell Genomics": 8.7,
}

GENERIC_KEYWORDS = {
    "bioinformatics": 4.0,
    "single-cell": 3.0,
    "single cell": 2.4,
    "spatial": 2.1,
    "atlas": 2.4,
    "resource": 2.2,
    "database": 2.5,
    "foundation model": 3.5,
    "language model": 3.5,
    "llm": 3.0,
    "algorithm": 2.2,
    "software": 2.5,
    "machine learning": 2.8,
    "deep learning": 2.8,
    "genomics": 2.1,
    "transcriptomics": 2.1,
}

NEGATIVE_KEYWORDS = {
    "case report": -4.0,
    "editorial": -5.0,
    "correction": -6.0,
    "erratum": -6.0,
    "retraction": -8.0,
    "news": -3.0,
    "comment": -2.0,
}


@dataclass
class GeneratedFile:
    role: str
    path: Path


@dataclass
class PaperDigestResult:
    identifier: str
    title: str
    output_dir: Path
    files: list[GeneratedFile] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class WeeklyReportResult:
    output_dir: Path
    papers: list[dict]
    files: list[GeneratedFile] = field(default_factory=list)


def default_report_dir(*parts: str) -> Path:
    return Path("data/reports", *parts)


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "report"


def normalize_space(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def strip_tags(text: str | None) -> str:
    return normalize_space(re.sub(r"<[^>]+>", " ", html.unescape(text or "")))


def write_json(path: Path, data: object) -> GeneratedFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    return GeneratedFile("json", path)


def write_text(path: Path, text: str, role: str = "text") -> GeneratedFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return GeneratedFile(role, path)


def fetch_paper_metadata(
    pmid: str | None = None,
    doi: str | None = None,
    arxiv: str | None = None,
    pdf: Path | None = None,
) -> PaperCreate:
    if pmid:
        return fetch_pubmed_paper(pmid)
    if doi:
        return fetch_doi_paper(doi)
    if arxiv:
        return fetch_arxiv_paper(arxiv)
    if pdf:
        return PaperCreate(title=pdf.stem, source="PDF", url=str(pdf))
    raise ValueError("Provide one of pmid, doi, arxiv, or pdf")


def fetch_pubmed_paper(pmid: str) -> PaperCreate:
    settings = get_settings()
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    with httpx.Client(timeout=20) as client:
        response = client.get(f"{EUTILS}/efetch.fcgi", params=params)
        response.raise_for_status()
    papers = parse_pubmed_xml(response.text)
    if not papers:
        raise ValueError(f"No PubMed paper found for PMID {pmid}")
    return papers[0]


def fetch_doi_paper(doi: str) -> PaperCreate:
    with httpx.Client(timeout=20) as client:
        response = client.get(f"{CROSSREF_WORKS}/{doi}")
        response.raise_for_status()
        item = response.json().get("message", {})
    title = normalize_space((item.get("title") or [""])[0])
    journal = normalize_space((item.get("container-title") or [""])[0])
    authors = []
    for author in item.get("author", []) or []:
        name = " ".join(x for x in [author.get("given", ""), author.get("family", "")] if x).strip()
        if name:
            authors.append(name)
    return PaperCreate(
        title=title or doi,
        abstract=strip_tags(item.get("abstract", "")) or None,
        authors="; ".join(authors) or None,
        journal=journal or None,
        doi=doi,
        source="CrossRef",
        url=normalize_space(item.get("URL", "")) or None,
    )


def fetch_arxiv_paper(arxiv_id: str) -> PaperCreate:
    clean_id = arxiv_id.replace("arxiv:", "").strip()
    with httpx.Client(timeout=20) as client:
        response = client.get("https://export.arxiv.org/api/query", params={"id_list": clean_id})
        response.raise_for_status()
    root = ET.fromstring(response.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise ValueError(f"No arXiv paper found for {arxiv_id}")
    title = normalize_space("".join(entry.findtext("atom:title", "", ns)))
    abstract = normalize_space("".join(entry.findtext("atom:summary", "", ns)))
    authors = [
        normalize_space(author.findtext("atom:name", "", ns))
        for author in entry.findall("atom:author", ns)
    ]
    return PaperCreate(
        title=title or arxiv_id,
        abstract=abstract or None,
        authors="; ".join(a for a in authors if a) or None,
        journal="arXiv",
        source="arXiv",
        url=f"https://arxiv.org/abs/{clean_id}",
    )


def digest_paper(
    paper: PaperCreate,
    output_dir: Path,
    output_format: str = "markdown",
    topic_keywords: list[str] | None = None,
    identifier: str | None = None,
) -> PaperDigestResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    identifier = identifier or paper.pmid or paper.doi or slugify(paper.title[:80])
    safe_id = slugify(identifier)
    metadata = paper.model_dump(mode="json")
    sections = extract_sections(paper.abstract or "")
    entities = extract_entities(f"{paper.title} {paper.abstract or ''}", topic_keywords or [])
    statistics = extract_statistics(paper.abstract or "")
    impact = assess_impact(paper)
    report_data = {
        "metadata": metadata,
        "sections": sections,
        "entities": entities,
        "statistics": statistics,
        "impact": impact,
    }

    files = [
        write_json(output_dir / f"paper_metadata_{safe_id}.json", metadata),
        write_json(output_dir / f"paper_digest_{safe_id}.json", report_data),
    ]
    if output_format in {"markdown", "md"}:
        files.append(
            write_text(
                output_dir / f"paper_digest_{safe_id}.md",
                render_paper_digest_markdown(report_data),
                "markdown",
            )
        )
    elif output_format == "txt":
        files.append(
            write_text(
                output_dir / f"paper_digest_{safe_id}.txt",
                render_paper_digest_text(report_data),
                "text",
            )
        )
    elif output_format != "json":
        raise ValueError("output_format must be one of markdown, json, or txt")

    files.append(write_text(output_dir / f"extraction_log_{safe_id}.txt", "Digest generated\n"))
    result = PaperDigestResult(
        identifier=safe_id, title=paper.title, output_dir=output_dir, files=files, metadata=metadata
    )
    files.append(write_json(output_dir / "manifest.json", result_to_manifest(result)))
    return result


def extract_sections(abstract: str) -> dict[str, str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if s.strip()]
    if not sentences:
        return {"background": "", "methods": "", "results": "", "conclusions": ""}
    methods = []
    results = []
    for sentence in sentences[1:-1]:
        low = sentence.lower()
        if any(k in low for k in ["used", "performed", "analyzed", "sequencing", "cohort"]):
            methods.append(sentence)
        if any(k in low for k in ["found", "identified", "showed", "revealed", "increased"]):
            results.append(sentence)
    return {
        "background": " ".join(sentences[:2]),
        "methods": " ".join(methods[:2]),
        "results": " ".join(results[:3]),
        "conclusions": " ".join(sentences[-2:]),
    }


def extract_entities(text: str, topic_keywords: list[str]) -> dict[str, list[str]]:
    genes = sorted(set(re.findall(r"\b[A-Z]{2,}[A-Z0-9-]*\b", text)))
    excluded = {"AND", "OR", "THE", "WITH", "FROM", "WAS", "WERE"}
    topic_mentions = [kw for kw in topic_keywords if kw.lower() in text.lower()]
    return {
        "genes": [g for g in genes if g not in excluded][:30],
        "topic_mentions": topic_mentions,
    }


def extract_statistics(text: str) -> dict[str, list[str]]:
    return {
        "pvalues": sorted(set(re.findall(r"[pP]\s*[<>=]+\s*(?:0\.)?0*\d+", text)))[:10],
        "fold_changes": sorted(set(re.findall(r"[\d.]+[\s-]*fold", text, re.I)))[:10],
        "sample_sizes": sorted(set(re.findall(r"[nN]\s*[=:]\s*\d+", text)))[:10],
    }


def assess_impact(paper: PaperCreate) -> dict[str, object]:
    high_impact = any(j.lower() in (paper.journal or "").lower() for j in JOURNAL_WEIGHTS)
    return {
        "journal_tier": "High Impact" if high_impact else "Standard",
        "is_high_impact": high_impact,
        "publication_category": "Original Research",
    }


def render_paper_digest_markdown(report_data: dict) -> str:
    metadata = report_data["metadata"]
    sections = report_data["sections"]
    entities = report_data["entities"]
    statistics = report_data["statistics"]
    impact = report_data["impact"]
    return f"""# Paper Digest: {metadata.get("title", "Unknown Paper")}

## Citation
- **Authors:** {metadata.get("authors") or "Unknown"}
- **Journal:** {metadata.get("journal") or "Unknown"}
- **Date:** {metadata.get("publication_date") or "Unknown"}
- **DOI:** {metadata.get("doi") or "Not available"}
- **PMID:** {metadata.get("pmid") or "Not available"}

## Abstract
{metadata.get("abstract") or "No abstract available."}

## Key Findings
{sections.get("results") or "No structured findings extracted."}

## Methods Summary
{sections.get("methods") or "Methods information not separately extracted from abstract."}

## Conclusions
{sections.get("conclusions") or "Conclusion not separately extracted."}

## Entities And Statistics
- **Genes/Proteins:** {", ".join(entities.get("genes", [])[:15]) or "None extracted"}
- **Topic Keywords:** {", ".join(entities.get("topic_mentions", [])) or "None"}
- **P-values:** {", ".join(statistics.get("pvalues", [])) or "None extracted"}
- **Fold changes:** {", ".join(statistics.get("fold_changes", [])) or "None extracted"}
- **Sample sizes:** {", ".join(statistics.get("sample_sizes", [])) or "None extracted"}

## Research Impact Notes
- **Journal Impact Tier:** {impact["journal_tier"]}
- **High Impact Journal:** {"Yes" if impact["is_high_impact"] else "No"}

---
Generated: {datetime.now().isoformat(timespec="seconds")}
"""


def render_paper_digest_text(report_data: dict) -> str:
    metadata = report_data["metadata"]
    return "\n".join(
        [
            f"Title: {metadata.get('title', '')}",
            f"Journal: {metadata.get('journal') or ''}",
            f"DOI: {metadata.get('doi') or ''}",
            "",
            metadata.get("abstract") or "No abstract available.",
        ]
    )


def result_to_manifest(result: PaperDigestResult | WeeklyReportResult) -> dict:
    return {
        "output_dir": str(result.output_dir),
        "files": [{"role": f.role, "path": str(f.path)} for f in result.files],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_big_paper_records(
    journals: list[str],
    date_from: date,
    date_to: date,
    rows_per_journal: int = 30,
) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    with httpx.Client(timeout=30, headers={"User-Agent": "litmonitor/0.1"}) as client:
        for journal in journals:
            params = {
                "filter": f"from-pub-date:{date_from},until-pub-date:{date_to},container-title:{journal},type:journal-article",
                "rows": rows_per_journal,
                "select": "DOI,title,container-title,published,published-print,published-online,abstract,author,URL,subject,is-referenced-by-count,type",
            }
            response = client.get(CROSSREF_WORKS, params=params)
            response.raise_for_status()
            for item in response.json().get("message", {}).get("items", []):
                record = parse_crossref_record(item)
                key = (record.get("doi") or record.get("title", "")).lower()
                if key and key not in seen:
                    seen.add(key)
                    records.append(record)
    return records


def parse_crossref_record(item: dict) -> dict:
    title = normalize_space((item.get("title") or [""])[0])
    journal = normalize_space((item.get("container-title") or [""])[0])
    authors = []
    for author in item.get("author", []) or []:
        name = " ".join(x for x in [author.get("given", ""), author.get("family", "")] if x).strip()
        if name:
            authors.append(name)
    return {
        "doi": normalize_space(item.get("DOI", "")),
        "title": title,
        "journal": journal,
        "pub_date": choose_crossref_date(item),
        "abstract": strip_tags(item.get("abstract", "")),
        "authors": "; ".join(authors[:12]),
        "url": normalize_space(item.get("URL", "")),
        "subjects": "; ".join(item.get("subject", []) or []),
        "citation_count": int(item.get("is-referenced-by-count", 0) or 0),
        "type": normalize_space(item.get("type", "")),
    }


def choose_crossref_date(item: dict) -> str:
    for key in ["published-print", "published-online", "published"]:
        part = item.get(key)
        if isinstance(part, dict) and part.get("date-parts"):
            values = list(part["date-parts"][0]) + [1, 1]
            return f"{values[0]:04d}-{values[1]:02d}-{values[2]:02d}"
    return ""


def build_weekly_big_papers_report(
    records: list[dict],
    output_dir: Path,
    date_from: date,
    date_to: date,
    interest_keywords: list[str] | None = None,
    top_n: int = 20,
) -> WeeklyReportResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    keywords = [kw.lower() for kw in (interest_keywords or []) if kw.strip()]
    papers = []
    for record in records:
        if is_non_primary_record(record):
            continue
        if not date_in_window(record.get("pub_date", ""), date_from, date_to):
            continue
        scored = dict(record)
        scored.update(score_big_paper(record, keywords))
        if keywords and not scored["matched_interest_keywords"]:
            continue
        papers.append(scored)
    papers = sorted(
        papers,
        key=lambda row: (row["impact_score"], row.get("citation_count", 0)),
        reverse=True,
    )[:top_n]
    for index, paper in enumerate(papers, start=1):
        paper["rank"] = index
        paper.update(summarize_big_paper(paper))

    files = [
        write_weekly_tsv(output_dir / "weekly_big_papers.tsv", papers),
        write_json(output_dir / "weekly_big_papers.json", papers),
        write_text(
            output_dir / "weekly_big_papers.md",
            render_weekly_big_papers_markdown(papers, date_from, date_to, keywords),
            "markdown",
        ),
    ]
    result = WeeklyReportResult(output_dir=output_dir, papers=papers, files=files)
    files.append(write_json(output_dir / "manifest.json", result_to_manifest(result)))
    return result


def score_big_paper(record: dict, interest_keywords: list[str]) -> dict:
    text = f"{record.get('title', '')} {record.get('abstract', '')} {record.get('subjects', '')}".lower()
    matched_interest = [kw for kw in interest_keywords if kw in text]
    matched_generic = [kw for kw in GENERIC_KEYWORDS if kw in text]
    generic_score = sum(GENERIC_KEYWORDS[kw] for kw in matched_generic)
    negative_score = sum(value for kw, value in NEGATIVE_KEYWORDS.items() if kw in text)
    citation_bonus = min(float(record.get("citation_count", 0) or 0), 50.0) * 0.03
    impact_score = (
        JOURNAL_WEIGHTS.get(record.get("journal", ""), 5.0)
        + generic_score
        + negative_score
        + len(matched_interest) * 2.0
        + citation_bonus
        + (1.0 if record.get("abstract") else 0.0)
    )
    return {
        "matched_interest_keywords": "; ".join(matched_interest),
        "matched_generic_keywords": "; ".join(matched_generic),
        "impact_score": round(impact_score, 3),
    }


def is_non_primary_record(record: dict) -> bool:
    text = (
        f"{record.get('title', '')} {record.get('type', '')} {record.get('abstract', '')}".lower()
    )
    return any(term in text for term in NEGATIVE_KEYWORDS)


def date_in_window(value: str, date_from: date, date_to: date) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return date_from <= parsed <= date_to


def summarize_big_paper(paper: dict) -> dict:
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", paper.get("abstract", "")) if s.strip()
    ]
    return {
        "why_it_matters": sentences[0]
        if sentences
        else "Abstract unavailable from retrieval sources.",
        "major_discoveries": " ".join(sentences[1:3]) if len(sentences) > 1 else "",
        "significance": "Matched keywords: "
        + (
            paper.get("matched_interest_keywords")
            or paper.get("matched_generic_keywords")
            or "high-impact journal scope"
        ),
    }


def write_weekly_tsv(path: Path, papers: list[dict]) -> GeneratedFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "title",
        "journal",
        "pub_date",
        "doi",
        "matched_interest_keywords",
        "matched_generic_keywords",
        "impact_score",
        "url",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for paper in papers:
            writer.writerow({key: paper.get(key, "") for key in fieldnames})
    return GeneratedFile("tsv", path)


def render_weekly_big_papers_markdown(
    papers: list[dict], date_from: date, date_to: date, interest_keywords: list[str]
) -> str:
    lines = [
        "# Weekly Big Papers Report",
        "",
        f"Coverage window: {date_from} to {date_to}",
        f"Interest keywords: {', '.join(interest_keywords) if interest_keywords else 'None'}",
        "",
    ]
    for paper in papers:
        lines.extend(
            [
                f"## {paper['rank']}. {paper['title']}",
                f"- Journal: {paper.get('journal', '')}",
                f"- Date: {paper.get('pub_date', '')}",
                f"- DOI: {paper.get('doi', '')}",
                f"- Impact score: {paper.get('impact_score', '')}",
                f"- Matched keywords: {paper.get('matched_interest_keywords') or paper.get('matched_generic_keywords')}",
                f"- Why it matters: {paper.get('why_it_matters', '')}",
                f"- Major discoveries: {paper.get('major_discoveries', '')}",
                "",
            ]
        )
    return "\n".join(lines)


def weekly_output_dir(topic: str | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return default_report_dir("weekly-big-papers", f"{stamp}-{slugify(topic or 'general')}")


def paper_digest_output_dir(identifier: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return default_report_dir("paper-digests", f"{stamp}-{slugify(identifier)}")


def last_week_window() -> tuple[date, date]:
    end = date.today()
    return end - timedelta(days=7), end
