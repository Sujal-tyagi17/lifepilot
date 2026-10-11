"""Job sources with caching.

Sources, all optional except the sample set:
1. Sample roles (app/data/sample_roles.json): always available, works offline.
   These describe what a type of role typically asks for in India. They are
   not live openings and name no employer; the UI labels them "Sample".
2. Public RSS feeds that publish jobs for reuse (We Work Remotely, python.org).
3. Adzuna job search API (free developer tier) when ADZUNA_APP_ID/KEY are set.
4. Job postings on LinkedIn, Naukri, Indeed, foundit, Internshala and others,
   found through Google with Serper when SERPER_API_KEY is set.
5. Jooble job search API when JOOBLE_API_KEY is set.

Live sources are searched twice: in the user's state, and across India.

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
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Callable

import httpx

from app.config import settings
from app.jobs.locations import STATE_CITIES, find_place, find_state, is_remote

logger = logging.getLogger("lifepilot.jobs.sources")

SAMPLE_JOBS_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_roles.json"

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
        job = _job(
            id=j["id"], title=j["title"], company=j.get("company"), location=j.get("location"),
            description=j.get("description", ""), url=j.get("url"), source="sample",
            job_type=j.get("job_type"), country=j.get("country"),
            salary=j.get("salary"), salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
            currency="INR" if j.get("salary_min") else None,
        )
        job["family"] = j.get("family")
        jobs.append(job)
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
            "max_days_old": MAX_AGE_DAYS,
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
                _note(f"Adzuna · {location or 'India'}", f"failed: HTTP {resp.status_code}")
                return []
            results = resp.json().get("results", [])
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(f"Adzuna search failed: {e}")
            _note(f"Adzuna · {location or 'India'}", f"failed: {e.__class__.__name__}")
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
        _note(f"Adzuna · {location or 'India'}", f"{len(jobs)} listings found")
        return jobs

    return cached(f"adzuna:{query.lower()}:{(location or '').lower()}", fetch)


# ── 4. Job postings found through Google (Serper) ─────────────
#
# We only read Google's result titles and snippets through the Serper API; the
# job sites themselves are never scraped. Only links to a single posting are
# kept (search-listing pages like "15,000 Python jobs in Bangalore" are dropped).

JOB_SITES: list[tuple[str, str, str]] = [
    # (site: filter, regex a posting URL must match, display name)
    ("linkedin.com/jobs/view", r"linkedin\.com/jobs/view/", "LinkedIn"),
    ("naukri.com/job-listings", r"naukri\.com/job-listings-", "Naukri"),
    ("in.indeed.com/viewjob", r"indeed\.com/(?:viewjob|rc/clk|m/viewjob)", "Indeed"),
    ("foundit.in/job", r"foundit\.in/job/", "foundit"),
    ("internshala.com/job/detail", r"internshala\.com/(?:job|internship)/detail/", "Internshala"),
    ("cutshort.io/job", r"cutshort\.io/job/", "Cutshort"),
    ("instahyre.com/job", r"instahyre\.com/job-", "Instahyre"),
    # Company career pages on common hiring systems: real openings straight from the employer
    ("jobs.lever.co", r"jobs\.lever\.co/[^/]+/[0-9a-f-]{20,}", "Company site"),
    ("boards.greenhouse.io", r"greenhouse\.io/[^/]+/jobs/\d+", "Company site"),
    ("myworkdayjobs.com", r"myworkdayjobs\.com/.+/job/", "Company site"),
    ("apply.workable.com", r"apply\.workable\.com/[^/]+/j/", "Company site"),
]
# One Google query per group: simple queries return far more than one long OR of every site.
QUERY_GROUPS: list[list[str]] = [
    ["linkedin.com/jobs/view"],
    ["naukri.com/job-listings", "foundit.in/job"],
    ["in.indeed.com/viewjob", "internshala.com/job/detail"],
    ["jobs.lever.co", "boards.greenhouse.io", "myworkdayjobs.com", "apply.workable.com", "cutshort.io/job", "instahyre.com/job"],
]
_SUFFIX = re.compile(r"\s*[|\-–]\s*(linkedin|naukri(?:\.com)?|indeed(?:\.com)?|foundit(?:\.in)?|internshala|cutshort|instahyre|job details|careers?|lever|greenhouse|workday|workable)\s*$", re.IGNORECASE)
_YEARS_PART = re.compile(r"^\d+\s*(?:-|to)\s*\d+\s*(?:years?|yrs?)$|^\d+\+?\s*(?:years?|yrs?)$|^fresher", re.IGNORECASE)

# What each live source last reported, shown on the Jobs page so a missing or
# wrong key, a quota error or an empty search is visible instead of silent.
_status: dict[str, str] = {}


def _note(source: str, message: str) -> None:
    _status[source] = message


def source_status() -> dict[str, str]:
    return dict(_status)


CLOSED = re.compile(r"no longer accepting|not accepting applications|job (?:has )?expired|this job is closed|"
                    r"position (?:has been )?filled|applications? (?:are )?closed|expired on", re.IGNORECASE)
MAX_AGE_DAYS = 30


def age_days(text: str | None) -> float | None:
    """Days since a date like "3 days ago", "2 weeks ago", "10 months ago" or "Sep 14, 2026"."""
    if not text:
        return None
    low = text.lower()
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month|year)s?\s+ago", low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return n * {"minute": 1 / 1440, "hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}[unit]
    if re.search(r"\b(?:just now|today|yesterday)\b", low):
        return 1
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return (datetime.now() - datetime.strptime(text.strip()[:18], fmt)).days
        except ValueError:
            continue
    return None


def is_open(item: dict) -> bool:
    """False for a posting that says it is closed or is older than a month."""
    text = f"{item.get('title', '')} {item.get('snippet', '')}"
    if CLOSED.search(text):
        return False
    age = age_days(item.get("date"))
    if age is None:  # dates sometimes sit inside the snippet: "Posted 10 months ago"
        m = re.search(r"\d+\s*(?:minute|hour|day|week|month|year)s?\s+ago", item.get("snippet", "") or "", re.IGNORECASE)
        age = age_days(m.group(0)) if m else None
    return age is None or age <= MAX_AGE_DAYS


def posting_key(link: str) -> str:
    """One key per posting: in.linkedin.com and www.linkedin.com links to the same job match."""
    m = re.search(r"linkedin\.com/jobs/view/(?:[^/?]*-)?(\d{6,})", link)
    if m:
        return f"linkedin:{m.group(1)}"
    m = re.search(r"[?&]jk=([0-9a-f]+)", link)
    if m:
        return f"indeed:{m.group(1)}"
    return re.sub(r"^https?://(?:www\.|in\.|m\.)?", "", link.split("?")[0].split("#")[0]).rstrip("/").lower()


def _site_of(link: str) -> str | None:
    for _f, pattern, name in JOB_SITES:
        if re.search(pattern, link, re.IGNORECASE):
            return name
    return None


def parse_posting_title(title: str) -> tuple[str, str | None, str | None]:
    """(role, company, location) from a job posting's search-result title.

    Handles the usual shapes:
      "Acme hiring Data Analyst in Bengaluru, Karnataka, India | LinkedIn"
      "Data Analyst job at Acme in Pune - Internship"  /  "Data Analyst internship at Acme"
      "Data Analyst - Acme - 1 to 3 years - Bengaluru"  (Naukri)
      "Data Analyst - Acme - Pune, Maharashtra - Indeed.com"
    """
    t = title.strip()
    for _ in range(2):
        t = _SUFFIX.sub("", t).strip()
    m = re.match(r"^(.+?)\s+hiring\s+(.+?)(?:\s+in\s+(.+))?$", t, re.IGNORECASE)
    if m:
        return m.group(2).strip(), m.group(1).strip(), (m.group(3) or "").strip() or None
    m = re.match(r"^(.+?)\s+(?:job|internship)s?\s+(?:at|in)\s+(.+?)(?:\s+in\s+(.+))?$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip() or None
    parts = [p.strip() for p in re.split(r"\s+[-–—|]\s+", t) if p.strip()]
    if len(parts) == 1:
        m = re.match(r"^(.+?)\s+(?:at|@)\s+(.+)$", t)
        return (m.group(1), m.group(2), None) if m else (t, None, None)
    role, rest = parts[0], [p for p in parts[1:] if not _YEARS_PART.match(p)]
    place = next((p for p in reversed(rest) if find_state(p) or is_remote(p)), None)
    company = next((p for p in rest if p != place), None)
    return role, company, place


def _place_terms(location: str | None) -> str:
    """Words for Google: the state plus its two biggest cities, or India."""
    if not location:
        return "India"
    cities = [c.title() for c in STATE_CITIES.get(location, [])[:2]]
    return "(" + " OR ".join(f'"{x}"' for x in [location, *cities]) + ")"


def _serper(q: str) -> list[dict] | str:
    """Organic results, or an error message."""
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                # tbs=qdr:m: only pages Google saw change in the last month, so old, closed posts drop out
                json={"q": q, "gl": "in", "hl": "en", "num": 10, "tbs": "qdr:m"},
            )
    except httpx.HTTPError as e:
        return f"could not connect ({e.__class__.__name__})"
    if resp.status_code != 200:
        hint = {401: "key not accepted", 403: "key not accepted", 429: "free searches used up"}.get(resp.status_code, "")
        return f"HTTP {resp.status_code}" + (f": {hint}" if hint else "")
    try:
        return resp.json().get("organic", [])
    except ValueError:
        return "bad response"


def web_job_postings(query: str, location: str | None, fresher: bool = False) -> list[dict]:
    if not settings.serper_api_key:
        return []

    def fetch() -> list[dict]:
        place = _place_terms(location)
        # Freshers: leave senior, lead and manager roles out of the search itself
        level = " -senior -sr -lead -principal -staff -manager -architect -director" if fresher else ""
        queries = [f'{" OR ".join(f"site:{x}" for x in group)} "{query}" {place}{level}' for group in QUERY_GROUPS]
        with ThreadPoolExecutor(max_workers=len(queries)) as pool:
            answers = list(pool.map(_serper, queries))
        errors = [a for a in answers if isinstance(a, str)]
        organic = [item for a in answers if isinstance(a, list) for item in a]

        jobs, seen, closed = [], set(), 0
        for item in organic:
            link = item.get("link", "")
            site = _site_of(link)
            key = posting_key(link)
            if not site or key in seen:
                continue  # a listing page, an unrelated result, or one we already have
            seen.add(key)
            if not is_open(item):
                closed += 1
                continue
            role, company, where = parse_posting_title(item.get("title", ""))
            snippet = item.get("snippet", "") or ""
            where = where or find_place(snippet) or (location if location and find_state(snippet) == location else None)
            if site == "Company site" and not company:
                company = re.sub(r"^https?://[^/]+/([^/]+).*", r"\1", link).replace("-", " ").title()
            job = _job(
                id=f"web-{hashlib.md5(link.encode()).hexdigest()[:12]}", title=role, company=company,
                location=where, description=snippet, url=link, source="web_job",
                job_type="Remote" if is_remote(f"{where} {snippet}") else None,
                country="India" if find_state(where) or find_state(snippet) else None,
            )
            job["site"] = site
            job["posted"] = item.get("date")
            jobs.append(job)
        if errors and not organic:
            logger.warning(f"Serper job search failed: {errors[0]}")
            _note(f"Google · {location or 'India'}", f"failed: {errors[0]}")
        else:
            _note(f"Google · {location or 'India'}", f"{len(jobs)} open postings found"
                  + (f", {closed} closed or old ones left out" if closed else ""))
        return jobs

    return cached(f"webjobs:{query.lower()}:{(location or 'india').lower()}:{int(fresher)}", fetch)


# ── 4b. Google Jobs through SerpApi (free plan: serpapi.com) ──

def google_jobs(query: str, location: str | None, fresher: bool = False) -> list[dict]:
    """Structured listings from Google's job search: title, company, place, full description."""
    if not settings.serpapi_key:
        return []

    def fetch() -> list[dict]:
        params = {"engine": "google_jobs", "q": f"{query} fresher" if fresher else query, "location": f"{location}, India" if location else "India",
                  "gl": "in", "hl": "en", "api_key": settings.serpapi_key}
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get("https://serpapi.com/search.json", params=params)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            _note(f"Google Jobs · {location or 'India'}", f"failed: {e.__class__.__name__}")
            return []
        if resp.status_code != 200 or data.get("error"):
            logger.warning(f"SerpApi Google Jobs failed: {data.get('error') or resp.status_code}")
            _note(f"Google Jobs · {location or 'India'}", f"failed: {data.get('error') or resp.status_code}")
            return []
        jobs = []
        for r in data.get("jobs_results", []):
            ext = r.get("detected_extensions") or {}
            if (age_days(ext.get("posted_at")) or 0) > MAX_AGE_DAYS:
                continue
            apply = (r.get("apply_options") or [{}])[0]
            link = apply.get("link") or r.get("share_link")
            via = re.sub(r"^via\s+", "", r.get("via") or "", flags=re.IGNORECASE) or None
            job = _job(
                id=f"gj-{hashlib.md5((r.get('job_id') or link or r.get('title', '')).encode()).hexdigest()[:12]}",
                title=r.get("title", ""), company=r.get("company_name"), location=r.get("location"),
                description=r.get("description", ""), url=link, source="google_jobs",
                job_type="Remote" if ext.get("work_from_home") else ext.get("schedule_type"),
                country="India", salary=ext.get("salary"),
            )
            job["site"] = apply.get("title") or via
            job["posted"] = ext.get("posted_at")
            jobs.append(job)
        _note(f"Google Jobs · {location or 'India'}", f"{len(jobs)} listings found")
        return jobs

    return cached(f"gjobs:{query.lower()}:{(location or 'india').lower()}:{int(fresher)}", fetch)


