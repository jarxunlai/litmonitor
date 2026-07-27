from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from litmonitor.config import Settings
from litmonitor.database import engine
from litmonitor.models import Digest, PaperLLMAnalysis, PaperSearchResult, SearchProfile, SearchRun
from litmonitor.services.runner import run_profile


PROFILE_NAMES = [
    "PAH high-impact journals weekly",
    "Single-cell spatial lung top journals weekly",
]


def _delete_run_children(session: Session, run_id: int) -> tuple[int, int, int]:
    result_count = 0
    analysis_count = 0
    digest_count = 0

    for digest in session.exec(select(Digest).where(Digest.run_id == run_id)).all():
        session.delete(digest)
        digest_count += 1
    for analysis in session.exec(select(PaperLLMAnalysis).where(PaperLLMAnalysis.run_id == run_id)).all():
        session.delete(analysis)
        analysis_count += 1
    for result in session.exec(select(PaperSearchResult).where(PaperSearchResult.run_id == run_id)).all():
        session.delete(result)
        result_count += 1

    return result_count, analysis_count, digest_count


def reset_profile_runs(session: Session, profile: SearchProfile) -> None:
    runs = session.exec(select(SearchRun).where(SearchRun.profile_id == profile.id)).all()
    removed_results = 0
    removed_analyses = 0
    removed_digests = 0

    for run in runs:
        result_count, analysis_count, digest_count = _delete_run_children(session, run.id)
        removed_results += result_count
        removed_analyses += analysis_count
        removed_digests += digest_count
        run.status = "failed"
        run.message = "Reset before first-week resend."
        run.result_count = 0
        run.new_count = 0
        run.sent_count = 0
        run.llm_analyzed_count = 0
        run.llm_failed_count = 0
        run.finished_at = datetime.now(timezone.utc)
        session.add(run)

    session.commit()
    print(
        f"reset profile={profile.name!r} runs={len(runs)} "
        f"results={removed_results} analyses={removed_analyses} digests={removed_digests}",
        flush=True,
    )


def main() -> int:
    # This resend is meant to recover the first weekly email. Keep LLM off here so
    # network/model failures cannot block PubMed retrieval and SMTP delivery.
    run_settings = Settings(llm_enabled=False)

    with Session(engine) as session:
        profiles = []
        for name in PROFILE_NAMES:
            profile = session.exec(select(SearchProfile).where(SearchProfile.name == name)).first()
            if profile is None:
                raise RuntimeError(f"Profile not found: {name}")
            profiles.append(profile)

        original_llm_flags = {profile.id: profile.llm_enabled for profile in profiles}
        try:
            for profile in profiles:
                reset_profile_runs(session, profile)
                profile.llm_enabled = False
                session.add(profile)
            session.commit()

            for profile in profiles:
                print(f"running profile={profile.name!r}", flush=True)
                run = run_profile(session, profile, use_llm=False, send_email=True, settings=run_settings)
                print(
                    f"completed profile={profile.name!r} run={run.id} status={run.status} "
                    f"results={run.result_count} new={run.new_count} sent={run.sent_count} "
                    f"message={run.message!r}",
                    flush=True,
                )
        finally:
            for profile in profiles:
                profile.llm_enabled = bool(original_llm_flags.get(profile.id, False))
                session.add(profile)
            session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
