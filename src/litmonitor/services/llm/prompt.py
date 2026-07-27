from litmonitor.schemas import PaperCreate, SearchProfileCreate

SYSTEM_PROMPT = (
    "You are a biomedical literature analyst. Produce concise, objective, "
    "non-promotional analysis for a researcher. Do not overstate the findings. "
    "If information is insufficient, explicitly state the limitation. Return strict JSON only."
)


def build_user_prompt(paper: PaperCreate, profile: SearchProfileCreate | None) -> str:
    profile_name = profile.name if profile else "ad hoc search"
    include = ", ".join(profile.include_keywords) if profile else ""
    exclude = ", ".join(profile.exclude_keywords) if profile else ""
    return f"""Analyze the following paper for a weekly literature digest.

Search Profile:
Name: {profile_name}
Research interests: {include}
Excluded topics: {exclude}

Paper:
Title: {paper.title}
Journal: {paper.journal or ""}
Publication date: {paper.publication_date or ""}
DOI: {paper.doi or ""}
PMID: {paper.pmid or ""}
Abstract:
{paper.abstract or ""}

Return strict JSON with exactly the following keys:
{{
  "one_sentence_summary": "...",
  "background": "...",
  "main_finding": "...",
  "method_or_data": "...",
  "relevance_to_profile": "...",
  "limitations_or_caution": "...",
  "keywords": ["...", "..."],
  "confidence": "low|medium|high"
}}

Rules:
- Do not invent data not present in the title or abstract.
- If the abstract is missing, say that interpretation is limited.
- Keep each field concise.
- Focus on relevance to the search profile.
- Avoid promotional language."""


def build_full_prompt(paper: PaperCreate, profile: SearchProfileCreate | None) -> str:
    return f"{SYSTEM_PROMPT}\n\n{build_user_prompt(paper, profile)}"
