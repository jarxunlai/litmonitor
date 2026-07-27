from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select

from litmonitor.database import engine, init_db
from litmonitor.models import Digest, Paper, SearchProfile
from litmonitor.schemas import SearchProfileCreate
from litmonitor.services.dedup import upsert_paper
from litmonitor.services.llm.factory import get_llm_backend
from litmonitor.services.pubmed import search_pubmed
from litmonitor.services.reports import (
    DEFAULT_BIG_PAPER_JOURNALS,
    build_weekly_big_papers_report,
    digest_paper,
    fetch_big_paper_records,
    fetch_paper_metadata,
    last_week_window,
    paper_digest_output_dir,
    weekly_output_dir,
)
from litmonitor.services.runner import paper_to_schema, run_profile

app = typer.Typer(help="LitMonitor literature search and digest tool.")
profile_app = typer.Typer(help="Manage search profiles.")
digest_app = typer.Typer(help="Preview and send digests.")
paper_app = typer.Typer(help="Generate single-paper digest reports.")
report_app = typer.Typer(help="Generate standalone literature reports.")
app.add_typer(profile_app, name="profile")
app.add_typer(digest_app, name="digest")
app.add_typer(paper_app, name="paper")
app.add_typer(report_app, name="report")
console = Console()


@app.command("init-db")
def init_db_command() -> None:
    init_db()
    console.print("Database initialized.")


@app.command()
def search(
    query: str,
    journal: list[str] = typer.Option(None, "--journal"),
    since: str = "30d",
    limit: int = 20,
) -> None:
    papers = search_pubmed(query, journals=journal or [], since=since, limit=limit)
    with Session(engine) as session:
        for candidate in papers:
            upsert_paper(session, candidate)
    table = Table("Title", "Journal", "Date", "PMID", "DOI")
    for paper in papers:
        table.add_row(
            paper.title,
            paper.journal or "",
            str(paper.publication_date or ""),
            paper.pmid or "",
            paper.doi or "",
        )
    console.print(table)


@profile_app.command("add")
def profile_add(
    name: str = typer.Option(..., "--name"),
    include: list[str] = typer.Option(..., "--include"),
    exclude: list[str] = typer.Option(None, "--exclude"),
    journal: list[str] = typer.Option(None, "--journal"),
    schedule: str = "weekly",
    email: str = typer.Option(..., "--email"),
    date_window: str = "7d",
    min_relevance_score: float = 5,
    llm_enabled: bool = False,
) -> None:
    data = SearchProfileCreate(
        name=name,
        include_keywords=include,
        exclude_keywords=exclude or [],
        journals=journal or [],
        schedule=schedule,
        email_to=email,
        date_window=date_window,
        min_relevance_score=min_relevance_score,
        llm_enabled=llm_enabled,
    )
    with Session(engine) as session:
        profile = SearchProfile(**data.model_dump())
        session.add(profile)
        session.commit()
    console.print(f"Created profile: {name}")


@profile_app.command("list")
def profile_list() -> None:
    with Session(engine) as session:
        profiles = session.exec(select(SearchProfile)).all()
    table = Table("Name", "Enabled", "Schedule", "Email", "Keywords")
    for profile in profiles:
        table.add_row(
            profile.name,
            str(profile.enabled),
            profile.schedule,
            profile.email_to,
            ", ".join(profile.include_keywords),
        )
    console.print(table)


@profile_app.command("run")
def profile_run(name: str, use_llm: bool = False, send_email: bool = False) -> None:
    with Session(engine) as session:
        profile = session.exec(select(SearchProfile).where(SearchProfile.name == name)).first()
        if not profile:
            raise typer.BadParameter(f"Profile not found: {name}")
        run = run_profile(session, profile, use_llm=use_llm, send_email=send_email)
        console.print(f"Run {run.id}: {run.status}, new={run.new_count}, sent={run.sent_count}")
        if run.message:
            console.print(run.message)


@app.command("analyze-paper")
def analyze_paper(
    pmid: str | None = None,
    paper_id: int | None = None,
    profile: str | None = None,
    llm_backend: str | None = None,
) -> None:
    with Session(engine) as session:
        statement = select(Paper)
        if paper_id:
            statement = statement.where(Paper.id == paper_id)
        elif pmid:
            statement = statement.where(Paper.pmid == pmid)
        else:
            raise typer.BadParameter("Provide --pmid or --paper-id")
        paper = session.exec(statement).first()
        if not paper:
            raise typer.BadParameter("Paper not found")
        profile_model = None
        if profile:
            profile_model = session.exec(
                select(SearchProfile).where(SearchProfile.name == profile)
            ).first()
        backend = get_llm_backend(llm_backend)
        if not backend:
            raise typer.BadParameter("LLM backend is disabled")
        analysis = backend.analyze_paper(
            paper_to_schema(paper),
            SearchProfileCreate.model_validate(profile_model.model_dump())
            if profile_model
            else None,
        )
        console.print(analysis.model_dump_json(indent=2))


