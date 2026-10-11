"""Profile ownership checks.

Every endpoint that reads or changes a profile (or anything derived from it,
like agent runs) must go through `owned_profile`, so one user can never read or
delete another user's data by guessing an id.

Two kinds of owner:
- Logged-in users: profile.user_id must equal the Kinde user id in the token.
- Guests (no login): the browser that created the profile received a random
  `guest_key` and must send it back in the `X-Profile-Key` header.

Anything else gets a 404 (not 403), so ids cannot be probed for existence.
"""
from __future__ import annotations

import secrets
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db

PROFILE_KEY_HEADER = "X-Profile-Key"


def new_guest_key() -> str:
    return secrets.token_urlsafe(32)


def is_owner(profile: models.Profile, user: Optional[dict[str, Any]], profile_key: Optional[str]) -> bool:
    if profile.user_id:
        return bool(user and user.get("id") == profile.user_id)
    if profile.guest_key and profile_key:
        return secrets.compare_digest(profile.guest_key, profile_key)
    return False


def load_owned_profile(
    profile_id: int,
    db: Session,
    user: Optional[dict[str, Any]],
    profile_key: Optional[str],
) -> models.Profile:
    profile = db.get(models.Profile, profile_id)
    if not profile or not is_owner(profile, user, profile_key):
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def owned_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_current_user),
    x_profile_key: Optional[str] = Header(default=None, alias=PROFILE_KEY_HEADER),
) -> models.Profile:
    """FastAPI dependency for routes with a `{profile_id}` path parameter."""
    return load_owned_profile(profile_id, db, user, x_profile_key)
