"""A week-by-week plan to become ready for one job.

1. Focus areas: skills you already prove, skills you only list (strengthen),
   skills to learn (must-haves first).
2. Learning order: each skill's prerequisites come first (Python before
   Django), found by walking the prerequisite graph depth-first.
3. Effort: catalogue weeks assume 8 hours a week and are scaled to the hours
   the user says they have.
4. Then a portfolio project for the job family that also proves the skills
   you only list, and a job-ready step (interview topics, applying).
5. Fit now vs fit after: the job is scored again as if the plan were done.
"""
from __future__ import annotations

import math
import urllib.parse

from app.jobs.catalog import families, family_label, skill_info
from app.jobs.jobparse import analyse_job, with_typical_skills
from app.jobs.matching import score_with
from app.jobs.resume import STRENGTH_LABEL
from app.jobs.sources import sample_jobs

MAX_NICE = 2          # good-to-have skills added to a plan
MAX_STRENGTHEN = 3    # listed-only skills to prove


def scaled_weeks(base_weeks: float, hours: int) -> int:
    return max(1, math.ceil(base_weeks * 8 / max(1, hours)))


def demand(family: str | None) -> dict[str, tuple[int, int]]:
    """skill -> (roles in this family that ask for it, roles in the family)."""
    pool = [j for j in sample_jobs() if family and j.get("family") == family]
    counts: dict[str, int] = {}
    for j in pool:
        for s in set(analyse_job(j)["must"]):
            counts[s] = counts.get(s, 0) + 1
    return {s: (n, len(pool)) for s, n in counts.items()}


def learning_order(targets: list[str], has) -> list[tuple[str, str | None]]:
    """[(skill, needed_for)] with prerequisites before the skills that need them."""
    order: list[tuple[str, str | None]] = []
    seen: set[str] = set()

    def visit(skill: str, needed_for: str | None, depth: int):
        if skill in seen or depth > 6:
            return
        seen.add(skill)
        for pre in skill_info(skill)["prereqs"]:
            if not has(pre):
                visit(pre, skill, depth + 1)
        order.append((skill, needed_for))

    for t in targets:
        visit(t, None, 0)
    return order


_TASKS = {
    "tech": ["Work through the first resource up to the basics", "Write small practice programs every session",
             "Use {s} in a mini project and push it to GitHub"],
    "design": ["Follow the first resource end to end", "Redesign one real screen or poster with {s}",
               "Add the result to a portfolio page"],
    "business": ["Learn the basics from the first resource", "Do one worked example on real or public data",
                 "Write 3 resume lines on how you would use {s} in this job"],
    "finance": ["Learn the basics from the first resource", "Practise with sample entries or a dummy company",
                "Note the steps you followed as a one-page cheat sheet"],
    "office": ["Follow the first resource", "Redo one real task (a report, a sheet) with {s}",
               "Keep the file to show in interviews"],
}
_TASKS_DEFAULT = ["Learn the basics from the first resource", "Practise {s} with a small real task",
                  "Write one resume line on where you used {s}"]


def _tasks(skill: str) -> list[str]:
    return [t.format(s=skill) for t in _TASKS.get(skill_info(skill)["kind"], _TASKS_DEFAULT)]


def _resources(skill: str) -> list[dict]:
    res = list(skill_info(skill)["resources"])
    q = urllib.parse.quote(skill)
    if not any(r["provider"] == "YouTube" for r in res):
        res.append({"provider": "YouTube", "title": f"{skill} tutorials", "url": f"https://www.youtube.com/results?search_query={q}+tutorial"})
    return res[:3]


