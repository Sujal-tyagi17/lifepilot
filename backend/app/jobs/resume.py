"""Read a resume: sections, skills with strength, experience, degree.

Strength says how much evidence the resume gives for a skill:
    3  work     used in a job or internship (Experience section)
    2  project  used in a project, or learned in a course/certification
    1  listed   only named in a skills list (or typed in the form)
"""
from __future__ import annotations

import re
from datetime import date

from app.jobs.catalog import skills_meta
from app.jobs.skills import extract_skills_fuzzy, normalise_user_skills

STRENGTH_LABEL = {3: "work", 2: "project", 1: "listed"}

SECTION_PATTERNS = {
    "experience": r"(work\s+)?experience|employment|work history|professional experience|internships?",
    "projects": r"(academic\s+|personal\s+|key\s+)?projects?",
    "skills": r"(technical\s+|key\s+|core\s+)?skills|technologies|tools|tech stack|competencies",
    "education": r"education|academics?|academic (background|details)|qualifications?",
    "certifications": r"certifications?|courses|trainings?|licen[cs]es",
    "summary": r"summary|objective|profile|about me",
    "achievements": r"achievements|awards|accomplishments|extra.?curricular",
}
SECTION_WEIGHT = {"experience": 3, "projects": 2, "certifications": 2}

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE = r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*)?((?:19|20)\d{2})"
_RANGE = re.compile(_DATE + r"\s*(?:-|–|—|to)\s*(?:" + _DATE + r"|(present|current|now|till date|ongoing))", re.IGNORECASE)

DEGREES = [
    (r"\bph\.?\s?d\b", 7, "PhD"),
    (r"\bm\.?\s?tech\b|\bm\.?\s?e\b|\bm\.?\s?sc\b|\bmca\b|\bmba\b|\bm\.?\s?com\b|\bmaster'?s\b|\bm\.?\s?a\b(?!\w)", 6, "Master's degree"),
    (r"\bb\.?\s?tech\b|\bb\.?\s?e\b|\bb\.?\s?sc\b|\bbca\b|\bbba\b|\bb\.?\s?com\b|\bb\.?\s?a\b(?!\w)|\bbachelor'?s?\b|\bb\.?\s?ed\b|\bgnm\b", 5, "Bachelor's degree"),
    (r"\bdiploma\b|\bpolytechnic\b|\biti\b", 4, "Diploma"),
    (r"\b12th\b|\bhsc\b|\bclass xii\b|\bhigher secondary\b|\bintermediate\b", 3, "12th"),
]


def _heading(line: str) -> str | None:
    s = line.strip().strip(":|-•*").strip()
    if not s or len(s) > 40 or sum(c.isdigit() for c in s) > 2:
        return None
    low = s.lower()
    for name, pat in SECTION_PATTERNS.items():
        if re.fullmatch(rf"(?:{pat})\s*:?", low):
            return name
    return None


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"_top": []}
    current = "_top"
    for line in (text or "").splitlines():
        name = _heading(line)
        if name:
            current = name
            sections.setdefault(current, [])
            continue
        # "Projects: chat app in React" — a heading and its content on one line
        head, sep, rest = line.partition(":")
        inline = _heading(head) if sep and rest.strip() else None
        if inline:
            current = inline
            sections.setdefault(current, []).append(rest.strip())
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip() or k != "_top"}


def _months_between(m1, y1, m2, y2, open_end) -> int:
    start = (int(y1), _MONTHS.get((m1 or "jan")[:3].lower(), 1))
    if open_end:
        t = date.today(); end = (t.year, t.month)
    else:
        end = (int(y2), _MONTHS.get((m2 or "dec")[:3].lower(), 12))
    return max(0, (end[0] - start[0]) * 12 + end[1] - start[1] + 1)


def experience(text_experience: str) -> tuple[float, int]:
    """(years of work, number of internships) from the Experience section."""
    years, internships = 0.0, 0
    lines = text_experience.splitlines()
    for i, line in enumerate(lines):
        low = line.lower()
        context = " ".join(lines[max(0, i - 1): i + 2]).lower()
        m = _RANGE.search(line)
        if m:
            months = _months_between(m.group(1), m.group(2), m.group(3), m.group(4), bool(m.group(5)))
            if "intern" in context or "trainee" in context:
                internships += 1
            else:
                years += months / 12
        elif re.search(r"\bintern(ship)?\b", low) and not m:
            pass
    stated = re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", text_experience.lower())
    if stated:
        years = max(years, max(float(s) for s in stated))
    if internships == 0:
        internships = len(re.findall(r"\bintern(?:ship)?\b", text_experience.lower())) and 1 or 0
    return round(min(years, 40), 1), internships


def degree(text: str) -> tuple[int, str] | None:
    low = (text or "").lower()
    for pat, level, label in DEGREES:
        if re.search(pat, low):
            return level, label
    return None


def analyse_resume(text: str = "", typed_skills: list[str] | None = None) -> dict:
    """Everything the matcher and planner need to know about the candidate."""
    text = text or ""
    sections = split_sections(text)
    strength: dict[str, int] = {}
    where: dict[str, str] = {}

    def give(skills, level, section):
        for s in skills:
            if level > strength.get(s, 0):
                strength[s] = level
                where[s] = section

    found_any = False
    for name, body in sections.items():
        level = SECTION_WEIGHT.get(name, 1)
        skills = extract_skills_fuzzy(body)   # typos like "Pyhton" still count
        found_any = found_any or bool(skills)
        give(skills, level, name)

    # Using a skill proves its foundations: FastAPI at work means Python at work.
    def implied(skill, level, depth=0):
        for pre in skills_meta().get(skill, {}).get("prereqs", []):
            if level > strength.get(pre, 0) and depth < 4:
                strength[pre] = level
                where[pre] = f"via {skill}"
                implied(pre, level, depth + 1)

    for s, level in list(strength.items()):
        if level >= 2:
            implied(s, level)
    in_resume = set(strength)

    typed = normalise_user_skills(typed_skills)
    typed_only = [s for s in typed if s not in in_resume]
    for s in typed_only:
        strength.setdefault(s, 1); where.setdefault(s, "form")

    years, internships = experience(sections.get("experience", ""))
    deg = degree(sections.get("education", "") or text)

    return {
        "has_resume": bool(text.strip()),
        "sections": sorted(k for k in sections if k != "_top"),
        "skills": [{"name": s, "strength": strength[s], "evidence": STRENGTH_LABEL[strength[s]], "where": where[s]}
                   for s in sorted(strength, key=lambda k: (-strength[k], k.lower()))],
        "strength": strength,
        "typed_only": typed_only,
        "years": years,
        "internships": internships,
        "degree": {"level": deg[0], "label": deg[1]} if deg else None,
        "words": len(text.split()),
    }


def public_summary(r: dict) -> dict:
    """What the UI shows under "What we read from your resume"."""
    return {k: r[k] for k in ("has_resume", "sections", "skills", "typed_only", "years", "internships", "degree", "words")}
