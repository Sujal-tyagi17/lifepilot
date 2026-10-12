"""ML Lab endpoints: real metrics, live predictions with explanations, labelling and retraining."""
from __future__ import annotations

import csv
import json
import logging
import random
import threading
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.ml import predict
from app.ml.describe import describe

logger = logging.getLogger("lifepilot.routers.ml")
router = APIRouter(prefix="/api/ml", tags=["ml"])
DATA = Path(predict.__file__).resolve().parent / "data"
TEAM_FILE = DATA / "fit_pairs_team.csv"
_train_lock = threading.Lock()
_training = {"running": False, "last": None}


def _dev_only():
    """Labelling and retraining change files on the server: development only."""
    if settings.environment.lower() == "production":
        raise HTTPException(status_code=403, detail="Labelling and retraining are turned off in production.")


@router.get("/metrics")
def metrics():
    m = predict.metrics()
    if not m:
        return {"trained": False, "hint": "Run: python -m app.ml.train"}
    return {"trained": True, "training": _training, **m}


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


@router.post("/predict/role")
def predict_role(body: TextIn):
    from app.jobs.catalog import classify_role_rules, family_label
    ml = predict.role_family_explained(body.text)
    rules = classify_role_rules(body.text.split(".")[0], body.text)
    if ml:
        ml["label_name"] = family_label(ml["label"])
        for t in ml["top"]:
            t["label_name"] = family_label(t["label"])
    return {"model": ml, "rules": {"label": rules[0], "label_name": family_label(rules[0]), "confidence": rules[1]}}


@router.post("/predict/intent")
def predict_intent(body: TextIn):
    from app.knowledge.rag import detect_intent
    return {"model": predict.intent(body.text, explain_it=True), "used": detect_intent(body.text)}


@router.post("/predict/document")
def predict_document(body: TextIn):
    return {"model": predict.document_type(body.text)}


@router.post("/predict/skills")
def predict_skills(body: TextIn):
    from app.jobs.resume import analyse_resume
    from app.jobs.skills import extract_skills, fuzzy_skills
    exact = extract_skills(body.text)
    return {"exact": exact, "fuzzy": fuzzy_skills(body.text, exact), "resume": analyse_resume(body.text)["skills"]}


@router.post("/describe")
def describe_yourself(body: TextIn):
    return describe(body.text)


class FitIn(BaseModel):
    job_text: str = Field(min_length=1, max_length=8000)
    resume_text: str = Field(default="", max_length=20000)
    target_role: str = Field(default="", max_length=120)
    education_level: Optional[str] = Field(default=None, max_length=40)


def _pair(body: FitIn) -> tuple[dict, dict]:
    from app.jobs.matching import HAND_WEIGHTS, candidate, score_with, weights
    title, _, rest = body.job_text.partition(".")
    job = {"title": title.strip(), "description": rest.strip() or body.job_text}
    cand = candidate({"education_level": body.education_level} if body.education_level else {}, body.resume_text, body.target_role)
    scored = score_with(job, cand)
    feats = {b["signal"]: b["value"] for b in scored["fit_breakdown"]}
    # The same pair with the old hand-set weights, for the rules-vs-ML comparison
    from app.jobs import matching
    learned = matching.weights
    matching.weights = lambda: HAND_WEIGHTS
    try:
        rules = score_with(job, cand)["fit_score"]
    finally:
        matching.weights = learned
    return {"features": feats, "learned_fit": scored["fit_score"], "rules_fit": rules, "weights": weights(),
            "breakdown": scored["fit_breakdown"], "probabilities": predict.fit_probabilities(feats),
            "skills_matched": scored["skills_matched"], "skills_missing": scored["skills_missing"]}, job


@router.post("/predict/fit")
def predict_fit(body: FitIn):
    out, _ = _pair(body)
    return out


# ── Labelling (team relabels resume–job pairs) ─────────────────────

FIT_COLUMNS = ["job_title", "job_text", "resume_text", "education_level", "target_role",
               "must", "nice", "role", "experience", "education", "field", "text", "rules_fit", "label", "labelled_by"]


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@router.get("/label/next")
def label_next():
    """A seed pair the team has not labelled yet, to check and relabel."""
    seed = _read(DATA / "fit_pairs.csv")
    done = {(r["job_text"], r["resume_text"]) for r in _read(TEAM_FILE)}
    todo = [r for r in seed if (r["job_text"], r["resume_text"]) not in done]
    if not todo:
        return {"pair": None, "done": len(done), "total": len(seed)}
    pair = random.choice(todo)
    return {"pair": {k: pair[k] for k in ("job_title", "job_text", "resume_text", "education_level", "target_role", "label")},
            "done": len(done), "total": len(seed)}


class LabelIn(BaseModel):
    job_title: str = Field(max_length=300)
    job_text: str = Field(max_length=8000)
    resume_text: str = Field(max_length=20000)
    education_level: Optional[str] = Field(default=None, max_length=40)
    target_role: str = Field(default="", max_length=120)
    label: Literal["Good", "Okay", "Poor"]
    labelled_by: str = Field(default="team", max_length=60)


@router.post("/label")
def add_label(body: LabelIn):
    _dev_only()
    out, _ = _pair(FitIn(job_text=f"{body.job_title}. {body.job_text}", resume_text=body.resume_text,
                         target_role=body.target_role, education_level=body.education_level))
    f = out["features"]
    row = {"job_title": body.job_title, "job_text": body.job_text, "resume_text": body.resume_text,
           "education_level": body.education_level or "", "target_role": body.target_role,
           **{k: f.get(k, "") for k in ("must", "nice", "role", "experience", "education", "field", "text")},
           "rules_fit": out["rules_fit"], "label": body.label, "labelled_by": body.labelled_by.strip() or "team"}
    rows = [r for r in _read(TEAM_FILE) if (r["job_text"], r["resume_text"]) != (body.job_text, body.resume_text)]
    rows.append(row)
    with open(TEAM_FILE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return {"saved": True, "team_labels": len(rows)}


@router.post("/retrain")
def retrain():
    """Retrain every model from the CSV files (takes about 20 seconds)."""
    _dev_only()
    if not _train_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Training is already running.")
    _training["running"] = True
    try:
        from app.ml import train
        train.main()
        predict.reload()
        _training["last"] = predict.metrics().get("trained_at")
        return {"ok": True, "trained_at": _training["last"]}
    except Exception as e:
        logger.error(f"Retraining failed: {e}")
        raise HTTPException(status_code=500, detail=f"Training failed: {e}")
    finally:
        _training["running"] = False
        _train_lock.release()
