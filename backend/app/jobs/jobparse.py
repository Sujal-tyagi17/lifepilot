"""Read a job post: must-have vs good-to-have skills, experience, education, family.

Job posts mark optional skills with words like "good to have", "preferred" or
"bonus". Every sentence is checked for those words: skills in a sentence that
has them are good-to-have, everything else (and anything in the title) is a
must-have. A skill named in both places counts as a must-have.
"""
from __future__ import annotations

import re

from app.jobs.catalog import classify_role, family_label
from app.jobs.skills import extract_skills

NICE_CUES = re.compile(
    r"good[\s-]to[\s-]have|nice[\s-]to[\s-]have|\bpreferred\b|\bpreferably\b|\bplus\b|\bbonus\b|"
    r"\bdesirable\b|\badvantage\b|\boptional\b|added advantage|would be great",
    re.IGNORECASE,
)

EDUCATION = [
    # (pattern, level, label) — checked from highest to lowest
    (r"\bph\.?\s?d\b|\bdoctorate\b", 7, "PhD"),
    (r"\bmaster'?s\b|\bm\.?\s?tech\b|\bm\.?\s?sc\b|\bmba\b|\bpost[\s-]?graduat", 6, "Master's degree"),
    (r"\bbachelor'?s\b|\bb\.?\s?tech\b|\bb\.?\s?e\b|\bb\.?\s?sc\b|\bb\.?\s?com\b|\bb\.?\s?ed\b|\bgraduate degree\b|"
     r"\bundergraduate degree\b|\bdegree in\b|\bgraduation\b|\bany graduate\b|\bgnm\b", 5, "Bachelor's degree"),
    (r"\bdiploma\b|\biti\b", 4, "Diploma"),
    (r"\b12th\b|\bhigher secondary\b|\bclass xii\b", 3, "12th pass"),
    (r"\b10th\b|\bmatriculat", 1, "10th pass"),
]

_YEARS = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:(?:-|–|to)\s*(\d+(?:\.\d+)?)|\+)?\s*(?:years?|yrs?)", re.IGNORECASE)


def required_education(text: str) -> tuple[int, str] | None:
    """Lowest qualification the post accepts ("B.Com or MBA" accepts a B.Com)."""
    low = (text or "").lower()
    found = [(level, label) for pattern, level, label in EDUCATION if re.search(pattern, low)]
    return min(found) if found else None


def required_years(text: str) -> tuple[float, float | None] | None:
    """(minimum, maximum) years of experience asked for, or None if not stated."""
    low = (text or "").lower()
    if re.search(r"\bfreshers?\b|\bno experience\b|\bentry[\s-]level\b|\b0\s*years?\b", low):
        base = (0.0, None)
    else:
        base = None
    for sentence in re.split(r"(?<=[.;\n])\s+", low):
        if "experience" not in sentence and "exp" not in sentence:
            continue
        m = _YEARS.search(sentence)
        if m:
            lo = float(m.group(1))
            hi = float(m.group(2)) if m.group(2) else None
            if lo > 30:
                continue
            return lo, hi
    return base


# Seniority words in a job title and the experience they usually mean.
SENIORITY = [
    (r"\b(?:director|vp|vice president|head of)\b", 10, "Director-level role"),
    (r"\b(?:principal|staff|architect)\b", 8, "Principal-level role"),
    (r"\b(?:lead|manager)\b", 5, "Lead or manager role"),
    (r"\b(?:senior|sr\.?)\b|\b(?:engineer|developer|analyst)\s+(?:ii|iii|iv|2|3)\b", 4, "Senior role"),
]
JUNIOR = re.compile(r"\b(?:junior|jr\.?|fresher|freshers|graduate|trainee|intern|internship|entry[\s-]level|associate|apprentice)\b", re.IGNORECASE)


def seniority(title: str) -> tuple[int, str] | None:
    """(years usually needed, label) when the title says senior/lead/principal…"""
    low = (title or "").lower()
    if JUNIOR.search(low):
        return None
    for pattern, years, label in SENIORITY:
        if re.search(pattern, low):
            return years, label
    return None


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.;\n])\s+|\n", text or "") if s.strip()]


def _groups(sentence: str) -> list[list[str]]:
    """Requirement units in a sentence. "Django or FastAPI" is one unit either skill satisfies."""
    units: list[list[str]] = []
    for chunk in re.split(r",|;|\band\b|&", sentence):
        skills = extract_skills(chunk)
        if not skills:
            continue
        if len(skills) > 1 and re.search(r"\bor\b|/", chunk):
            units.append(skills)
        else:
            units.extend([s] for s in skills)
    # skills the chunking missed (e.g. split inside a skill name like "R&D")
    seen = {s for u in units for s in u}
    units.extend([s] for s in extract_skills(sentence) if s not in seen)
    return units


def analyse_job(job: dict) -> dict:
    title = job.get("title", "") or ""
    description = job.get("description", "") or ""
    must_units: list[list[str]] = []
    nice_units: list[list[str]] = []

    def add(bucket, units):
        taken = {s for u in must_units + nice_units for s in u}
        for u in units:
            u = [s for s in u if s not in taken]
            if u:
                bucket.append(u)
                taken.update(u)

    add(must_units, [[s] for s in extract_skills(title)])
    for sentence in _sentences(description):
        if NICE_CUES.search(sentence):
            continue
        add(must_units, _groups(sentence))
    for sentence in _sentences(description):
        if NICE_CUES.search(sentence):
            add(nice_units, _groups(sentence))
    must = [s for u in must_units for s in u]
    nice = [s for u in nice_units for s in u]

    family = job.get("family")
    confidence = 1.0 if family else 0.0
    if not family:
        family, confidence = classify_role(title, description, must + nice)

    years = required_years(description)
    senior = seniority(title)
    if senior and (not years or years[0] < senior[0]):
        years = (float(senior[0]), years[1] if years else None)
    edu = required_education(f"{title}\n{description}")
    return {
        "must": must,
        "nice": nice,
        "must_units": must_units,
        "nice_units": nice_units,
        "min_years": years[0] if years else None,
        "max_years": years[1] if years else None,
        "education": edu,
        "family": family,
        "family_label": family_label(family),
        "family_confidence": confidence,
        "seniority": senior[1] if senior else None,
        "junior": bool(JUNIOR.search(title)),
    }