# ── 5. Jooble (free key on request: jooble.org/api/about) ────

def jooble_jobs(query: str, location: str | None) -> list[dict]:
    if not settings.jooble_api_key:
        return []

    def fetch() -> list[dict]:
        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(f"https://jooble.org/api/{settings.jooble_api_key}",
                                   json={"keywords": query, "location": location or "India"})
            if resp.status_code != 200:
                logger.warning(f"Jooble search failed: HTTP {resp.status_code}")
                _note(f"Jooble · {location or 'India'}", f"failed: HTTP {resp.status_code}")
                return []
            results = resp.json().get("jobs", [])
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(f"Jooble search failed: {e}")
            _note(f"Jooble · {location or 'India'}", f"failed: {e.__class__.__name__}")
            return []
        jobs = []
        for r in results[:40]:
            link = r.get("link") or ""
            if not is_open({"title": r.get("title"), "snippet": r.get("snippet"), "date": (r.get("updated") or "")[:10]}):
                continue
            desc = re.sub(r"<[^>]+>", " ", r.get("snippet") or "")
            job = _job(
                id=f"jooble-{r.get('id') or hashlib.md5(link.encode()).hexdigest()[:12]}", title=r.get("title", ""),
                company=r.get("company"), location=r.get("location"), description=desc, url=link or None,
                source="jooble", job_type=r.get("type") or None, country="India",
                salary=(r.get("salary") or "").strip() or None,
            )
            job["site"] = r.get("source")
            job["posted"] = (r.get("updated") or "")[:10] or None
            jobs.append(job)
        _note(f"Jooble · {location or 'India'}", f"{len(jobs)} listings found")
        return jobs

    return cached(f"jooble:{query.lower()}:{(location or 'india').lower()}", fetch)


