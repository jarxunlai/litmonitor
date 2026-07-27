from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from litmonitor.database import get_session
from litmonitor.models import Digest, SearchProfile, SearchRun
from litmonitor.schemas import DigestRequest
from litmonitor.services.digest import save_digest
from litmonitor.services.mailer import send_digest_email

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("")
def list_digests(session: Session = Depends(get_session)):
    return session.exec(select(Digest).order_by(Digest.id.desc())).all()


@router.post("/preview")
def preview_digest(payload: DigestRequest, session: Session = Depends(get_session)):
    profile = session.get(SearchProfile, payload.profile_id)
    run = session.get(SearchRun, payload.run_id)
    if not profile or not run:
        raise HTTPException(status_code=404, detail="Profile or run not found")
    return save_digest(session, profile, run, payload.email_to)


@router.post("/send")
def send_digest(payload: DigestRequest, session: Session = Depends(get_session)):
    digest = preview_digest(payload, session)
    return send_digest_email(session, digest)
