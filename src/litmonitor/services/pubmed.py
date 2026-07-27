from datetime import date
import time
import xml.etree.ElementTree as ET

import httpx

from litmonitor.config import get_settings
from litmonitor.schemas import PaperCreate
from litmonitor.services.query_builder import build_pubmed_query, keywords_from_query

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
REQUEST_ATTEMPTS = 4
REQUEST_BACKOFF_SECONDS = 3.0
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _text(node: ET.Element | None, path: str) -> str | None:
    if node is None:
        return None
    found = node.find(path)
    return "".join(found.itertext()).strip() if found is not None else None


def _parse_pubdate(article: ET.Element) -> date | None:
    pubdate = article.find(".//JournalIssue/PubDate")
    if pubdate is None:
        return None
    year = _text(pubdate, "Year")
    if not year or not year.isdigit():
        return None
    month_text = (_text(pubdate, "Month") or "1").lower()[:3]
    day_text = _text(pubdate, "Day") or "1"
    month = int(month_text) if month_text.isdigit() else MONTHS.get(month_text, 1)
    day = int(day_text) if day_text.isdigit() else 1
    return date(int(year), month, day)


def _authors(article: ET.Element) -> str | None:
    values: list[str] = []
    for author in article.findall(".//AuthorList/Author"):
        collective = _text(author, "CollectiveName")
        if collective:
            values.append(collective)
            continue
        last = _text(author, "LastName")
        fore = _text(author, "ForeName")
        if last and fore:
            values.append(f"{fore} {last}")
        elif last:
            values.append(last)
    return "; ".join(values) if values else None


def _doi(article: ET.Element) -> str | None:
    for node in article.findall(".//ELocationID"):
        if node.attrib.get("EIdType", "").lower() == "doi" and node.text:
            return node.text.strip()
    for node in article.findall(".//ArticleId"):
        if node.attrib.get("IdType", "").lower() == "doi" and node.text:
            return node.text.strip()
    return None


def _pmcid(pubmed_article: ET.Element) -> str | None:
    for node in pubmed_article.findall(".//ArticleId"):
        if node.attrib.get("IdType", "").lower() == "pmc" and node.text:
            return node.text.strip()
    return None


def parse_pubmed_xml(xml_text: str) -> list[PaperCreate]:
    root = ET.fromstring(xml_text)
    papers: list[PaperCreate] = []
    for pubmed_article in root.findall(".//PubmedArticle"):
        article = pubmed_article.find(".//Article")
        citation = pubmed_article.find(".//MedlineCitation")
        if article is None or citation is None:
            continue
        pmid = _text(citation, "PMID")
        title = _text(article, "ArticleTitle") or "(untitled)"
        abstract_parts = [
            "".join(node.itertext()).strip()
            for node in article.findall(".//Abstract/AbstractText")
            if "".join(node.itertext()).strip()
        ]
        abstract = "\n".join(abstract_parts) if abstract_parts else None
        papers.append(
            PaperCreate(
                title=title,
                abstract=abstract,
                authors=_authors(article),
                journal=_text(article, ".//Journal/Title"),
                publication_date=_parse_pubdate(article),
                doi=_doi(article),
                pmid=pmid,
                pmcid=_pmcid(pubmed_article),
                source="PubMed",
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            )
        )
    return papers


def _get_with_retries(
    client: httpx.Client,
    url: str,
    params: dict[str, str],
    attempts: int = REQUEST_ATTEMPTS,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
        except httpx.HTTPError as exc:
            last_error = exc
        if attempt < attempts - 1:
            time.sleep(REQUEST_BACKOFF_SECONDS * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("PubMed request failed without an error")


def search_pubmed(
    query: str, journals: list[str] | None = None, since: str = "30d", limit: int = 20
) -> list[PaperCreate]:
    settings = get_settings()
    pubmed_query = build_pubmed_query(
        keywords_from_query(query), journals=journals or [], since=since
    )
    params = {
        "db": "pubmed",
        "term": pubmed_query,
        "retmode": "json",
        "retmax": str(limit),
        "sort": "pub+date",
    }
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    with httpx.Client(timeout=30) as client:
        search_response = _get_with_retries(client, f"{EUTILS}/esearch.fcgi", params=params)
        ids = search_response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        fetch_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
        if settings.ncbi_api_key:
            fetch_params["api_key"] = settings.ncbi_api_key
        fetch_response = _get_with_retries(client, f"{EUTILS}/efetch.fcgi", params=fetch_params)
        return parse_pubmed_xml(fetch_response.text)
