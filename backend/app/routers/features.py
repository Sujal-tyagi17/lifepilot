"""Phase 4: what would change it, priority planner, knowledge graph, document check."""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.ownership import PROFILE_KEY_HEADER, load_owned_profile, owned_profile
from app.services import counterfactual, doc_verify, graph, planner
from app.services.doc_types import doc_type

router = APIRouter(prefix="/api", tags=["features"])

PROFILE_FIELDS = ("name", "age", "gender", "state", "category", "education_level", "field_of_study",
                  "annual_income", "disability", "goals")


def _profile_dict(p: models.Profile) -> dict:
    return {f: getattr(p, f) for f in PROFILE_FIELDS}


def _matches(db: Session, p: models.Profile) -> list[dict]:
    from app.routers.agent import _matches_for
    return _matches_for(db, p)


@router.get("/counterfactuals/{profile_id}")
def what_would_change_it(profile: models.Profile = Depends(owned_profile)):
    """Smallest honest changes that would unlock more schemes, ranked by value per effort."""
    return counterfactual.counterfactuals(_profile_dict(profile))


class PlanJob(BaseModel):
    id: str = Field(max_length=300)
    title: str = Field(max_length=300)
    company: Optional[str] = Field(default=None, max_length=300)
    url: Optional[str] = Field(default=None, max_length=2000)
    fit_score: float = Field(default=0.5, ge=0, le=1)


class PlanSkill(BaseModel):
    skill: str = Field(max_length=80)
    jobs: int = Field(default=0, ge=0, le=100)


class PlannerIn(BaseModel):
    hours_per_week: float = Field(default=6, ge=1, le=40)
    owned_documents: List[str] = Field(default_factory=list, max_length=200)
    jobs: List[PlanJob] = Field(default_factory=list, max_length=10)
    skill: Optional[PlanSkill] = None


@router.post("/planner/{profile_id}")
def priority_planner(body: PlannerIn, profile: models.Profile = Depends(owned_profile), db: Session = Depends(get_db)):
    """Week-by-week plan: documents, scheme applications, job applications and one skill."""
    return planner.plan(_matches(db, profile), body.hours_per_week, body.owned_documents,
                        [j.model_dump() for j in body.jobs], body.skill.model_dump() if body.skill else None)


class GraphIn(BaseModel):
    owned_documents: List[str] = Field(default_factory=list, max_length=200)


@router.post("/graph/{profile_id}")
def knowledge_graph(body: GraphIn, profile: models.Profile = Depends(owned_profile)):
    return graph.build_graph(_profile_dict(profile), body.owned_documents)


class VerifyIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    profile_id: Optional[int] = None


@router.post("/documents/verify")
def verify_document(
    body: VerifyIn,
    db: Session = Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_current_user),
    x_profile_key: Optional[str] = Header(default=None, alias=PROFILE_KEY_HEADER),
):
    """Text read from a scanned certificate in → its type, fields and checks out. Nothing is stored."""
    profile, limits, matches = None, [], []
    if body.profile_id is not None:
        p = load_owned_profile(body.profile_id, db, user, x_profile_key)
        profile = _profile_dict(p)
        matches = _matches(db, p)
        limits = sorted({(m.get("criteria") or {}).get("max_income") for m in matches
                         if m.get("status") == "eligible" and (m.get("criteria") or {}).get("max_income")})
    res = doc_verify.verify(body.text, profile, limits)
    # The names your schemes use for this kind of document, so the page can tick them off
    res["documents"] = sorted({d for m in matches for d in (m.get("documents") or []) if doc_type(d) == res["type"]}, key=lambda d: (len(d), d))
    return res
