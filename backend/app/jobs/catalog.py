"""Skill and role-family catalogue (app/jobs/data/*.json).

skills_meta.json  — per skill: learning effort in weeks (at 8 hours a week),
                    prerequisites, free resources, kind.
role_families.json — per job family: words that identify it, its core skills,
                    a portfolio project and interview topics.

`classify_role` uses the trained classifier from app/ml (TF-IDF + linear SVM)
and falls back to the keyword rules; callers only see (family, confidence).
"""
from __future__ import annotations

import json
import re
import urllib.parse
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def skills_meta() -> dict:
    with open(DATA / "skills_meta.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def families() -> dict:
    with open(DATA / "role_families.json", encoding="utf-8") as f:
        return json.load(f)


def skill_info(skill: str) -> dict:
    """Catalogue entry for a skill; unknown skills get a sensible default."""
    meta = skills_meta().get(skill)
    if meta:
        return meta
    q = urllib.parse.quote(skill)
    return {
        "weeks": 3, "prereqs": [], "kind": "other",
        "resources": [
            {"provider": "SWAYAM", "title": f"Free {skill} courses on SWAYAM (Govt. of India)", "url": f"https://swayam.gov.in/explorer?searchText={q}"},
            {"provider": "YouTube", "title": f"{skill} tutorials", "url": f"https://www.youtube.com/results?search_query={q}+tutorial"},
        ],
    }


def family_label(key: str | None) -> str | None:
    return families().get(key, {}).get("label") if key else None


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def classify_role(title: str, description: str = "", skills: list[str] | None = None) -> tuple[str | None, float]:
    """Job family and a 0–1 confidence: the trained classifier (app/ml) when its
    model file is present and sure enough, else the keyword rules below."""
    from app.ml.predict import role_family
    ml = role_family(title, description)
    if ml and ml[1] >= 0.35:
        return ml
    return classify_role_rules(title, description, skills)


def classify_role_rules(title: str, description: str = "", skills: list[str] | None = None) -> tuple[str | None, float]:
    """Best-matching job family by keywords, and a 0–1 confidence.

    Words in the title count three times as much as words in the description;
    the job's skills break ties using each family's core skills.
    """
    t, d = (title or "").lower(), (description or "").lower()
    best, best_score = None, 0.0
    for key, fam in families().items():
        score = 0.0
        for kw in fam["keywords"]:
            if _has(t, kw):
                score += 3 + len(kw) / 20   # longer phrases are more specific
            elif d and _has(d, kw):
                score += 1
        if skills:
            score += 0.4 * len(set(skills) & set(fam["core"]))
        if score > best_score:
            best, best_score = key, score
    if best_score < 1:
        return None, 0.0
    return best, round(min(1.0, best_score / 5), 2)
