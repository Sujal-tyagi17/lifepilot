"""Job sources with caching.

Sources, all optional except the sample set:
1. Sample roles (app/data/indian_jobs.json): always available, works offline.
   These are illustrative role descriptions, not live openings, and are
   labelled "Sample" in the UI.
2. Public RSS feeds that publish jobs for reuse (We Work Remotely, python.org).
3. Adzuna job search API (free developer tier) when ADZUNA_APP_ID/KEY are set.
4. Serper (Google search API) when SERPER_API_KEY is set.

LinkedIn scraping was removed: LinkedIn's terms forbid it and it gets blocked.

No source ever invents a salary. If the source does not state one, salary is
None and the UI shows "Not disclosed".
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Callable

import httpx

from app.config import settings

logger = logging.getLogger("lifepilot.jobs.sources")

SAMPLE_JOBS_FILE = Path(__file__).resolve().parent.parent / "data" / "indian_jobs.json"

RSS_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/remote-jobs.rss",
    "https://www.python.org/jobs/feed/rss/",
]

CACHE_TTL_SECONDS = 6 * 60 * 60
_cache: dict[str, tuple[float, list[dict]]] = {}


def cached(key: str, fetch: Callable[[], list[dict]], ttl: int = CACHE_TTL_SECONDS) -> list[dict]:
    """Return a cached result for `key`, refreshing it after `ttl` seconds.

    Failed or empty fetches are not cached, so a temporary outage does not
    hide a source for six hours.
    """
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    data = fetch()
    if data:
        _cache[key] = (now, data)
    return data


def clear_cache() -> None:
    _cache.clear()


def _job(
    *, id: str, title: str, company: str | None, location: str | None, description: str,
    url: str | None, source: str, job_type: str | None = None, country: str | None = None,
    salary: str | None = None, salary_min: int | None = None, salary_max: int | None = None,
    currency: str | None = None,
) -> dict:
    return {
        "id": id,
        "title": title.strip(),
        "company": (company or "").strip() or None,
        "location": location,
        "job_type": job_type,
        "country": country,
        "description": description or "",
        "url": url,
        "source": source,
        "salary": salary,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
        "category": "job",
    }


# ── 1. Sample roles ───────────────────────────────────────────

def sample_jobs() -> list[dict]:
    try:
        with open(SAMPLE_JOBS_FILE, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f"Could not read sample jobs: {e}")
        return []
    jobs = []
    for j in items:
        jobs.append(_job(
            id=j["id"], title=j["title"], company=j.get("company"), location=j.get("location"),
            description=j.get("description", ""), url=j.get("url"), source="sample",
            job_type=j.get("job_type"), country=j.get("country"),
            salary=j.get("salary"), salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
            currency="INR" if j.get("salary_min") else None,
        ))
    return jobs


# ── 2. RSS feeds ──────────────────────────────────────────────

def _split_company(title: str) -> tuple[str | None, str]:
    """We Work Remotely titles look like "Company: Role"."""
    if ":" in title:
        company, role = title.split(":", 1)
        if company.strip() and role.strip():
            return company.strip(), role.strip()
    return None, title


def rss_jobs() -> list[dict]:
    from app.scraper.engine import _scrape_rss_jobs

    jobs: list[dict] = []
    for url in RSS_FEEDS:
        for item in cached(f"rss:{url}", lambda url=url: _scrape_rss_jobs(url)):
            company, role = _split_company(item.get("title", ""))
            jobs.append(_job(
                id=item["id"], title=role, company=company, location="Remote",
                description=item.get("description", ""), url=item.get("url"),
                source="rss", job_type="Remote", country="Global",
            ))
    return jobs


# ── 3. Adzuna ─────────────────────────────────────────────────

def adzuna_jobs(query: str, location: str | None) -> list[dict]:
    if not (settings.adzuna_app_id and settings.adzuna_app_key):
        return []

    def fetch() -> list[dict]:
        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "what": query,
            "results_per_page": 30,
            "content-type": "application/json",
        }
        if location and location.lower() not in ("india", "remote"):
            params["where"] = location
        url = f"https://api.adzuna.com/v1/api/jobs/{settings.adzuna_country}/search/1"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"Adzuna search failed: HTTP {resp.status_code}")
                return []
            results = resp.json().get("results", [])
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(f"Adzuna search failed: {e}")
            return []

        jobs = []
        for r in results:
            # Adzuna estimates salaries for ads that don't state one; only show stated ones.
            stated = str(r.get("salary_is_predicted", "1")) == "0"
            smin = int(r["salary_min"]) if stated and r.get("salary_min") else None
            smax = int(r["salary_max"]) if stated and r.get("salary_max") else None
            loc = (r.get("location") or {}).get("display_name")
            jobs.append(_job(
                id=f"adzuna-{r.get('id')}", title=r.get("title", ""),
                company=(r.get("company") or {}).get("display_name"), location=loc,
                description=r.get("description", ""), url=r.get("redirect_url"), source="adzuna",
                job_type=(r.get("contract_time") or "").replace("_", " ").title() or None,
                country="India" if settings.adzuna_country == "in" else settings.adzuna_country.upper(),
                salary_min=smin, salary_max=smax, currency="INR" if settings.adzuna_country == "in" else None,
            ))
        return jobs

    return cached(f"adzuna:{query.lower()}:{(location or '').lower()}", fetch)


# ── 4. Serper (Google search) ─────────────────────────────────

def serper_jobs(query: str, skills: list[str], location: str | None) -> list[dict]:
    if not settings.serper_api_key:
        return []

    def fetch() -> list[dict]:
        skills_part = " ".join(f'"{s}"' for s in skills[:3])
        loc_part = f"({location} OR remote)" if location else "remote"
        q = f'"{query}" {skills_part} jobs {loc_part}'
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                    json={"q": q, "num": 10},
                )
            if resp.status_code != 200:
                logger.warning(f"Serper search failed: HTTP {resp.status_code}")
                return []
            organic = resp.json().get("organic", [])
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(f"Serper search failed: {e}")
            return []

        jobs = []
        for item in organic[:8]:
            title, link = item.get("title", ""), item.get("link", "")
            company = None
            m = re.match(r"(.+?)\s+(?:at|@)\s+(.+?)(?:\s+[-|].*)?$", title)
            if m:
                title, company = m.group(1), m.group(2)
            jobs.append(_job(
                id=f"serper-{hashlib.md5(link.encode()).hexdigest()[:10]}", title=title,
                company=company, location=location, description=item.get("snippet", ""),
                url=link, source="web_search",
            ))
        return jobs

    return cached(f"serper:{query.lower()}:{','.join(skills).lower()}:{(location or '').lower()}", fetch)


# ── Combined search ───────────────────────────────────────────

_TECH_WORDS = {"developer", "engineer", "sde", "programmer", "software", "coder", "coding", "development"}


def _matches_query(job: dict, terms: list[str]) -> bool:
    hay = f"{job.get('title', '')} {job.get('company') or ''} {job.get('description', '')}".lower()
    return any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", hay) for t in terms)


def search_jobs(query: str = "", skills: list[str] | None = None, location: str | None = None,
                live: bool = True, limit: int = 50) -> list[dict]:
    """Search all sources, filter by the query, and de-duplicate."""
    skills = skills or []
    q = (query or "").strip().lower()
    terms = [q] if q else []
    if q and set(q.split()) & _TECH_WORDS:
        terms += sorted(_TECH_WORDS)

    jobs = sample_jobs()
    if live and settings.scraping_enabled:
        jobs += rss_jobs()
        if q:
            jobs += adzuna_jobs(q, location)
            jobs += serper_jobs(q, skills, location)

    if terms:
        # Live API results were already searched for the query; filter the rest.
        jobs = [j for j in jobs if j["source"] in ("adzuna", "web_search") or _matches_query(j, terms)]

    seen: set[str] = set()
    unique = []
    for j in jobs:
        keys = {f"{j['title'].lower()}@{(j.get('company') or '').lower()}"}
        # Sample roles share generic careers-page links, so only live URLs identify a job
        if j.get("url") and j["source"] != "sample":
            keys.add(j["url"])
        if keys & seen:
            continue
        seen |= keys
        unique.append(j)
    return unique[:limit]
