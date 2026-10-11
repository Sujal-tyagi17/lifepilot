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
import re
from datetime import date, timedelta
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


PACES = [
    # (up to hours/week, key, label, parallel learning tracks)
    (5, "light", "Light pace: must-have skills only", 1),
    (15, "steady", "Steady pace: must-haves and the most useful extras", 1),
    (29, "intensive", "Intensive: weekly self-tests, more practice and mock interviews", 1),
    (40, "fulltime", "Full-time: everything above plus a second project", 1),
]


def pace_for(hours: int) -> dict:
    for limit, key, label, tracks in PACES:
        if hours <= limit:
            return {"key": key, "label": label, "tracks": tracks}
    return {"key": "fulltime", "label": PACES[-1][2], "tracks": 1}


def _tasks(skill: str, hours_week: float = 8, pace: str = "steady") -> list[str]:
    tasks = [t.format(s=skill) for t in _TASKS.get(skill_info(skill)["kind"], _TASKS_DEFAULT)]
    per_day = hours_week / 6
    tasks.insert(0, f"About {per_day:.1f} hours a day, 6 days a week" if per_day >= 1
                 else f"About {round(hours_week * 60 / 3)} minutes, 3 times a week")
    if skill in ("Data Structures", "Algorithms", "Python", "Java", "C++", "JavaScript", "SQL"):
        n = max(3, round(hours_week / 1.5))
        tasks.append(f"Solve {n} practice problems a week on LeetCode, HackerRank or GeeksforGeeks")
    if pace in ("intensive", "fulltime"):
        tasks.append(f"End of each week: a 30-minute self-test on what you learned in {skill}")
    return tasks


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
    pace = pace_for(hours)
    is_intern = bool(re.search(r"\bintern(ship)?\b|\btrainee\b|\bapprentice\b", job.get("title", ""), re.IGNORECASE))
    # Light pace: must-haves only. More time: the good-to-haves too.
    # (More hours never adds skills: it makes the plan shorter and deeper.)
    nice_extra = 0 if pace["key"] == "light" else MAX_NICE
    targets = start["skills_missing"] + start["skills_missing_nice"][:nice_extra]
    must_set = set(start["skills_missing"])
    learn_order = learning_order(targets, has)
    learn = [{
        "skill": s,
        "must": s in must_set,
        "prereq_for": needed_for,
        "weeks": scaled_weeks(skill_info(s)["weeks"], hours),
        "hours": skill_info(s)["weeks"] * 8,
        "alternatives": start["alternatives"].get(s, []),
        "demand": {"jobs": dem[s][0], "of": dem[s][1]} if s in dem else None,
        "typical": s in typical,
    } for s, needed_for in learn_order]

    # Steps, one after another; a skill never starts before the skills it needs.
    # Every step's length is its effort in hours divided by your hours a week.
    steps: list[dict] = []
    tracks = [0] * pace["tracks"]
    finish: dict[str, int] = {}
    week = 0

    def place(step: dict, after: int = 0, track_hours: float | None = None):
        nonlocal week
        t = min(range(len(tracks)), key=lambda i: max(tracks[i], after))
        begin = max(tracks[t], after)
        step["start_week"] = begin + 1
        step["end_week"] = begin + step["weeks"]
        step["track"] = t + 1 if len(tracks) > 1 else None
        step["hours_per_week"] = round(track_hours or hours, 1)
        tracks[t] = step["end_week"]
        week = max(week, step["end_week"])
        step["done"] = bool(step["skills"]) and all(x in learned for x in step["skills"])
        steps.append(step)
        return step

    def add(step: dict):
        """A step everyone works on together, after everything before it."""
        begin = max(tracks)
        for i in range(len(tracks)):
            tracks[i] = begin
        place(step, begin)
        for i in range(len(tracks)):
            tracks[i] = step["end_week"]

    if is_intern or cand["fresher"] and parsed["junior"]:
        add({"id": "apply-early", "kind": "apply", "skills": [], "title": "Apply now, learn alongside",
             "why": "Internships and fresher roles fill fast; most ask for basics and a willingness to learn",
             "weeks": 1, "hours": 3,
             "tasks": [f"Apply to {job.get('title') or 'this role'}" + (f" at {job['company']}" if job.get("company") else "") + " this week",
                       "Write a 3-line cover note: what you know, what you are learning (from this plan), why this company",
                       f"Apply to {3 if pace['key'] == 'light' else 5 if pace['key'] == 'steady' else 10} more similar internships every week from your matches"],
             "resources": [{"provider": "Internshala", "title": "Internships", "url": "https://internshala.com/internships"}]})

    per_track = hours / pace["tracks"]
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
        effort = item["hours"] / (2 if refresher else 1)
        weeks = max(1, math.ceil(effort / per_track))
        needs = [finish[p] for p in skill_info(sk)["prereqs"] if p in finish]
        step = place({"id": f"learn-{sk}", "kind": "learn", "skills": [sk],
                      "title": f"Brush up on {sk}" if refresher else f"Learn {sk}", "why": why,
                      "weeks": weeks, "hours": round(effort), "tasks": _tasks(sk, per_track, pace["key"]),
                      "resources": _resources(sk)}, after=max(needs, default=0), track_hours=per_track)
        finish[sk] = step["end_week"]

    # The project mirrors this job and proves the new and the listed-only skills.
    prove = [x["skill"] for x in strengthen]
    fam = families().get(family or "", {})
    uses = [x["skill"] for x in learn if not x["prereq_for"]][:4] + prove + [x["skill"] for x in have][:2]
    what = job.get("title") or (fam.get("label") or "this role")
    at = f" at {job['company']}" if job.get("company") else ""
    if fam.get("project") or uses:
        add({"id": "build-project", "kind": "build", "skills": prove, "title": "Build a project for this job",
             "why": f"Proof you can do the work of a {what}{at}",
             "weeks": scaled_weeks(3 + 0.5 * len(prove), hours), "hours": round((3 + 0.5 * len(prove)) * 8),
             "tasks": [f"Pick a problem {job['company']} or its customers have, and solve a small part of it" if job.get("company")
                       else "Pick a real problem from your college, family business or city",
                       fam.get("project") or "Build a small working version end to end",
                       f"Use {', '.join(dict.fromkeys(uses))}" if uses else "Use the skills this job asks for",
                       "Write a README with screenshots, and add it to your resume with one result in numbers"]
                      + (["Deploy it so a recruiter can open it from a link"] if pace["key"] != "light" else []),
             "resources": []})
    if pace["key"] == "fulltime":
        add({"id": "build-second", "kind": "build", "skills": [], "title": "Build a second, bigger project",
             "why": "With full-time hours you can show depth: two projects beat one",
             "weeks": scaled_weeks(4, hours), "hours": 32,
             "tasks": ["Extend the first project or build a new one with a database, login and tests",
                       "Get 3 friends or classmates to use it and fix what they report",
                       "Write a short blog post or LinkedIn post about what you built"],
             "resources": []})

    if gap:
        short = need - cand["years"]
        add({"id": "experience", "kind": "build", "skills": [], "title": "Get real work experience",
             "why": f"This job asks for about {need:g}+ years; you have {cand['years']:g}. Close part of the gap with real work.",
             "weeks": scaled_weeks(6, hours), "hours": 48,
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
    mocks = {"light": 1, "steady": 2, "intensive": 4, "fulltime": 6}[pace["key"]]
    add({"id": "job-ready", "kind": "apply", "skills": [], "title": "Get interview-ready and apply",
         "why": f"Turn the plan into applications for {what}{at}", "weeks": max(1, math.ceil((8 if pace["key"] in ("light", "steady") else 16) / hours)),
         "hours": 8 if pace["key"] in ("light", "steady") else 16,
         "tasks": [f"Revise: {t}" for t in topics[:4]] + [
             f"Do {mocks} mock interview{'s' if mocks > 1 else ''} with a friend or on Pramp",
             "Update your resume with the fixes above",
             f"Apply to this job and {5 if pace['key'] in ('light', 'steady') else 10} similar ones from your matches"]
             + (["Also apply to internships and trainee roles: they hire freshers fastest"] if cand["fresher"] and not is_intern else []),
         "resources": [{"provider": "Pramp", "title": "Free mock interviews", "url": "https://www.pramp.com/"}] if family in ("backend", "frontend", "fullstack", "software", "data_scientist", "mobile") else []})

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
        "pace": pace,
        "ready_by": (date.today() + timedelta(weeks=week)).isoformat(),
        "per_day": round(hours / 6, 1),
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