@digest_app.command("preview")
def digest_preview(profile: str) -> None:
    with Session(engine) as session:
        profile_model = session.exec(
            select(SearchProfile).where(SearchProfile.name == profile)
        ).first()
        if not profile_model:
            raise typer.BadParameter(f"Profile not found: {profile}")
        run = session.exec(
            select(Digest).where(Digest.profile_id == profile_model.id).order_by(Digest.id.desc())
        ).first()
        if run:
            console.print(run.body_text)
        else:
            console.print("No digest found.")


@digest_app.command("send")
def digest_send(profile: str) -> None:
    from litmonitor.services.mailer import send_digest_email

    with Session(engine) as session:
        profile_model = session.exec(
            select(SearchProfile).where(SearchProfile.name == profile)
        ).first()
        if not profile_model:
            raise typer.BadParameter(f"Profile not found: {profile}")
        digest = session.exec(
            select(Digest).where(Digest.profile_id == profile_model.id).order_by(Digest.id.desc())
        ).first()
        if not digest:
            raise typer.BadParameter("No digest found")
        send_digest_email(session, digest)
        console.print(f"Digest {digest.id}: {digest.status}")


@paper_app.command("digest")
def paper_digest(
    pmid: str | None = None,
    doi: str | None = None,
    arxiv: str | None = None,
    pdf: Path | None = None,
    paper_id: int | None = None,
    output_dir: Path | None = None,
    output_format: str = "markdown",
    topic_keyword: list[str] = typer.Option(None, "--topic-keyword"),
) -> None:
    if paper_id:
        with Session(engine) as session:
            paper_model = session.get(Paper, paper_id)
            if not paper_model:
                raise typer.BadParameter(f"Paper not found: {paper_id}")
            paper = paper_to_schema(paper_model)
    else:
        paper = fetch_paper_metadata(pmid=pmid, doi=doi, arxiv=arxiv, pdf=pdf)
    identifier = paper.pmid or paper.doi or paper.title
    result = digest_paper(
        paper,
        output_dir=output_dir or paper_digest_output_dir(identifier),
        output_format=output_format,
        topic_keywords=topic_keyword or [],
    )
    console.print(f"Paper digest written: {result.output_dir}")
    for file in result.files:
        console.print(f"- {file.role}: {file.path}")


@report_app.command("weekly-big")
def weekly_big_report(
    date_from: str | None = None,
    date_to: str | None = None,
    journal: list[str] = typer.Option(None, "--journal"),
    interest_keyword: list[str] = typer.Option(None, "--interest-keyword"),
    top_n: int = 20,
    rows_per_journal: int = 30,
    output_dir: Path | None = None,
) -> None:
    default_from, default_to = last_week_window()
    start = default_from if date_from is None else date.fromisoformat(date_from)
    end = default_to if date_to is None else date.fromisoformat(date_to)
    journals = journal or []
    records = fetch_big_paper_records(
        journals=journals or DEFAULT_BIG_PAPER_JOURNALS,
        date_from=start,
        date_to=end,
        rows_per_journal=rows_per_journal,
    )
    topic = "-".join(interest_keyword or []) or "general"
    result = build_weekly_big_papers_report(
        records,
        output_dir=output_dir or weekly_output_dir(topic),
        date_from=start,
        date_to=end,
        interest_keywords=interest_keyword or [],
        top_n=top_n,
    )
    console.print(f"Weekly report written: {result.output_dir}")
    console.print(f"Papers: {len(result.papers)}")
    for file in result.files:
        console.print(f"- {file.role}: {file.path}")


@app.command()
def export(profile: str | None = None, format: str = "csv", output: Path | None = None) -> None:
    with Session(engine) as session:
        papers = session.exec(select(Paper)).all()
    if format == "bibtex":
        text = "\n".join(
            f"@article{{pmid{paper.pmid or paper.id},\n  title={{{paper.title}}},\n  journal={{{paper.journal or ''}}},\n  year={{{paper.publication_date.year if paper.publication_date else ''}}},\n  doi={{{paper.doi or ''}}}\n}}"
            for paper in papers
        )
    else:
        lines = ["title,journal,publication_date,doi,pmid,url"]
        lines.extend(
            f'"{paper.title}","{paper.journal or ""}","{paper.publication_date or ""}","{paper.doi or ""}","{paper.pmid or ""}","{paper.url or ""}"'
            for paper in papers
        )
        text = "\n".join(lines)
    if output:
        output.write_text(text)
    else:
        console.print(text)


if __name__ == "__main__":
    app()