def resume_fixes(job_score: dict, cand: dict) -> list[str]:
    r = cand["resume"]
    fixes: list[str] = []
    if not r["has_resume"]:
        return ["Add your resume on the Jobs page. Without it we only know the skills you typed, so the plan cannot "
                "tell which ones you have proved."]
    for s in job_score["skills_weak"][:3]:
        fixes.append(f"You list {s} but no project or job shows it. Add one line under a project saying what you built with {s}.")
    if "projects" not in r["sections"]:
        fixes.append("Add a Projects section. For freshers it is the strongest proof of skill.")
    if "experience" not in r["sections"] and not r["internships"]:
        fixes.append("Add internships, freelance or volunteer work, even short ones, under Experience.")
    if job_score["skills_matched"]:
        fixes.append(f"Put {', '.join(job_score['skills_matched'][:4])} near the top. This job asks for them.")
    if "certifications" not in r["sections"]:
        fixes.append("Add a Certifications section and list the courses you finish from this plan.")
    if r["words"] and r["words"] < 150:
        fixes.append("Your resume is very short. Add 2–3 lines per project: what you built, the tools, and a result.")
    need = job_score.get("min_years")
    if need and cand["years"] < need:
        fixes.append(f"This job asks for {need:g}+ years. Finish the project in this plan first, and apply to internships or "
                     "trainee roles in the same family at the same time.")
    return fixes[:6]


