"""Agent run endpoints: run the multi-agent pipeline and serve its results.

All profile-scoped routes check ownership (app/ownership.py).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.agents.orchestrator import Orchestrator
from app.auth import get_current_user
from app.database import get_db
from app.ownership import PROFILE_KEY_HEADER, load_owned_profile, owned_profile
from app.services import assistant as assistant_service
from app.services import calendar as calendar_service
from app.services.analytics import build_insights

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _save_run(db: Session, profile: models.Profile, result: dict) -> models.AgentRun:
    run = models.AgentRun(profile_id=profile.id, status="completed", summary=result["summary"])
    db.add(run)
    db.flush()
    for log in result["logs"]:
        db.add(models.AgentLog(run_id=run.id, agent=log["agent"], message=log["message"],
                               confidence=log.get("confidence")))
    for m in result["matches"]:
        db.add(models.MatchResult(
            run_id=run.id,
            opportunity_id=m.get("opportunity_id", ""),
            title=m.get("title", ""),
            provider=m.get("provider"),
            url=m.get("url"),
            amount=m.get("amount"),
            deadline=m.get("deadline"),
            deadline_note=m.get("deadline_note"),
            eligible=m.get("eligible", False),
            status=m.get("status"),
            score=m.get("score", 0.0),
            confidence=m.get("confidence", 0.0),
            reasons=m.get("reasons", []),
            unmet=m.get("unmet", []),
            notes=m.get("notes") or [],
            documents=m.get("documents", []),
            roadmap=m.get("roadmap", []),
            description=m.get("description"),
            criteria=m.get("criteria", {}),
        ))
    db.commit()
    db.refresh(run)
    return run


def _latest_run(db: Session, profile_id: int) -> models.AgentRun | None:
    return db.scalars(
        select(models.AgentRun)
        .where(models.AgentRun.profile_id == profile_id)
        .order_by(models.AgentRun.created_at.desc(), models.AgentRun.id.desc())
    ).first()


def _match_dicts(run: models.AgentRun) -> list[dict]:
    return [schemas.MatchOut.model_validate(m).model_dump() for m in run.matches]


def _matches_for(db: Session, profile: models.Profile) -> list[dict]:
    """Matches from the latest saved run; runs the pipeline once if none exists.

    The assistant and calendar used to re-run the full pipeline (web search
    and LLM calls) on every request. Reusing the saved run makes them instant.
    """
    run = _latest_run(db, profile.id)
    if run is None:
        run = _save_run(db, profile, Orchestrator().run(profile))
    return _match_dicts(run)


@router.post("/run/{profile_id}", response_model=schemas.AgentRunOut)
def run_agents(profile: models.Profile = Depends(owned_profile), db: Session = Depends(get_db)):
    result = Orchestrator().run(profile)
    run = _save_run(db, profile, result)
    out = schemas.AgentRunOut.model_validate(run)
    out.insights = result["insights"]
    return out


@router.get("/latest/{profile_id}", response_model=Optional[schemas.AgentRunOut])
def latest_run(profile: models.Profile = Depends(owned_profile), db: Session = Depends(get_db)):
    """The most recent saved run with fresh insights, or null if there is none.

    Lets the app show results after a page reload without re-running the
    pipeline (which may call web search and an LLM).
    """
    run = _latest_run(db, profile.id)
    if run is None:
        return None
    out = schemas.AgentRunOut.model_validate(run)
    out.insights = build_insights(_match_dicts(run), [])
    return out


@router.post("/simulate", response_model=schemas.SimulateResponse)
def simulate(payload: schemas.SimulateRequest):
    """What-if simulator: evaluate a hypothetical profile without saving anything.

    Runs in "simulate" mode: curated data only, no web search, no LLM.
    """
    data = payload.model_dump()
    data.pop("user_id", None)
    owned = data.pop("owned_documents", [])
    profile = SimpleNamespace(**data, owned_documents=owned)
    result = Orchestrator().run(profile, owned_documents=owned, mode="simulate")
    return schemas.SimulateResponse(
        summary=result["summary"],
        logs=result["logs"],
        matches=result["matches"],
        insights=result["insights"],
    )


@router.post("/assistant", response_model=schemas.AssistantResponse)
def assistant(
    payload: schemas.AssistantRequest,
    db: Session = Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_current_user),
    x_profile_key: Optional[str] = Header(default=None, alias=PROFILE_KEY_HEADER),
):
    profile = load_owned_profile(payload.profile_id, db, user, x_profile_key)
    profile_dict = {
        "name": profile.name, "category": profile.category,
        "state": profile.state, "education_level": profile.education_level,
        "annual_income": profile.annual_income,
    }
    reply = assistant_service.answer(
        question=payload.question,
        matches=_matches_for(db, profile),
        name=profile.name,
        profile_id=profile.id,
        profile=profile_dict,
    )
    return schemas.AssistantResponse(**reply)


@router.get("/calendar/{profile_id}")
def calendar(profile: models.Profile = Depends(owned_profile), db: Session = Depends(get_db)):
    """Download deadlines of open, eligible schemes as an .ics calendar file."""
    matches = [m for m in _matches_for(db, profile) if m.get("status") != "closed"]
    ics = calendar_service.build_ics(matches, only_eligible=True)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=lifepilot-deadlines.ics"},
    )


@router.get("/runs/{profile_id}", response_model=list[schemas.AgentRunOut])
def list_runs(profile: models.Profile = Depends(owned_profile), db: Session = Depends(get_db)):
    return db.scalars(
        select(models.AgentRun)
        .where(models.AgentRun.profile_id == profile.id)
        .order_by(models.AgentRun.created_at.desc())
    ).all()


@router.get("/run/{run_id}", response_model=schemas.AgentRunOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(get_current_user),
    x_profile_key: Optional[str] = Header(default=None, alias=PROFILE_KEY_HEADER),
):
    run = db.get(models.AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        load_owned_profile(run.profile_id, db, user, x_profile_key)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
