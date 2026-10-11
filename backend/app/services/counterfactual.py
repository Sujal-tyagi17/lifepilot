"""What would change my eligibility? (counterfactual explanations)

For each scheme the person does not qualify for yet, the rule engine says
which criteria are unmet. We try small changes to the profile, re-run the same
rules, and keep the changes that unlock schemes, grouped by change and ranked
by value per unit of effort.

Only things a person can honestly change are tried:
  - documents they can obtain (a disability certificate if they have a 40%+ disability)
  - their next stage of education (from next year)
  - field of study and goals
  - family income, only framed as "if your family income changes", never as
    something to report differently
Caste, gender, age and state are never suggested as changes.

This is the explainable-AI technique called counterfactual explanations.
"""
from __future__ import annotations

import json
import math
from datetime import date
from itertools import combinations

from app.knowledge.vectorstore import DATA_FILE
from app.services.analytics import parse_amount_details
from app.services.eligibility import evaluate

NEXT_LEVEL = {"9th": "10th", "10th": "11th", "11th": "12th", "12th": "Undergraduate",
              "Diploma": "Undergraduate", "Undergraduate": "Postgraduate"}
EFFORT = {"goals": 1, "field_of_study": 3, "disability": 2, "education_level": 4, "annual_income": 5}


def scheme_value(amount: str | None) -> int:
    """Rupees a year; a one-time grant counts as a fifth of its size per year."""
    value, period = parse_amount_details(amount)
    return value * 12 if period == "month" else value // 5 if period == "one_time" else value


def _schemes() -> list[dict]:
    with open(DATA_FILE, encoding="utf-8") as f:
        items = json.load(f)
    today = date.today().isoformat()
    return [s for s in items if not s.get("deadline") or s["deadline"] >= today]   # open schemes only


def _eligible_ids(profile: dict, schemes: list[dict]) -> set[str]:
    return {s["id"] for s in schemes if evaluate(profile, s).eligible}


def candidate_changes(profile: dict, schemes: list[dict]) -> list[dict]:
    """Single changes worth trying, each with how to describe it honestly."""
    out: list[dict] = []
    level = profile.get("education_level")
    if level in NEXT_LEVEL:
        nxt = NEXT_LEVEL[level]
        out.append({"field": "education_level", "value": nxt, "kind": "later",
                    "text": f"When you move to {nxt} (next academic year)"})
    fields = sorted({f for s in schemes for f in (s.get("criteria") or {}).get("field_of_study", [])})
    for f in fields:
        if (profile.get("field_of_study") or "").lower() != f.lower():
            out.append({"field": "field_of_study", "value": f, "kind": "choice", "text": f"If you study {f}"})
    goals = (profile.get("goals") or "").lower()
    for s in schemes:
        keys = (s.get("criteria") or {}).get("goals_keywords", [])
        if keys and not any(k.lower() in goals for k in keys):
            business = any(k.lower() in ("startup", "business", "entrepreneur") for k in keys)
            out.append({"field": "goals", "value": f"{profile.get('goals') or ''}, {keys[0]}".strip(", "), "kind": "choice",
                        "effort": 8 if business else 2,
                        "text": "If you plan to start your own business or startup" if business
                        else f"If your goals include {', '.join(keys[:2]).lower()}"})
    if not profile.get("disability") and any((s.get("criteria") or {}).get("disability") for s in schemes):
        out.append({"field": "disability", "value": True, "kind": "document",
                    "text": "If you have a disability of 40% or more: get a disability certificate (UDID)"})
    income = profile.get("annual_income")
    if income is not None:
        limits = sorted({s["criteria"]["max_income"] for s in schemes
                         if (s.get("criteria") or {}).get("max_income") and s["criteria"]["max_income"] < income})
        for lim in limits[-2:]:   # the two nearest limits below today's income
            out.append({"field": "annual_income", "value": lim, "kind": "situation",
                        "text": f"If your family income changes to ₹{lim:,} or less (with a new income certificate)"})
    # de-duplicate by (field, value)
    seen, unique = set(), []
    for c in out:
        key = (c["field"], str(c["value"]))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def counterfactuals(profile: dict, max_results: int = 6) -> dict:
    schemes = _schemes()
    by_id = {s["id"]: s for s in schemes}
    base = _eligible_ids(profile, schemes)
    singles = candidate_changes(profile, schemes)

    results = []
    tried: list[tuple[list[dict], set[str]]] = []
    for c in singles:
        unlocked = _eligible_ids({**profile, c["field"]: c["value"]}, schemes) - base
        tried.append(([c], unlocked))
    # Pairs of changes, kept only when they unlock more than either change alone
    for a, b in combinations(singles, 2):
        if a["field"] == b["field"]:
            continue
        unlocked = _eligible_ids({**profile, a["field"]: a["value"], b["field"]: b["value"]}, schemes) - base
        alone = max((u for cs, u in tried if len(cs) == 1 and cs[0] in (a, b)), key=len, default=set())
        single_a = next(u for cs, u in tried if len(cs) == 1 and cs[0] is a)
        single_b = next(u for cs, u in tried if len(cs) == 1 and cs[0] is b)
        if unlocked - single_a - single_b and len(unlocked) > len(alone):
            tried.append(([a, b], unlocked))

    for changes, unlocked in tried:
        if not unlocked:
            continue
        value = sum(scheme_value(by_id[i].get("amount")) for i in unlocked)
        effort = sum(c.get("effort", EFFORT[c["field"]]) for c in changes)
        results.append({
            "changes": [{k: c[k] for k in ("field", "value", "kind", "text")} for c in changes],
            "unlocks": [{"id": i, "title": by_id[i]["title"], "amount": by_id[i].get("amount"),
                         "deadline": by_id[i].get("deadline")} for i in sorted(unlocked)],
            "count": len(unlocked),
            "value": value,
            "effort": effort,
            # value counts, but with diminishing returns, so one huge grant does not drown everything else
            "score": round((2 * math.log10(1 + value / 1000) + 2 * len(unlocked)) / effort, 2),
        })
    # Several values of the same field unlocking the same schemes become one
    # suggestion: "If you study Physics, Chemistry or Biology"
    merged: dict[tuple, dict] = {}
    for r in results:
        key = (tuple(c["field"] for c in r["changes"]), tuple(u["id"] for u in r["unlocks"]))
        if key in merged and len(r["changes"]) == 1:
            m = merged[key]
            m["options"].append(r["changes"][0]["value"])
            continue
        merged[key] = {**r, "options": [r["changes"][0]["value"]] if len(r["changes"]) == 1 else []}
    results = list(merged.values())
    for r in results:
        if len(r["options"]) > 1 and r["changes"][0]["field"] == "field_of_study":
            r["changes"][0]["text"] = "If you study " + ", ".join(r["options"][:-1]) + f" or {r['options'][-1]}"
        r.pop("options")
    results.sort(key=lambda r: (-r["score"], -r["count"]))
    return {
        "eligible_now": len(base),
        "suggestions": results[:max_results],
        "note": "Suggestions are about documents you can get or changes in your situation. "
                "Always report your details truthfully; these are not changes to what you report.",
    }
