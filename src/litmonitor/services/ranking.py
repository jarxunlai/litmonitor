from datetime import date

from litmonitor.schemas import PaperCreate, RankingResult, SearchProfileCreate

JOURNAL_SCORE_WEIGHTS = {
    "the new england journal of medicine": 6.0,
    "new england journal of medicine": 6.0,
    "nature": 6.0,
    "science": 6.0,
    "cell": 6.0,
    "the lancet": 5.8,
    "lancet": 5.8,
    "jama": 5.5,
    "nature medicine": 5.5,
    "circulation": 5.2,
    "european heart journal": 5.0,
    "journal of the american college of cardiology": 5.0,
    "american journal of respiratory and critical care medicine": 4.8,
    "the european respiratory journal": 4.8,
    "european respiratory journal": 4.8,
    "circulation research": 4.7,
    "the journal of clinical investigation": 4.6,
    "journal of clinical investigation": 4.6,
    "nature cardiovascular research": 4.6,
    "nature biotechnology": 5.0,
    "nature methods": 5.0,
    "nature genetics": 4.9,
    "nature immunology": 4.8,
    "nature communications": 4.4,
    "cell systems": 4.6,
    "cell genomics": 4.6,
    "cancer cell": 4.6,
    "science translational medicine": 4.6,
}


def _contains(text: str | None, keyword: str) -> bool:
    return keyword.lower() in (text or "").lower()


def journal_score(journal: str | None) -> float:
    key = (journal or "").lower()
    return JOURNAL_SCORE_WEIGHTS.get(key, 3.0 if key else 0.0)


def score_paper(paper: PaperCreate, profile: SearchProfileCreate) -> RankingResult:
    score = 0.0
    matched: list[str] = []
    exclusion_reason = None

    for keyword in profile.include_keywords:
        if _contains(paper.title, keyword):
            score += 5
            matched.append(keyword)
        elif _contains(paper.abstract, keyword):
            score += 2
            matched.append(keyword)

    if paper.journal and any(paper.journal.lower() == journal.lower() for journal in profile.journals):
        score += journal_score(paper.journal)
        matched.append(paper.journal)

    for keyword in profile.exclude_keywords:
        if _contains(paper.title, keyword) or _contains(paper.abstract, keyword):
            score -= 10
            matched.append(keyword)
            exclusion_reason = f"Matched excluded keyword: {keyword}"

    if paper.publication_date:
        age = (date.today() - paper.publication_date).days
        if age <= 7:
            score += 2
        elif age <= 30:
            score += 1

    return RankingResult(
        relevance_score=score, matched_keywords=matched, exclusion_reason=exclusion_reason
    )
