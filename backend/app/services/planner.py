"""Smart application priority planner.

Turns what the person qualifies for into a week-by-week plan:
"Week 1: get the income certificate (unlocks 3 schemes). Week 2: apply to
AICTE Pragati (closes 15 Oct). Week 3: apply to 3 jobs above 75% fit."

Tasks
    get a document     effort from doc_types (e.g. income certificate 6 h)
    apply to a scheme  1.5 h; needs its missing documents first; has a deadline
    apply to a job     1 h; from the person's best job matches
    start a skill      a few hours on the best next skill from the Jobs page

Value
    scheme   10 × log10(1 + rupees a year / 1,000) × eligibility confidence (one-time grants count a fifth a year)
    job      fit score × 30 points
    document no value of its own; it carries the value of the applications it unblocks,
             split between the documents each application still needs, so a document
             needed by many schemes is done first

Scheduling
    Week by week: from the tasks whose prerequisites are done, pick the set that fits the
    week's hours and has the most value (0/1 knapsack, in half-hour steps). Urgency: a task
    closing this week or within two weeks after it counts 2×, within four weeks 1.4×; a task
    with no deadline counts half, since nothing is lost by doing it later. A document is as
    urgent as the earliest application still waiting for it, and worth a share of each such
    application (the last missing document carries the most). Looking ahead, an
    application whose remaining work would no longer fit before its deadline if it
    waited a week is critical, and its whole chain counts 3×. Earlier deadlines win ties
    (Earliest Deadline First). An application that cannot be finished before its deadline is
    marked "at risk"; one whose deadline passes first is listed as missed.

The same tasks are also scheduled the naive way (nearest deadline first, take whatever
fits). Both schedules are scored by the value of applications finished before their
deadlines, and the better one is returned ("strategy"), with both values reported.
Any hours left in a week go to work that became possible that week (a form whose last
document was just collected).
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.services.counterfactual import scheme_value
from app.services.doc_types import doc_type, hours_of, label_of, owned_types

WEEKS = 8
APPLY_HOURS = 1.5
JOB_HOURS = 1.0


def _deadline(m: dict) -> date | None:
    try:
        return date.fromisoformat(m.get("deadline") or "")
    except ValueError:
        return None


def _lower(label: str) -> str:
    """'Income certificate' -> 'income certificate', but 'Aadhaar card' and 'PAN' keep their capitals."""
    return " ".join(w if w in ("Aadhaar", "PAN", "UDID", "DPIIT") or w.isupper() else w.lower() for w in label.split())


def build_tasks(matches: list[dict], owned: list[str] | None, jobs: list[dict] | None, skill: dict | None) -> list[dict]:
    have = owned_types(owned)
    today = date.today()
    tasks: dict[str, dict] = {}
    for m in matches:
        if (m.get("status") or ("eligible" if m.get("eligible") else "partial")) != "eligible":
            continue
        dl = _deadline(m)
        if dl and dl < today:
            continue
        needs = []
        for d in m.get("documents") or []:
            key = doc_type(d)
            if key in have:
                continue
            needs.append(f"doc:{key}")
            t = tasks.setdefault(f"doc:{key}", {"id": f"doc:{key}", "kind": "document", "title": f"Get your {_lower(label_of(key, d))}",
                                                "doc": key, "hours": hours_of(key), "value": 0.0, "deadline": None,
                                                "deps": [], "for": []})
            t["for"].append(m["title"])
            if dl and (t["deadline"] is None or dl < t["deadline"]):
                t["deadline"] = dl
        # Points grow with the log of the amount, so a ₹50 lakh startup grant does not drown every scholarship
        value = 10 * math.log10(1 + scheme_value(m.get("amount")) / 1000) * float(m.get("confidence") or 0.8)
        tasks[f"scheme:{m.get('opportunity_id') or m['title']}"] = {
            "id": f"scheme:{m.get('opportunity_id') or m['title']}", "kind": "scheme", "title": f"Apply to {m['title']}",
            "hours": APPLY_HOURS, "value": round(max(value, 5.0), 1), "deadline": dl, "deps": needs,
            "url": m.get("url"), "amount": m.get("amount"),
        }
    for j in (jobs or [])[:6]:
        tasks[f"job:{j.get('id')}"] = {
            "id": f"job:{j.get('id')}", "kind": "job",
            "title": f"Apply to {j.get('title')}" + (f" at {j['company']}" if j.get("company") else ""),
            "hours": JOB_HOURS, "value": round(float(j.get("fit_score") or 0.5) * 30, 1), "deadline": None, "deps": [],
            "url": j.get("url"), "fit": j.get("fit_score"),
        }
    if skill and skill.get("skill"):
        tasks["skill"] = {"id": "skill", "kind": "skill", "title": f"Start learning {skill['skill']}",
                          "hours": 4.0, "value": 8.0 + 2 * float(skill.get("jobs") or 0), "deadline": None, "deps": [],
                          "why": f"Asked by {skill.get('jobs')} of your top job matches"}
    # Documents carry the value of what they unblock
    for t in tasks.values():
        for dep in t["deps"]:
            tasks[dep]["value"] += 0.9 * t["value"] / len(t["deps"])
    for t in tasks.values():
        if t["kind"] == "document":
            n = len(set(t["for"]))
            t["why"] = f"Needed for {n} scheme{'s' if n != 1 else ''}: {', '.join(sorted(set(t['for']))[:3])}"
            t["value"] = round(t["value"], 1)
    return list(tasks.values())


def _week_value(t: dict, week_end: date) -> float:
    """Value this week: things that close soon are worth more now, because waiting loses them."""
    v = t["value"]
    if t["deadline"]:
        days = (t["deadline"] - (week_end - timedelta(days=6))).days   # from the start of this week
        if days < 0:
            v *= 0.3      # already closed: little point doing it first
        elif days <= 20:
            v *= 2.0      # closes this week or within two weeks after it
        elif days <= 34:
            v *= 1.4
    else:
        v *= 0.5          # no deadline: nothing is lost by doing it a week later
    if t.get("crit"):
        v *= 3.0          # its application cannot wait another week
    return v


def _knapsack(items: list[dict], capacity_halves: int, week_end: date) -> list[dict]:
    """Best set of tasks for one week. Ties go to the earlier deadline."""
    far = date(9999, 1, 1)
    items = sorted(items, key=lambda t: (t["deadline"] or far, t["id"]))
    n = len(items)
    w = [max(1, math.ceil(t["hours"] * 2)) for t in items]
    # tiny bonus for earlier deadlines makes EDF the tie-breaker
    v = [_week_value(t, week_end) + 1e-3 * (n - i) for i, t in enumerate(items)]
    best = [[0.0] * (capacity_halves + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for c in range(capacity_halves + 1):
            best[i][c] = best[i - 1][c]
            if w[i - 1] <= c:
                best[i][c] = max(best[i][c], best[i - 1][c - w[i - 1]] + v[i - 1])
    chosen, c = [], capacity_halves
    for i in range(n, 0, -1):
        if best[i][c] != best[i - 1][c]:
            chosen.append(items[i - 1])
            c -= w[i - 1]
    return chosen


def _schedule(tasks: list[dict], hours: float, pick) -> tuple[list[dict], list[dict]]:
    today = date.today()
    done: set[str] = set()
    missed: list[dict] = []
    weeks, remaining = [], {t["id"]: t for t in tasks}
    for wk in range(1, WEEKS + 1):
        start = today + timedelta(days=7 * (wk - 1))
        end = start + timedelta(days=6)
        for t in [t for t in remaining.values() if t["kind"] != "document" and t["deadline"] and t["deadline"] < start]:
            missed.append(_public(t, start)); remaining.pop(t["id"])   # closed before we could get to it
        # A document is as urgent as the earliest application still waiting for it, and worth a
        # share of each one: the fewer documents an application still lacks, the bigger the share,
        # so the last document standing between you and a scheme carries that scheme's value
        for t in remaining.values():
            if t["kind"] == "document":
                waiting = [r for r in remaining.values() if t["id"] in r["deps"]]
                dated = [r["deadline"] for r in waiting if r["deadline"]]
                t["deadline"] = min(dated) if dated else None
                t["value"] = round(sum(0.9 * r["value"] / max(1, len([d for d in set(r["deps"]) if d not in done]))
                                       for r in waiting), 1)
        # Look ahead: an application whose remaining work (its missing documents plus the form)
        # no longer fits in the weeks before its deadline if we skip this week is critical,
        # and so is everything in its chain. Critical work is done first.
        for t in remaining.values():
            t["crit"] = False
        for r in remaining.values():
            if r["kind"] == "document" or not r["deadline"]:
                continue
            chain = [r] + [remaining[d] for d in set(r["deps"]) if d in remaining]
            need = sum(t.get("hours_left", t["hours"]) for t in chain)
            weeks_left = sum(1 for k in range(wk, WEEKS + 1) if today + timedelta(days=7 * (k - 1)) <= r["deadline"])
            if need > hours * (weeks_left - 1) + 1e-9:   # it cannot wait a week
                for t in chain:
                    t["crit"] = True
        ready = [t for t in remaining.values() if all(d in done for d in t["deps"])]
        cap = int(hours * 2)
        oversized = [t for t in ready if t["hours"] * 2 > cap]
        for t in oversized:   # a task bigger than a whole week is spread over several weeks
            t["hours_left"] = t.get("hours_left", t["hours"])
        chosen = pick([t for t in ready if t["hours"] * 2 <= cap], cap, end)
        used = sum(t["hours"] for t in chosen)
        if not chosen and oversized:
            t = min(oversized, key=lambda x: x["deadline"] or date(9999, 1, 1))
            t["hours_left"] -= hours
            chosen_rows = [{**_public(t, end), "partial": True, "hours": hours}]
            used = hours
            if t["hours_left"] <= 0:
                done.add(t["id"]); remaining.pop(t["id"])
            weeks.append({"week": wk, "start": start.isoformat(), "end": end.isoformat(), "hours_used": used, "tasks": chosen_rows})
            continue
        for t in chosen:
            done.add(t["id"]); remaining.pop(t["id"])
        # Time left this week: do follow-on work that just became possible, such as the
        # application form whose last document was collected earlier this week
        while True:
            left = hours - used
            follow = [t for t in remaining.values() if all(d in done for d in t["deps"]) and t["hours"] <= left + 1e-9]
            if not follow:
                break
            t = max(follow, key=lambda x: (x.get("crit", False), x["kind"] != "document" and bool(x["deadline"]),
                                           -(x["deadline"] or date(9999, 1, 1)).toordinal(), x["value"]))
            chosen.append(t); used += t["hours"]
            done.add(t["id"]); remaining.pop(t["id"])
        weeks.append({"week": wk, "start": start.isoformat(), "end": end.isoformat(), "hours_used": round(used, 1),
                      "tasks": [_public(t, end) for t in sorted(chosen, key=lambda t: (t["kind"] != "document", t["deadline"] or date(9999, 1, 1)))]})
        if not remaining:
            break
    while weeks and not weeks[-1]["tasks"]:
        weeks.pop()
    # documents nothing needs any more are not worth listing
    left = [t for t in remaining.values() if t["kind"] != "document"
            or any(d == t["id"] for r in remaining.values() for d in r["deps"])]
    return weeks, left, missed


def _public(t: dict, week_end: date) -> dict:
    out = {k: t.get(k) for k in ("id", "kind", "title", "why", "hours", "url", "amount", "fit")}
    out["value"] = round(t["value"], 1)
    out["deadline"] = t["deadline"].isoformat() if t["deadline"] else None
    # at risk if it closes before the middle of the week it is planned for
    out["at_risk"] = bool(t["kind"] != "document" and t["deadline"] and t["deadline"] < week_end - timedelta(days=3))
    out["unlocks"] = len(set(t.get("for", [])))
    return {k: v for k, v in out.items() if v not in (None, "")}


def _naive(items, capacity_halves, week_end):
    """Nearest deadline first: take tasks in deadline order while they fit."""
    far = date(9999, 1, 1)
    chosen, left = [], capacity_halves
    for t in sorted(items, key=lambda t: (t["deadline"] or far, -t["value"])):
        w = max(1, math.ceil(t["hours"] * 2))
        if w <= left:
            chosen.append(t); left -= w
    return chosen


def _captured(weeks: list[dict]) -> float:
    """Value of applications finished before their deadline (documents only count through them)."""
    return round(sum(t["value"] for w in weeks for t in w["tasks"]
                     if t["kind"] != "document" and not t.get("at_risk") and not t.get("partial")), 1)


def plan(matches: list[dict], hours_per_week: float = 6, owned: list[str] | None = None,
         jobs: list[dict] | None = None, skill: dict | None = None) -> dict:
    hours = max(1.0, min(40.0, float(hours_per_week or 6)))
    tasks = build_tasks(matches, owned, jobs, skill)
    weeks, left, missed = _schedule([dict(t) for t in tasks], hours, _knapsack)
    naive_weeks, naive_left, naive_missed = _schedule([dict(t) for t in tasks], hours, _naive)
    # Two candidate schedules; keep the one that gets more value in before the deadlines.
    # Value-first usually wins when deadlines differ; deadline-first can win when they cluster.
    strategy = "value-first"
    knapsack_value = _captured(weeks)
    if _captured(naive_weeks) > _captured(weeks) + 1e-9:
        weeks, left, missed, strategy = naive_weeks, naive_left, naive_missed, "deadline-first"
    first_deadline = min((t["deadline"] for t in tasks if t["deadline"]), default=None)
    return {
        "hours_per_week": hours,
        "weeks": weeks,
        "strategy": strategy,
        "not_scheduled": [_public(t, date.today()) for t in left],
        "missed": missed,
        "totals": {
            "tasks": len(tasks),
            "documents": sum(t["kind"] == "document" for t in tasks),
            "schemes": sum(t["kind"] == "scheme" for t in tasks),
            "jobs": sum(t["kind"] == "job" for t in tasks),
            "value": _captured(weeks),
            "naive_value": _captured(naive_weeks),
            "knapsack_value": knapsack_value,
            "at_risk": sum(t.get("at_risk", False) for w in weeks for t in w["tasks"]),
            "first_deadline": first_deadline.isoformat() if first_deadline else None,
        },
    }
