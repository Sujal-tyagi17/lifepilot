"""Knowledge graph of schemes, the documents they need and their rules.

Nodes   scheme · document · criterion (category, income limit, education level, state, ...)
Edges   scheme → needs → document, scheme → requires → criterion

Each node carries the person's state: schemes they qualify for, documents they
already have, criteria they meet. From the graph we compute the most valuable
missing document: the one whose schemes add up to the most money.
"""
from __future__ import annotations

import json
from datetime import date

from app.knowledge.vectorstore import DATA_FILE
from app.services.counterfactual import scheme_value
from app.services.doc_types import doc_type, label_of, owned_types
from app.services.eligibility import evaluate


def _criteria(c: dict) -> list[tuple[str, str]]:
    out = []
    for cat in c.get("category", []):
        out.append((f"category:{cat}", f"Category {cat}"))
    if c.get("max_income"):
        out.append((f"income:{c['max_income']}", f"Income ≤ ₹{c['max_income'] / 100000:g} lakh"))
    for lvl in c.get("education_level", []):
        out.append((f"education:{lvl}", lvl))
    for st in c.get("state", []):
        out.append((f"state:{st}", st))
    for g in c.get("gender", []):
        out.append((f"gender:{g}", g))
    if c.get("disability"):
        out.append(("disability", "Disability 40%+"))
    if c.get("field_of_study"):
        out.append((f"field:{'/'.join(c['field_of_study'][:2])}", "Field: " + ", ".join(c["field_of_study"][:3])))
    if c.get("goals_keywords"):
        out.append(("goal:" + c["goals_keywords"][0], "Goal: " + c["goals_keywords"][0]))
    return out


def _meets(key: str, profile: dict) -> bool:
    kind, _, val = key.partition(":")
    if kind == "category":
        return (profile.get("category") or "").lower() == val.lower()
    if kind == "income":
        return profile.get("annual_income") is not None and profile["annual_income"] <= int(val)
    if kind == "education":
        return (profile.get("education_level") or "").lower() == val.lower()
    if kind == "state":
        return (profile.get("state") or "").lower() == val.lower()
    if kind == "gender":
        return (profile.get("gender") or "").lower() == val.lower()
    if kind == "disability":
        return bool(profile.get("disability"))
    if kind == "field":
        f = (profile.get("field_of_study") or "").lower()
        return bool(f) and any(x.lower() in f or f in x.lower() for x in val.split("/"))
    if kind == "goal":
        return val.lower() in (profile.get("goals") or "").lower()
    return False


def build_graph(profile: dict, owned: list[str] | None = None) -> dict:
    with open(DATA_FILE, encoding="utf-8") as f:
        schemes = json.load(f)
    today = date.today().isoformat()
    have = owned_types(owned)
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    missing_value: dict[str, dict] = {}

    for s in schemes:
        if s.get("deadline") and s["deadline"] < today:
            continue
        r = evaluate(profile, s)
        sid = f"scheme:{s['id']}"
        nodes[sid] = {"id": sid, "kind": "scheme", "label": s["title"], "status": "eligible" if r.eligible else "partial",
                      "amount": s.get("amount"), "deadline": s.get("deadline")}
        for d in s.get("documents") or []:
            key = doc_type(d)
            did = f"doc:{key}"
            node = nodes.setdefault(did, {"id": did, "kind": "document", "label": label_of(key, d), "have": key in have,
                                          "names": []})
            if d not in node["names"]:
                node["names"].append(d)
            edges.append({"source": sid, "target": did, "kind": "needs"})
            if r.eligible and key not in have:
                mv = missing_value.setdefault(did, {"id": did, "label": node["label"], "value": 0, "schemes": []})
                mv["value"] += scheme_value(s.get("amount"))
                mv["schemes"].append(s["title"])
        for key, label in _criteria(s.get("criteria") or {}):
            cid = f"crit:{key}"
            nodes.setdefault(cid, {"id": cid, "kind": "criterion", "label": label, "met": _meets(key, profile)})
            edges.append({"source": sid, "target": cid, "kind": "requires"})

    degree: dict[str, int] = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    for n in nodes.values():
        n["degree"] = degree.get(n["id"], 0)

    top_missing = sorted(missing_value.values(), key=lambda m: (-len(m["schemes"]), -m["value"]))
    shared = max((n for n in nodes.values() if n["kind"] == "document"), key=lambda n: n["degree"], default=None)
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "insights": {
            "most_valuable_missing_document": top_missing[0] if top_missing else None,
            "missing_documents": top_missing[:5],
            "most_shared_document": {"id": shared["id"], "label": shared["label"], "schemes": shared["degree"]} if shared else None,
            "counts": {k: sum(n["kind"] == k for n in nodes.values()) for k in ("scheme", "document", "criterion")},
        },
    }
