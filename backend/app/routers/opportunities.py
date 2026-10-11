"""Opportunity endpoints: schemes (curated + semantic search) and jobs.

Job logic lives in app/jobs/ (sources, skills, matching); this module only
exposes it over HTTP.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.jobs.matching import candidate, match_report, search_query
from app.jobs.roadmap import build_plan
from app.jobs.sources import live_sources, sample_jobs, search_jobs, source_status
from app.knowledge.vectorstore import DATA_FILE, add_schemes, search as vector_search
from app.scraper.engine import scrape_portals

logger = logging.getLogger("lifepilot.routers.opportunities")

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

# Only government portals may be scraped on request. Without this, the endpoint
# would fetch any URL a caller sends, including internal addresses (SSRF).
ALLOWED_PORTAL_SUFFIXES = (".gov.in", ".nic.in")


@router.get("")
def list_opportunities():
    """All curated schemes in the dataset."""
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        logger.error(f"Could not read curated schemes: {e}")
        raise HTTPException(status_code=500, detail="Scheme dataset unavailable")


@router.get("/search")
def search_opportunities(q: str):
    """Semantic search over the ChromaDB vector store of schemes."""
    if not q.strip():
        return []
    try:
        return vector_search(q, n_results=10)
    except Exception as e:
        logger.error(f"Failed to search opportunities: {e}")
        raise HTTPException(status_code=500, detail="Search is unavailable right now")


class ScrapeRequest(BaseModel):
    urls: List[str] = Field(max_length=10)
    keywords: Optional[List[str]] = None


def _is_allowed_portal(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == s.lstrip(".") or host.endswith(s) for s in ALLOWED_PORTAL_SUFFIXES
    )


@router.post("/scrape")
def scrape_and_index(payload: ScrapeRequest):
    """Scrape Indian government portals (.gov.in / .nic.in) and index new schemes."""
    if not payload.urls:
        raise HTTPException(status_code=400, detail="At least one portal URL is required.")
    rejected = [u for u in payload.urls if not _is_allowed_portal(u)]
    if rejected:
        raise HTTPException(
            status_code=400,
            detail=f"Only https government portals (.gov.in, .nic.in) can be scraped. Rejected: {', '.join(rejected)}",
        )
    try:
        scraped = scrape_portals(payload.urls, payload.keywords)
        added_count = add_schemes(scraped) if scraped else 0
        return {
            "status": "success",
            "scraped_count": len(scraped),
            "indexed_count": added_count,
            "opportunities": scraped,
        }
    except Exception as e:
        logger.error(f"Failed to scrape portals: {e}")
        raise HTTPException(status_code=500, detail="Scraping failed")


# ── Jobs ──────────────────────────────────────────────────────

def _salary_label(job: dict) -> str:
    """Display salary only when the source states it. Never estimate."""
    if job.get("salary"):
        return job["salary"]
    lo, hi = job.get("salary_min"), job.get("salary_max")
    if not (lo or hi):
        return "Not disclosed"
    sym = "₹" if job.get("salary_currency") == "INR" else ""
    fmt = (lambda n: f"{sym}{n:,}") if sym != "₹" else (lambda n: f"{sym}{_inr(n)}")
    if lo and hi and lo != hi:
        return f"{fmt(lo)} - {fmt(hi)} / year"
    return f"{fmt(lo or hi)} / year"


def _inr(n: int) -> str:
    """Indian digit grouping: 1500000 -> 15,00,000."""
    s = str(int(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def _public_job(job: dict) -> dict:
    out = dict(job)
    out["salary"] = _salary_label(job)
    # Kept for the existing salary filter: annual INR, or null when not stated
    out["salary_num"] = job.get("salary_min") if job.get("salary_currency") == "INR" else None
    return out


@router.get("/jobs")
def get_jobs(q: str = "", skills: Optional[List[str]] = Query(None), location: Optional[str] = None):
    """Search sample roles, RSS feeds and (if configured) Adzuna and Serper."""
    return [_public_job(j) for j in search_jobs(q, skills or [], location)]


class JobMatchRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    resume_text: Optional[str] = Field(default="", max_length=60_000)
    desired_role: Optional[str] = Field(default="", max_length=120)
    expected_salary: Optional[int] = None
    skills: Optional[List[str]] = None


@router.post("/jobs/match")
def match_jobs(payload: JobMatchRequest):
    """Rank jobs for this person: the profile form, the resume and the target role.

    Returns the ranked jobs (with a score breakdown and a relevance flag), what
    was read from the resume, and the one skill that would lift the most matches.
    """
    profile = payload.profile or {}
    cand = candidate(profile, payload.resume_text or "", payload.desired_role or "", payload.skills)
    query = search_query(cand)
    # Live sources are searched in the user's state and across India; ranking
    # then puts their state first, remote next, then the rest of India.
    jobs = search_jobs(query, payload.skills or [], profile.get("state"), limit=0, filter_samples=False,
                       include_rss=False, fresher=cand["fresher"])
    report = match_report(jobs, profile, cand=cand)
    report["sources"] = live_sources()
    if report["sources"]:
        # Live search is set up: show real openings only, never the example roles
        report["jobs"] = [j for j in report["jobs"] if j.get("source") != "sample"]
    scopes = {"India", profile.get("state") or "India"}
    report["source_status"] = [{"source": k, "message": v} for k, v in source_status().items()
                               if k.split(" · ")[-1] in scopes]
    report["jobs"] = [_public_job(j) for j in report["jobs"][:80]]
    return report


class PlanJob(BaseModel):
    id: Optional[str] = Field(default=None, max_length=300)
    title: str = Field(max_length=300)
    description: str = Field(default="", max_length=20_000)
    company: Optional[str] = Field(default=None, max_length=300)
    location: Optional[str] = Field(default=None, max_length=300)
    url: Optional[str] = Field(default=None, max_length=2_000)
    source: Optional[str] = Field(default=None, max_length=40)
    family: Optional[str] = Field(default=None, max_length=40)


class JobPlanRequest(JobMatchRequest):
    job_id: Optional[str] = Field(default=None, max_length=300)
    job: Optional[PlanJob] = None
    hours_per_week: int = Field(default=8, ge=2, le=40)
    learned: List[str] = Field(default_factory=list, max_length=100)


@router.post("/jobs/plan")
def job_plan(payload: JobPlanRequest):
    """A personalised, week-by-week roadmap to become ready for one job."""
    job = None
    if payload.job_id:
        job = next((j for j in sample_jobs() if j["id"] == payload.job_id), None)
    if job is None and payload.job:
        job = payload.job.model_dump()
        if job.get("source") == "sample":
            job["family"] = job.get("family")  # trusted only for our own sample roles
        else:
            job["family"] = None
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found. Search again and pick it from the list.")
    cand = candidate(payload.profile or {}, payload.resume_text or "", payload.desired_role or "", payload.skills)
    return build_plan(job, cand, payload.hours_per_week, payload.learned)
