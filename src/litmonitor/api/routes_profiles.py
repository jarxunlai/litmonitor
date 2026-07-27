from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from litmonitor.database import get_session
from litmonitor.models import SearchProfile
from litmonitor.schemas import SearchProfileCreate, SearchProfileUpdate
from litmonitor.services.runner import run_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("")
def list_profiles(session: Session = Depends(get_session)):
    return session.exec(select(SearchProfile)).all()


@router.post("")
def create_profile(payload: SearchProfileCreate, session: Session = Depends(get_session)):
    profile = SearchProfile(**payload.model_dump())
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/{profile_id}")
def get_profile(profile_id: int, session: Session = Depends(get_session)):
    profile = session.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/{profile_id}")
def update_profile(
    profile_id: int, payload: SearchProfileUpdate, session: Session = Depends(get_session)
):
    profile = session.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, session: Session = Depends(get_session)):
    profile = session.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.enabled = False
    session.add(profile)
    session.commit()
    return {"status": "disabled"}


@router.post("/{profile_id}/run")
def run_profile_endpoint(
    profile_id: int,
    send_email: bool = False,
    use_llm: bool = False,
    session: Session = Depends(get_session),
):
    profile = session.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return run_profile(session, profile, use_llm=use_llm, send_email=send_email)
