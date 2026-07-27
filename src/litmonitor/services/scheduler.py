from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from litmonitor.database import engine
from litmonitor.models import Digest, SearchProfile, SearchRun
from litmonitor.services.mailer import send_digest_email
from litmonitor.services.runner import run_profile


def retry_latest_unsent_digest(session: Session, profile: SearchProfile) -> None:
    digest = session.exec(
        select(Digest)
        .where(Digest.profile_id == profile.id)
        .where(Digest.email_to != "")
        .where(Digest.status.in_(["draft", "failed"]))
        .order_by(Digest.id.desc())
    ).first()
    if digest:
        send_digest_email(session, digest)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def run_due_weekly_profiles() -> None:
    with Session(engine) as session:
        profiles = session.exec(
            select(SearchProfile)
            .where(SearchProfile.enabled.is_(True))
            .where(SearchProfile.schedule == "weekly")
        ).all()
        for profile in profiles:
            latest = session.exec(
                select(SearchRun)
                .where(SearchRun.profile_id == profile.id)
                .where(SearchRun.status == "success")
                .order_by(SearchRun.started_at.desc())
            ).first()
            if latest and as_utc(latest.started_at) > datetime.now(timezone.utc) - timedelta(
                days=7
            ):
                retry_latest_unsent_digest(session, profile)
                continue
            run_profile(session, profile, use_llm=profile.llm_enabled, send_email=True)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_due_weekly_profiles, "interval", days=1, id="weekly-profile-check")
    return scheduler
