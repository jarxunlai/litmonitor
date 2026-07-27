from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine

from litmonitor.models import Digest, SearchProfile, SearchRun
from litmonitor.services import scheduler


def test_weekly_scheduler_retries_unsent_recent_digest(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    calls: list[tuple[str, int | None]] = []

    with Session(engine) as session:
        profile = SearchProfile(
            name="Weekly",
            schedule="weekly",
            enabled=True,
            email_to="user@example.com",
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.add(
            SearchRun(
                profile_id=profile.id,
                status="success",
                started_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            Digest(
                profile_id=profile.id,
                subject="Digest",
                body_html="<p>Digest</p>",
                body_text="Digest",
                email_to="user@example.com",
                status="draft",
            )
        )
        session.commit()

    def fake_send_digest_email(session, digest):
        calls.append(("send", digest.id))
        digest.status = "sent"
        session.add(digest)
        session.commit()
        return digest

    def fail_run_profile(*args, **kwargs):
        raise AssertionError("recent successful weekly runs should not be repeated")

    monkeypatch.setattr(scheduler, "engine", engine)
    monkeypatch.setattr(scheduler, "send_digest_email", fake_send_digest_email)
    monkeypatch.setattr(scheduler, "run_profile", fail_run_profile)

    scheduler.run_due_weekly_profiles()

    assert calls == [("send", 1)]