def build_plan(job: dict, cand: dict, hours_per_week: int = 8, learned: list[str] | None = None) -> dict:
    hours = max(2, min(40, int(hours_per_week or 8)))
    learned = set(learned or [])
    parsed = analyse_job(job)
    parsed = with_typical_skills(parsed, parsed["family"] or cand["target_family"])
    start = score_with(job, cand, parsed)
    strength = cand["strength"]

    def has(skill: str) -> bool:
        return strength.get(skill, 0) > 0

    family = parsed["family"]
    dem = demand(family)
    typical = set(parsed["typical"])
    experienced = cand["years_known"] and cand["years"] >= 2
    need = parsed["min_years"] or 0
    gap = cand["years_known"] and need > cand["years"]

    # Focus areas
    have = [{"skill": s, "evidence": STRENGTH_LABEL[strength[s]]} for s in start["skills_matched"] if strength.get(s, 0) >= 2]
    strengthen = [{"skill": s, "why": "Listed on your resume or form, but not shown in a project or job"}
                  for s in start["skills_weak"][:MAX_STRENGTHEN]]
    targets = start["skills_missing"] + start["skills_missing_nice"][:MAX_NICE]
    must_set = set(start["skills_missing"])
    learn_order = learning_order(targets, has)
    learn = [{
        "skill": s,
        "must": s in must_set,
        "prereq_for": needed_for,
        "weeks": scaled_weeks(skill_info(s)["weeks"], hours),
        "alternatives": start["alternatives"].get(s, []),
        "demand": {"jobs": dem[s][0], "of": dem[s][1]} if s in dem else None,
        "typical": s in typical,
    } for s, needed_for in learn_order]

    # Steps
    steps: list[dict] = []
    week = 0

    def add(step: dict):
        nonlocal week
        step["start_week"] = week + 1
        week += step["weeks"]
        step["end_week"] = week
        step["done"] = bool(step["skills"]) and all(x in learned for x in step["skills"])
        steps.append(step)

    for item in learn:
        sk = item["skill"]
        why = (f"Needed before {item['prereq_for']}" if item["prereq_for"]
               else "Must-have for this job" if item["must"] else "Good to have for this job")
        if item["alternatives"]:
            why += f" (or {', '.join(item['alternatives'])}, if you prefer)"
        if item["typical"]:
            why += " (this post doesn't list skills; roles like it usually ask for it)"
        # Someone with 2+ years of work likely knows the foundations already: a refresher, not a course
        refresher = experienced and item["prereq_for"]
        weeks = max(1, math.ceil(item["weeks"] / 2)) if refresher else item["weeks"]
        add({"id": f"learn-{sk}", "kind": "learn", "skills": [sk],
             "title": f"Brush up on {sk}" if refresher else f"Learn {sk}", "why": why,
             "weeks": weeks, "tasks": _tasks(sk), "resources": _resources(sk)})

    # One project proves the new skills and the listed-only ones together.
    prove = [x["skill"] for x in strengthen]
    fam = families().get(family or "", {})
    uses = [x["skill"] for x in learn if not x["prereq_for"]][:4] + prove
    if fam.get("project"):
        add({"id": "build-project", "kind": "build", "skills": prove, "title": "Build a portfolio project",
             "why": f"Proof that you can do the work of a {fam['label'].lower()}",
             "weeks": scaled_weeks(3 + 0.5 * len(prove), hours),
             "tasks": [fam["project"],
                       f"Use {', '.join(uses)}" if uses else "Use the skills this job asks for",
                       "Write a short README with screenshots and what you learned",
                       "Add it to your resume with one result in numbers"],
             "resources": []})
    elif prove:
        add({"id": "prove-skills", "kind": "build", "skills": prove, "title": f"Prove {', '.join(prove)}",
             "why": "Listed on your resume or form, but not shown in a project or job",
             "weeks": scaled_weeks(len(prove), hours),
             "tasks": [f"Do one small real task with each of {', '.join(prove)}",
                       "Add a resume line for each: what you did and the result"],
             "resources": []})

    if gap:
        short = need - cand["years"]
        add({"id": "experience", "kind": "build", "skills": [], "title": "Get real work experience",
             "why": f"This job asks for about {need:g}+ years; you have {cand['years']:g}. Close part of the gap with real work.",
             "weeks": scaled_weeks(6, hours),
             "tasks": [
                 "Apply for internships or trainee roles in this field (Internshala, LinkedIn, college placement cell)"
                 if cand["fresher"] else "Take on a freelance or side project for a real client",
                 "Contribute to an open-source project that uses these skills",
                 "Add each piece of work to your resume under Experience with dates and results",
                 f"Meanwhile, apply to roles asking for {max(0, need - 2):g}–{need:g} years in the same field"
                 if short > 2 else "Apply to this job once the project is done; a strong portfolio can stand in for a year",
             ],
             "resources": [{"provider": "Internshala", "title": "Internships and fresher jobs", "url": "https://internshala.com/"},
                           {"provider": "GitHub", "title": "Good first issues in open source", "url": "https://github.com/topics/good-first-issue"}]})

    topics = fam.get("interview") or ["Explaining your projects end to end", "Why you want this role"]
    add({"id": "job-ready", "kind": "apply", "skills": [], "title": "Get interview-ready and apply",
         "why": "Turn the plan into applications", "weeks": 1,
         "tasks": [f"Revise: {t}" for t in topics[:4]] + [
             "Update your resume with the fixes above",
             "Apply to this job and 5 similar ones from your matches"]
             + (["Also apply to internships and trainee roles: they hire freshers fastest"] if cand["fresher"] else []),
         "resources": []})

    # Fit: now (with ticked skills) and after the whole plan
    def with_skills(skills) -> dict:
        lifted = dict(strength)
        for s in skills:
            lifted[s] = max(lifted.get(s, 0), 2)
        return {**cand, "strength": lifted}

    fit_now = score_with(job, with_skills(learned), parsed)["fit_score"]
    fit_after = score_with(job, with_skills([x["skill"] for x in learn] + [x["skill"] for x in strengthen]), parsed)["fit_score"]

    return {
        "job": {k: job.get(k) for k in ("id", "title", "company", "location", "url", "source")},
        "family": family,
        "family_label": family_label(family),
        "hours_per_week": hours,
        "total_weeks": week,
        "fit_start": start["fit_score"],
        "fit_now": fit_now,
        "fit_after": fit_after,
        "eligible": start["eligible"],
        "unmet": start["unmet"],
        "focus": {"have": have, "strengthen": strengthen, "learn": learn},
        "resume_fixes": resume_fixes(start, cand),
        "typical_skills": parsed["typical"],
        "based_on": "resume" if cand["has_resume"] else "form",
        "years": cand["years"] if cand["years_known"] else None,
        "steps": steps,
        "fit_breakdown": start["fit_breakdown"],
    }
