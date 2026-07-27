from dataclasses import dataclass
from datetime import datetime

from jinja2 import Environment, PackageLoader, select_autoescape
from sqlmodel import Session, select

from litmonitor.config import get_settings
from litmonitor.models import (
    Digest,
    Paper,
    PaperLLMAnalysis,
    PaperSearchResult,
    SearchProfile,
    SearchRun,
)


@dataclass
class DigestBuildResult:
    subject: str
    body_html: str
    body_text: str
    paper_count: int


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("litmonitor", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )


def build_digest(session: Session, profile: SearchProfile, run: SearchRun) -> DigestBuildResult:
    settings = get_settings()
    rows = session.exec(
        select(PaperSearchResult, Paper)
        .join(Paper, Paper.id == PaperSearchResult.paper_id)
        .where(PaperSearchResult.run_id == run.id)
        .order_by(PaperSearchResult.relevance_score.desc())
    ).all()
    analyses = {
        analysis.paper_id: analysis
        for analysis in session.exec(
            select(PaperLLMAnalysis).where(PaperLLMAnalysis.run_id == run.id)
        ).all()
        if analysis.status == "success"
    }
    papers = [
        {"result": result, "paper": paper, "analysis": analyses.get(paper.id)}
        for result, paper in rows
        if result.is_new and result.relevance_score >= profile.min_relevance_score
    ]
    if settings.digest_max_papers_per_run > 0:
        papers = papers[: settings.digest_max_papers_per_run]
    highly = [item for item in papers if item["result"].relevance_score >= 10]
    possible = [item for item in papers if item["result"].relevance_score < 10]
    subject = f"[LitMonitor] {profile.name}: {len(papers)} new papers"
    template = _env().get_template("email_digest.html")
    body_html = template.render(
        profile=profile,
        run=run,
        generated_at=datetime.now(),
        highly=highly,
        possible=possible,
        paper_count=len(papers),
    )
    lines = [subject, f"Run: {run.id}", f"Total new papers: {len(papers)}", ""]
    for label, items in [("Highly relevant", highly), ("Possibly relevant", possible)]:
        lines.append(label)
        for item in items:
            paper = item["paper"]
            result = item["result"]
            analysis = item["analysis"]
            lines.extend(
                [
                    f"- {paper.title}",
                    f"  Journal: {paper.journal or ''}",
                    f"  Date: {paper.publication_date or ''}",
                    f"  DOI: {paper.doi or ''}",
                    f"  PMID: {paper.pmid or ''}",
                    f"  URL: {paper.url or ''}",
                    f"  Matched keywords: {', '.join(result.matched_keywords)}",
                    f"  Relevance score: {result.relevance_score}",
                    f"  LLM summary: {analysis.one_sentence_summary if analysis else 'not available'}",
                ]
            )
        lines.append("")
    return DigestBuildResult(subject, body_html, "\n".join(lines), len(papers))


def save_digest(
    session: Session, profile: SearchProfile, run: SearchRun, email_to: str | None = None
) -> Digest:
    built = build_digest(session, profile, run)
    digest = Digest(
        profile_id=profile.id,
        run_id=run.id,
        subject=built.subject,
        body_html=built.body_html,
        body_text=built.body_text,
        email_to=email_to or profile.email_to,
        paper_count=built.paper_count,
        status="draft",
    )
    session.add(digest)
    session.commit()
    session.refresh(digest)
    return digest
