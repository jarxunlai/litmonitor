import socket
import smtplib

from sqlmodel import Session, SQLModel, create_engine

from litmonitor.config import Settings
from litmonitor.models import Digest
from litmonitor.services.mailer import send_digest_email


def test_send_digest_email_records_socket_failure(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    def fail_smtp(*args, **kwargs):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(smtplib, "SMTP", fail_smtp)
    monkeypatch.setattr("litmonitor.services.mailer.time.sleep", lambda seconds: None)

    with Session(engine) as session:
        digest = Digest(
            subject="Digest",
            body_html="<p>Digest</p>",
            body_text="Digest",
            email_to="user@example.com",
        )
        session.add(digest)
        session.commit()
        session.refresh(digest)

        result = send_digest_email(
            session,
            digest,
            Settings(
                smtp_host="smtp.example.com",
                smtp_user="user@example.com",
                smtp_password="secret",
                smtp_from="user@example.com",
                smtp_use_ssl=False,
            ),
        )

        assert result.status == "failed"
        assert "name resolution failed" in result.error_message


def test_send_digest_email_uses_smtp_ssl_when_configured(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    calls: list[tuple[str, object]] = []

    def fail_plain_smtp(*args, **kwargs):
        raise AssertionError("plain SMTP should not be used when smtp_use_ssl is enabled")

    class FakeSmtpSsl:
        def __init__(self, host, port, timeout):
            calls.append(("connect", (host, port, timeout)))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def starttls(self):
            raise AssertionError("starttls should not be used with SMTP_SSL")

        def login(self, user, password):
            calls.append(("login", (user, password)))

        def send_message(self, message):
            calls.append(("send", message["To"]))

    monkeypatch.setattr(smtplib, "SMTP", fail_plain_smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtpSsl)

    with Session(engine) as session:
        digest = Digest(
            subject="Digest",
            body_html="<p>Digest</p>",
            body_text="Digest",
            email_to="user@example.com",
        )
        session.add(digest)
        session.commit()
        session.refresh(digest)

        result = send_digest_email(
            session,
            digest,
            Settings(
                smtp_host="smtp.qq.com",
                smtp_port=465,
                smtp_user="user@example.com",
                smtp_password="secret",
                smtp_from="user@example.com",
                smtp_use_tls=False,
                smtp_use_ssl=True,
            ),
        )

        assert result.status == "sent"
        assert calls == [
            ("connect", ("smtp.qq.com", 465, 30)),
            ("login", ("user@example.com", "secret")),
            ("send", "user@example.com"),
        ]


def test_send_digest_email_retries_transient_smtp_failure(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    calls = []

    class FlakySmtp:
        def __init__(self, host, port, timeout):
            calls.append(("connect", len(calls)))
            if len(calls) == 1:
                raise socket.timeout("handshake timed out")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def login(self, user, password):
            calls.append(("login", user))

        def send_message(self, message):
            calls.append(("send", message["To"]))

    monkeypatch.setattr(smtplib, "SMTP_SSL", FlakySmtp)
    monkeypatch.setattr("litmonitor.services.mailer.time.sleep", lambda seconds: None)

    with Session(engine) as session:
        digest = Digest(
            subject="Digest",
            body_html="<p>Digest</p>",
            body_text="Digest",
            email_to="user@example.com",
        )
        session.add(digest)
        session.commit()
        session.refresh(digest)

        result = send_digest_email(
            session,
            digest,
            Settings(
                smtp_host="smtp.qq.com",
                smtp_port=465,
                smtp_user="user@example.com",
                smtp_password="secret",
                smtp_from="user@example.com",
                smtp_use_tls=False,
                smtp_use_ssl=True,
            ),
        )

    assert result.status == "sent"
    assert calls == [
        ("connect", 0),
        ("connect", 1),
        ("login", "user@example.com"),
        ("send", "user@example.com"),
    ]
