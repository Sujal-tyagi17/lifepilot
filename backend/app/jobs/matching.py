"""Job fit scoring (v2): uses the profile form, the resume and the job post.

Every point is earned from a signal we can show the user:

    signal      weight  value
    must        0.40    must-have skills you have, weighted by how well the resume proves them
    nice        0.10    the same for good-to-have skills
    role        0.20    1 if the title matches your target role, 0.8 if it is the same kind of role
    experience  0.10    your years (internships count half a year) against the years asked for
    education   0.10    1 if your qualification meets the lowest one the job accepts
    field       0.05    1 if your field of study appears in the job
    text        0.05    how close the resume's wording is to the job post

Proof factor for a skill: used at work 1.0, in a project or course 0.85, only
listed 0.6. Signals with no data are left out and the remaining weights are
re-normalised, so missing data neither helps nor hurts.

Phase 3 swaps the hand-set weights for weights learned from labelled pairs;
the breakdown format stays the same.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from app.jobs.catalog import classify_role, families, family_label, skill_info
from app.jobs.locations import location_rank
from app.jobs.jobparse import analyse_job, required_education  # noqa: F401  (re-exported)
from app.jobs.resume import analyse_resume, public_summary

WEIGHTS = {"must": 0.40, "nice": 0.10, "role": 0.20, "experience": 0.10,
           "education": 0.10, "field": 0.05, "text": 0.05}
PROOF = {3: 1.0, 2: 0.85, 1: 0.6}

_LEVELS = {"9th": 0, "10th": 1, "11th": 2, "12th": 3, "diploma": 4, "undergraduate": 5, "postgraduate": 6, "phd": 7}
_STOP = set("""a an and are as at be by for from has have in is it its of on or our the their this to was we will with
you your who what can able work working team using use used across into about job role candidate candidates
requirements required good nice plus years year experience education degree skills skill etc also""".split())


def _words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+#.]+", (s or "").lower()) if len(w) > 1]


def _has_all(words: list[str], text: str) -> bool:
    return bool(words) and all(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text) for w in words)


def _bag(text: str) -> Counter:
    return Counter(w.strip(".") for w in _words(text) if w.strip(".") not in _STOP and len(w.strip(".")) > 2)


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b[k] for k, v in a.items() if k in b)
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


# ── The candidate ─────────────────────────────────────────────

def infer_family(strength: dict[str, int]) -> str | None:
    """The job family whose core skills the candidate covers best (needs 2 or more)."""
    best, best_score = None, 0.0
    for key, fam in families().items():
        hits = [s for s in fam["core"] if s in strength]
        score = sum(strength[s] for s in hits)
        if len(hits) >= 2 and score > best_score:
            best, best_score = key, score
    return best


def candidate(profile: dict | None = None, resume_text: str = "", desired_role: str = "",
              user_skills: list[str] | None = None, learned: list[str] | None = None) -> dict:
    """Everything about the user that scoring needs, computed once per request.

    `learned` are skills the user has ticked off in a roadmap; they count as
    project-level proof, which is how the plan page shows the fit going up.
    """
    profile = profile or {}
    r = analyse_resume(resume_text, user_skills)
    strength = dict(r["strength"])
    for s in learned or []:
        strength[s] = max(strength.get(s, 0), 2)

    level_name = (profile.get("education_level") or "").strip()
    level = _LEVELS.get(level_name.lower())
    if level is None and r["degree"]:
        level, level_name = r["degree"]["level"], r["degree"]["label"]

    desired = (desired_role or "").strip()
    if desired:
        target, how = classify_role(desired)[0], "role"
    else:
        target, how = infer_family(strength), "resume"

    return {
        "resume": r,
        "strength": strength,
        "level": level,
        "level_name": level_name,
        "field": (profile.get("field_of_study") or "").strip(),
        "state": (profile.get("state") or "").strip() or None,
        "desired": desired,
        "target_family": target,
        "target_from": how if target else None,
        "years": r["years"] + 0.5 * min(r["internships"], 2),
        "has_resume": r["has_resume"],
        "bag": _bag(resume_text),
    }


# ── One job ───────────────────────────────────────────────────

def _cheapest(unit: list[str]) -> str:
    return min(unit, key=lambda s: (skill_info(s)["weeks"], unit.index(s)))


def _units(units: list[list[str]], strength: dict) -> tuple[float | None, list[str], list[str], dict]:
    """(signal, skills you have, skills to learn, alternatives for a skill to learn)."""
    if not units:
        return None, [], [], {}
    total, have, missing, alts = 0.0, [], [], {}
    for unit in units:
        best = max(unit, key=lambda s: strength.get(s, 0))
        if strength.get(best, 0):
            total += PROOF[strength[best]]
            have.append(best)
        else:
            pick = _cheapest(unit)
            missing.append(pick)
            if len(unit) > 1:
                alts[pick] = [s for s in unit if s != pick]
    return total / len(units), have, missing, alts


def score_with(job: dict, cand: dict, parsed: dict | None = None) -> dict:
    a = parsed or analyse_job(job)
    title = job.get("title", "") or ""
    job_text = f"{title}\n{job.get('description', '') or ''}"
    low = job_text.lower()
    strength = cand["strength"]
    signals: dict[str, float | None] = {}
    reasons: list[str] = []
    unmet: list[str] = []

    # Skills
    signals["must"], have_must, missing, alts = _units(a["must_units"], strength)
    signals["nice"], have_nice, missing_nice, _ = _units(a["nice_units"], strength)
    weak = [s for s in have_must if strength.get(s) == 1]
    proven = [s for s in have_must if strength.get(s, 0) >= 2]
    if have_must:
        reasons.append(f"You have {len(have_must)} of {len(a['must_units'])} must-have skills: {', '.join(have_must)}")
    if proven:
        reasons.append(f"Your resume shows real use of {', '.join(proven[:4])}")
    if missing:
        unmet.append(f"Must-have skills to learn: {', '.join(missing)}")
    if weak:
        unmet.append(f"Listed but not shown in a project or job: {', '.join(weak)}")

    # Role
    words = _words(cand["desired"])
    same_family = bool(cand["target_family"]) and a["family"] == cand["target_family"]
    if words and _has_all(words, title.lower()):
        signals["role"] = 1.0
        reasons.append(f"Title matches your target role '{cand['desired']}'")
    elif same_family:
        signals["role"] = 0.8
        reasons.append(f"Same kind of role as {'your target' if cand['target_from'] == 'role' else 'your resume points to'}"
                       f" ({family_label(a['family'])})")
    elif words and _has_all(words, low):
        signals["role"] = 0.5
        reasons.append(f"Description mentions '{cand['desired']}'")
    elif words or cand["target_family"]:
        signals["role"] = 0.0
    else:
        signals["role"] = None

    # Experience
    need = a["min_years"]
    if need is None:
        signals["experience"] = None
    elif need == 0:
        signals["experience"] = 1.0
        reasons.append("Open to freshers")
    elif cand["has_resume"]:
        got = cand["years"]
        signals["experience"] = min(1.0, got / need)
        if got >= need:
            reasons.append(f"Your experience ({got:g} yrs) meets the {need:g}+ years asked")
        else:
            unmet.append(f"Asks for {need:g}+ years of experience (you: {got:g})")
    else:
        signals["experience"] = None

    # Education
    eligible = True
    req = a["education"]
    if req and cand["level"] is not None:
        ok = cand["level"] >= req[0]
        signals["education"] = 1.0 if ok else 0.0
        if ok:
            reasons.append(f"Your education ({cand['level_name']}) meets the requirement ({req[1]})")
        else:
            eligible = False
            unmet.append(f"Asks for {req[1]} (you: {cand['level_name']})")
    else:
        signals["education"] = None

    # Field of study
    if cand["field"]:
        hit = _has_all(_words(cand["field"]), low)
        signals["field"] = 1.0 if hit else 0.0
        if hit:
            reasons.append(f"Related to your field of study ({cand['field']})")
    else:
        signals["field"] = None

    # Wording of resume vs job post
    signals["text"] = min(1.0, _cosine(cand["bag"], _bag(job_text)) / 0.35) if cand["has_resume"] else None

    known = {k: v for k, v in signals.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in known)
    fit = sum(WEIGHTS[k] * v for k, v in known.items()) / total_weight if total_weight else 0.0
    breakdown = [
        {"signal": k, "value": round(v, 2), "weight": round(WEIGHTS[k] / total_weight, 2),
         "points": round(100 * WEIGHTS[k] * v / total_weight, 1)}
        for k, v in known.items()
    ]

    # Which list the job goes in: the role you asked for (or your resume points
    # to), other roles your resume fits, or weak matches hidden by default.
    coverage = len(have_must) / len(a["must_units"]) if a["must_units"] else 0.0
    role = signals["role"]
    if role is not None and role >= 0.5:
        group = "target"
    elif coverage >= 0.6 or fit >= 0.5 or (role is None and (coverage >= 0.34 or fit >= 0.35)):
        group = "other"
    elif job.get("source") in _LIVE and fit >= 0.25:
        group = "other"   # a live opening found by searching for this role: never bury it
    else:
        group = "weak"

    return {
        "fit_score": round(fit, 2),
        "fit_breakdown": breakdown,
        "eligible": eligible,
        "relevant": group != "weak",
        "group": group,
        "tier": "strong" if fit >= 0.7 else "good" if fit >= 0.5 else "stretch",
        "reasons": reasons,
        "unmet": unmet,
        "family": a["family"],
        "family_label": a["family_label"],
        "skills_must": a["must"],
        "skills_nice": a["nice"],
        "skills_required": a["must"] + a["nice"],
        "skills_matched": have_must + have_nice,
        "skills_missing": missing,
        "skills_missing_nice": missing_nice,
        "skills_weak": weak,
        "alternatives": alts,
        "min_years": a["min_years"],
        "location_rank": location_rank(job, cand.get("state"))[0],
        "location_tag": location_rank(job, cand.get("state"))[1],
        "education_required": req[1] if req else None,
        "data_coverage": round(total_weight, 2),
    }


def score_job(job: dict, profile: dict, resume_text: str = "", desired_role: str = "",
              user_skills: list[str] | None = None) -> dict:
    return score_with(job, candidate(profile, resume_text, desired_role, user_skills))


# ── Many jobs ─────────────────────────────────────────────────

_LIVE = {"web_job", "google_jobs", "adzuna", "jooble"}
_GROUP_ORDER = {"target": 0, "other": 1, "weak": 2}


def _sort_key(j: dict):
    # Within each group: live openings before example roles, then jobs in your
    # state, remote jobs, the rest of India; then by fit.
    return (_GROUP_ORDER[j["group"]], j.get("source") == "sample", j["location_rank"],
            not j["eligible"], -j["fit_score"], -len(j["skills_matched"]))


def rank_with(jobs: list[dict], cand: dict) -> list[dict]:
    ranked = [{**job, **score_with(job, cand)} for job in jobs]
    ranked.sort(key=_sort_key)
    return ranked


def rank_jobs(jobs: list[dict], profile: dict, resume_text: str = "", desired_role: str = "",
              user_skills: list[str] | None = None) -> list[dict]:
    return rank_with(jobs, candidate(profile, resume_text, desired_role, user_skills))


def market_insight(ranked: list[dict], cand: dict, top: int = 10) -> dict | None:
    """The one missing skill that would lift the most of your best matches, and by how much."""
    pool = [j for j in ranked if j["group"] == "target"][:top]
    if len(pool) < 3:
        pool = [j for j in ranked if j["relevant"]][:top]
    if len(pool) < 2:
        return None
    counts = Counter(s for j in pool for s in j["skills_missing"])
    if not counts:
        return None
    skill, n = max(counts.items(), key=lambda kv: (kv[1], -skill_info(kv[0])["weeks"]))
    if n < 2:
        return None
    lifted = {**cand, "strength": {**cand["strength"], skill: max(cand["strength"].get(skill, 0), 2)}}
    hit = [j for j in pool if skill in j["skills_missing"]]
    before = [j["fit_score"] for j in hit]
    after = [score_with(j, lifted)["fit_score"] for j in hit]
    return {
        "skill": skill,
        "jobs": n,
        "of": len(pool),
        "weeks": skill_info(skill)["weeks"],
        "fit_before": round(sum(before) / len(before), 2),
        "fit_after": round(sum(after) / len(after), 2),
        "also": [s for s, c in counts.most_common(4) if s != skill and c >= 2][:3],
    }


def search_query(cand: dict) -> str:
    """What to search live sources for: the role typed, else the role the resume points to."""
    return cand["desired"] or family_label(cand["target_family"]) or cand["field"] or ""


def match_report(jobs: list[dict], profile: dict, resume_text: str = "", desired_role: str = "",
                 user_skills: list[str] | None = None, cand: dict | None = None) -> dict:
    cand = cand or candidate(profile, resume_text, desired_role, user_skills)
    ranked = rank_with(jobs, cand)
    return {
        "jobs": ranked,
        "resume": public_summary(cand["resume"]),
        "target_family": cand["target_family"],
        "target_label": family_label(cand["target_family"]),
        "target_from": cand["target_from"],
        "insight": market_insight(ranked, cand),
        "relevant_count": sum(j["relevant"] for j in ranked),
        "target_count": sum(j["group"] == "target" for j in ranked),
        "live_count": sum(j.get("source") != "sample" and j["relevant"] for j in ranked),
        "state": cand["state"],
        "query": search_query(cand),
    }
