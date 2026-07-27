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


def cleanup_unfinished_runs(session: Session, profile: SearchProfile) -> None:
    runs = session.exec(
        select(SearchRun)
        .where(SearchRun.profile_id == profile.id)
        .where(SearchRun.status == "running")
    ).all()
    for run in runs:
        for digest in session.exec(select(Digest).where(Digest.run_id == run.id)).all():
            session.delete(digest)
        for analysis in session.exec(
            select(PaperLLMAnalysis).where(PaperLLMAnalysis.run_id == run.id)
        ).all():
            session.delete(analysis)
        for result in session.exec(
            select(PaperSearchResult).where(PaperSearchResult.run_id == run.id)
        ).all():
            session.delete(result)
        run.status = "failed"
        run.message = "Interrupted before immediate no-LLM resend."
        run.result_count = 0
        run.new_count = 0
        run.sent_count = 0
        run.llm_analyzed_count = 0
        run.llm_failed_count = 0
        run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        print(f"cleaned unfinished run profile={profile.name!r} run={run.id}", flush=True)
    session.commit()


def main() -> int:
    settings = Settings(llm_enabled=False)
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
                cleanup_unfinished_runs(session, profile)
                profile.llm_enabled = False
                session.add(profile)
            session.commit()

            for profile in profiles:
                print(f"running immediate send profile={profile.name!r}", flush=True)
                run = run_profile(session, profile, use_llm=False, send_email=True, settings=settings)
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
