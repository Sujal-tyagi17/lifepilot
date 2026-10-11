"""Profile endpoints.

Every route that touches an existing profile checks ownership (see
app/ownership.py). There is deliberately no "list all profiles" endpoint.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.llm.provider import get_provider
from app.ownership import PROFILE_KEY_HEADER, is_owner, new_guest_key, owned_profile
from app.resume.parser import ResumeParseError, extract_text

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _created_out(profile: models.Profile) -> schemas.ProfileCreatedOut:
    out = schemas.ProfileCreatedOut.model_validate(profile)
    out.guest_key = profile.guest_key
    return out


@router.post("", response_model=schemas.ProfileCreatedOut, status_code=201)
def create_or_update_profile(
    payload: schemas.ProfileCreate,
    db: Session = Depends(get_db),
    current_user: Optional[dict[str, Any]] = Depends(get_current_user),
    x_profile_key: Optional[str] = Header(default=None, alias=PROFILE_KEY_HEADER),
):
    """Create a profile, or update the caller's existing one.

    - Logged in: one profile per user, found by user id only.
    - Guest: the profile whose guest key the browser presents is updated;
      otherwise a new guest profile is created with a fresh key.
    - A logged-in user presenting the key of a guest profile claims it, so
      work done before signing in is kept.
    """
    data = payload.model_dump()
    data.pop("user_id", None)  # ownership is never taken from the request body
    user_id = current_user.get("id") if current_user else None

    existing: models.Profile | None = None
    if user_id:
        existing = db.scalars(
            select(models.Profile)
            .where(models.Profile.user_id == user_id)
            .order_by(models.Profile.created_at.desc())
        ).first()
        if not existing and x_profile_key:
            guest = db.scalars(
                select(models.Profile).where(
                    models.Profile.guest_key == x_profile_key,
                    models.Profile.user_id.is_(None),
                )
            ).first()
            if guest and is_owner(guest, None, x_profile_key):
                existing = guest
        if not data.get("email") and current_user.get("email"):
            data["email"] = current_user["email"]
    elif x_profile_key:
        guest = db.scalars(
            select(models.Profile).where(models.Profile.guest_key == x_profile_key)
        ).first()
        if guest and is_owner(guest, None, x_profile_key):
            existing = guest

    if existing:
        for k, v in data.items():
            if v is not None:
                setattr(existing, k, v)
        if user_id:
            existing.user_id = user_id
        if not existing.guest_key:
            existing.guest_key = new_guest_key()
        db.commit()
        db.refresh(existing)
        return _created_out(existing)

    # PostgreSQL only: re-sync the id sequence if it drifted (no-op on SQLite).
    try:
        db.execute(text(
            "SELECT setval(pg_get_serial_sequence('profiles', 'id'), "
            "COALESCE((SELECT MAX(id) FROM profiles), 0) + 1, false);"
        ))
        db.commit()
    except Exception:
        db.rollback()

    profile = models.Profile(**data, user_id=user_id, guest_key=new_guest_key())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _created_out(profile)


@router.post("/parse-resume", response_model=schemas.ParseResumeResponse)
async def parse_resume_to_profile(file: UploadFile = File(...)):
    """Read a resume and suggest profile fields using the configured LLM."""
    content = await file.read()
    try:
        resume_text = extract_text(file.filename or "", content)
    except ResumeParseError as e:
        raise HTTPException(status_code=422, detail=str(e))

    llm = get_provider()
    if llm.name == "mock":
        raise HTTPException(
            status_code=503,
            detail="Filling a profile from a resume needs an LLM provider (set LLM_PROVIDER in .env).",
        )

    prompt = f"""Extract profile information from the resume below.
Return ONLY a JSON object with these keys (use null when the resume does not say):
name, email, age, gender, state, category, education_level, field_of_study,
annual_income, disability, goals.
Never guess category, income or disability; they are almost never in a resume.

Resume:
{resume_text[:5000]}"""
    data = llm.generate_json(prompt, system="You are a strict JSON data extractor. Output only JSON.")
    if not data:
        raise HTTPException(status_code=502, detail="Could not extract details from this resume.")
    if not data.get("name"):
        data["name"] = "Unknown"
    try:
        return schemas.ParseResumeResponse(**{k: v for k, v in data.items() if k != "user_id"})
    except Exception:
        raise HTTPException(status_code=502, detail="The extracted details were not in the expected format.")


@router.get("/me/latest", response_model=Optional[schemas.ProfileCreatedOut])
def get_my_latest_profile(
    db: Session = Depends(get_db),
    current_user: Optional[dict[str, Any]] = Depends(get_current_user),
):
    """The logged-in user's own profile, or null."""
    if not current_user or not current_user.get("id"):
        return None
    profile = db.scalars(
        select(models.Profile)
        .where(models.Profile.user_id == current_user["id"])
        .order_by(models.Profile.created_at.desc())
    ).first()
    if profile and not profile.guest_key:
        profile.guest_key = new_guest_key()
        db.commit()
        db.refresh(profile)
    return _created_out(profile) if profile else None


@router.get("/{profile_id}", response_model=schemas.ProfileOut)
def get_profile(profile: models.Profile = Depends(owned_profile)):
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile: models.Profile = Depends(owned_profile), db: Session = Depends(get_db)):
    db.delete(db.merge(profile))
    db.commit()