def live_sources() -> list[str]:
    """Names of the live job sources configured on this server."""
    out = []
    if settings.adzuna_app_id and settings.adzuna_app_key:
        out.append("Adzuna")
    if settings.jooble_api_key:
        out.append("Jooble")
    if settings.serpapi_key:
        out.append("Google Jobs")
    if settings.serper_api_key:
        out.append("Google (LinkedIn, Naukri, Indeed, company sites)")
    return out


# ── Combined search ───────────────────────────────────────────

LIVE_API_SOURCES = ("adzuna", "jooble", "web_job", "google_jobs")
_TECH_WORDS = {"developer", "engineer", "sde", "programmer", "software", "coder", "coding", "development"}


def _matches_query(job: dict, terms: list[str]) -> bool:
    hay = f"{job.get('title', '')} {job.get('company') or ''} {job.get('description', '')}".lower()
    return any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", hay) for t in terms)


def search_jobs(query: str = "", skills: list[str] | None = None, location: str | None = None,
                live: bool = True, limit: int = 50, filter_samples: bool = True,
                include_rss: bool = True, fresher: bool = False) -> list[dict]:
    """Search all sources, filter by the query, and de-duplicate."""
    skills = skills or []
    q = (query or "").strip().lower()
    terms = [q] if q else []
    if q and set(q.split()) & _TECH_WORDS:
        terms += sorted(_TECH_WORDS)

    jobs = sample_jobs()
    if live and settings.scraping_enabled:
        if q:
            # The user's state first, then all of India, so nearby jobs are
            # never crowded out by the big cities.
            scopes = [location, None] if location and location.lower() not in ("india", "remote") else [None]
            sources_ = (adzuna_jobs, jooble_jobs, partial(web_job_postings, fresher=fresher), partial(google_jobs, fresher=fresher))
            calls = [(fn, where) for where in scopes for fn in sources_]
            with ThreadPoolExecutor(max_workers=len(calls)) as pool:  # sources are slow; ask them all at once
                for found in pool.map(lambda c: c[0](q, c[1]), calls):
                    jobs += found
        if include_rss:
            jobs += rss_jobs()  # worldwide remote jobs; left out of matching for India

    if terms:
        # Live API results were already searched for the query. RSS feeds are
        # filtered here. Sample roles are kept only when `filter_samples` is set
        # (plain search); matching scores all of them and decides relevance itself.
        keep = set(LIVE_API_SOURCES) | (set() if filter_samples else {"sample"})
        jobs = [j for j in jobs if j["source"] in keep or _matches_query(j, terms)]

    seen: set[str] = set()
    unique = []
    for j in jobs:
        keys = {f"{j['title'].lower()}@{(j.get('company') or '').lower()}@{(j.get('location') or '').lower()}"}
        # Sample roles share generic careers-page links, so only live URLs identify a job
        if j.get("url") and j["source"] != "sample":
            keys.add(posting_key(j["url"]))
        if keys & seen:
            continue
        seen |= keys
        unique.append(j)
    # The same post found twice, once without the company name: keep the fuller one
    def _tp(j):
        return j["title"].lower(), (j.get("location") or "").lower().split(",")[0].strip()
    named = {_tp(j) for j in unique if j.get("company") and j["source"] != "sample"}
    unique = [j for j in unique if j.get("company") or j["source"] == "sample" or _tp(j) not in named]
    return unique[:limit] if limit else unique
