from datetime import date


def _field_term(term: str, field: str) -> str:
    clean = term.strip()
    if field == "Journal" or " " in clean or "-" in clean:
        clean = f'"{clean}"'
    return f"{clean}[{field}]"


def _or_group(terms: list[str], field: str) -> str:
    return " OR ".join(_field_term(term, field) for term in terms if term.strip())


def _date_clause(since: str | None) -> str:
    if not since:
        return ""
    if since.endswith("d") and since[:-1].isdigit():
        return f'"last {since[:-1]} days"[PDat]'
    if ":" in since:
        start, end = since.split(":", 1)
        end = end or date.today().isoformat()
        return f'("{start}"[PDat] : "{end}"[PDat])'
    return f'"{since}"[PDat]'


def build_pubmed_query(
    include_keywords: list[str],
    exclude_keywords: list[str] | None = None,
    journals: list[str] | None = None,
    since: str | None = None,
) -> str:
    parts: list[str] = []
    include = _or_group(include_keywords, "Title/Abstract")
    if include:
        parts.append(f"({include})")
    journal_group = _or_group(journals or [], "Journal")
    if journal_group:
        parts.append(f"({journal_group})")
    date = _date_clause(since)
    if date:
        parts.append(date)
    query = " AND ".join(parts) if parts else "all[sb]"
    exclude = _or_group(exclude_keywords or [], "Title/Abstract")
    if exclude:
        query = f"{query} NOT ({exclude})"
    return query


def keywords_from_query(query: str) -> list[str]:
    return [part.strip() for part in query.split() if part.strip()]
