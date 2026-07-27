from datetime import datetime, timezone
from email.message import EmailMessage
import socket
import smtplib
import time

from sqlmodel import Session

from litmonitor.config import Settings, get_settings
from litmonitor.models import Digest


SMTP_ATTEMPTS = 4
SMTP_BACKOFF_SECONDS = 5.0


def send_digest_email(session: Session, digest: Digest, settings: Settings | None = None) -> Digest:
    settings = settings or get_settings()
    if not settings.smtp_host or not digest.email_to:
        digest.status = "failed"
        digest.error_message = "SMTP_HOST and digest email_to are required"
        session.add(digest)
        session.commit()
        return digest

    message = EmailMessage()
    message["Subject"] = digest.subject
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = digest.email_to
    message.set_content(digest.body_text)
    message.add_alternative(digest.body_html, subtype="html")
    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    last_error = ""
    for attempt in range(SMTP_ATTEMPTS):
        try:
            with smtp_class(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
                if settings.smtp_use_tls and not settings.smtp_use_ssl:
                    smtp.starttls()
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(message)
            last_error = ""
            break
        except (smtplib.SMTPException, OSError, socket.gaierror) as exc:
            last_error = str(exc)
            if attempt < SMTP_ATTEMPTS - 1:
                time.sleep(SMTP_BACKOFF_SECONDS * (attempt + 1))
    if not last_error:
        digest.status = "sent"
        digest.sent_at = datetime.now(timezone.utc)
        digest.error_message = ""
    else:
        digest.status = "failed"
        digest.error_message = last_error
    session.add(digest)
    session.commit()
    session.refresh(digest)
    return digest
