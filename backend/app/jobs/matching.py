"""Job fit scoring with a visible breakdown.

Replaces the old score that started every job at 50% and added points for
substring hits. Here every point is earned from a signal we can show:

    signal      weight  value
    skills      0.45    share of the job's skills the user has
    role        0.30    1 if the target role is in the title, 0.5 if only in the text
    education   0.15    1 if the user's level meets the job's stated requirement
    field       0.10    1 if the user's field of study appears in the job

Signals with no data (e.g. a job that names no skills) are left out and the
remaining weights are re-normalised, so missing data neither helps nor hurts.
Phase 2/3 replaces these hand-set weights with weights learned from labelled
resume-job pairs; the breakdown format stays the same.
"""
from __future__ import annotations

import re

from app.jobs.skills import extract_skills, normalise_user_skills

WEIGHTS = {"skills": 0.45, "role": 0.30, "education": 0.15, "field": 0.10}

_LEVELS = {"9th": 0, "10th": 1, "11th": 2, "12th": 3, "diploma": 4, "undergraduate": 5, "postgraduate": 6, "phd": 7}
_REQUIREMENTS = [
    # (pattern, required level, label) — checked from highest to lowest
    (r"\bph\.?\s?d\b|\bdoctorate\b", 7, "PhD"),
    (r"\bmaster'?s\b|\bm\.?\s?tech\b|\bm\.?\s?sc\b|\bmba\b|\bpost[\s-]?graduat", 6, "Master's degree"),
    (r"\bbachelor'?s\b|\bb\.?\s?tech\b|\bb\.?\s?e\b|\bb\.?\s?sc\b|\bb\.?\s?com\b|\bgraduate degree\b|\bundergraduate degree\b|\bdegree in\b", 5, "Bachelor's degree"),
    (r"\bdiploma\b", 4, "Diploma"),
    (r"\b12th\b|\bhigher secondary\b|\bclass xii\b", 3, "12th pass"),
]


def required_education(text: str) -> tuple[int, str] | None:
    low = (text or "").lower()
    for pattern, level, label in _REQUIREMENTS:
        if re.search(pattern, low):
            return level, label
    return None


def _words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+#.]+", s.lower()) if len(w) > 1]


def _role_signal(desired: str, title: str, description: str) -> tuple[float | None, str | None]:
    words = _words(desired)
    if not words:
        return None, None
    t, d = title.lower(), description.lower()
    if all(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", t) for w in words):
        return 1.0, f"Title matches your target role '{desired}'"
    if all(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", d) for w in words):
        return 0.5, f"Description mentions '{desired}'"
    return 0.0, None


def score_job(job: dict, profile: dict, resume_text: str = "", desired_role: str = "",
              user_skills: list[str] | None = None) -> dict:
    title = job.get("title", "")
    description = job.get("description", "")
    job_text = f"{title}\n{description}"

    have = set(normalise_user_skills(user_skills)) | set(extract_skills(resume_text))
    job_skills = extract_skills(job_text)
    matched = [s for s in job_skills if s in have]
    missing = [s for s in job_skills if s not in have]

    signals: dict[str, float | None] = {}
    reasons: list[str] = []
    unmet: list[str] = []

    # Skills
    if job_skills:
        signals["skills"] = len(matched) / len(job_skills)
        if matched:
            reasons.append(f"You have {len(matched)} of {len(job_skills)} skills it asks for: {', '.join(matched)}")
        if missing:
            unmet.append(f"Skills to learn: {', '.join(missing)}")
    else:
        signals["skills"] = None

    # Role
    role_value, role_reason = _role_signal(desired_role, title, description)
    signals["role"] = role_value
    if role_reason:
        reasons.append(role_reason)

    # Education
    eligible = True
    req = required_education(job_text)
    level_name = (profile.get("education_level") or "").strip()
    user_level = _LEVELS.get(level_name.lower())
    if req and user_level is not None:
        ok = user_level >= req[0]
        signals["education"] = 1.0 if ok else 0.0
        if ok:
            reasons.append(f"Your education ({level_name}) meets the requirement ({req[1]})")
        else:
            eligible = False
            unmet.append(f"Asks for {req[1]} (you: {level_name})")
    else:
        signals["education"] = None

    # Field of study
    field = (profile.get("field_of_study") or "").strip()
    if field:
        field_words = _words(field)
        hit = bool(field_words) and all(
            re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", job_text.lower()) for w in field_words
        )
        signals["field"] = 1.0 if hit else 0.0
        if hit:
            reasons.append(f"Related to your field of study ({field})")
    else:
        signals["field"] = None

    known = {k: v for k, v in signals.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in known)
    fit = sum(WEIGHTS[k] * v for k, v in known.items()) / total_weight if total_weight else 0.0

    breakdown = [
        {
            "signal": k,
            "value": round(v, 2),
            "weight": round(WEIGHTS[k] / total_weight, 2),
            "points": round(100 * WEIGHTS[k] * v / total_weight, 1),
        }
        for k, v in known.items()
    ]

    return {
        "fit_score": round(fit, 2),
        "fit_breakdown": breakdown,
        "eligible": eligible,
        "reasons": reasons,
        "unmet": unmet,
        "skills_required": job_skills,
        "skills_matched": matched,
        "skills_missing": missing,
        "data_coverage": round(total_weight, 2),
    }


def rank_jobs(jobs: list[dict], profile: dict, resume_text: str = "", desired_role: str = "",
              user_skills: list[str] | None = None) -> list[dict]:
    ranked = []
    for job in jobs:
        ranked.append({**job, **score_job(job, profile, resume_text, desired_role, user_skills)})
    ranked.sort(key=lambda j: (not j["eligible"], -j["fit_score"], -len(j["skills_matched"])))
    return ranked
