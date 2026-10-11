"""Analytics & insight engine.

Turns a list of eligibility matches into high-impact, demo-ready insights:
- estimated potential financial benefit (parsed from scheme amounts)
- a de-duplicated master document checklist across all eligible schemes
- application readiness given the documents a user already owns
- deadline urgency buckets
- category distribution & average confidence

Pure Python, deterministic, no external calls.
"""
from __future__ import annotations

import re
from datetime import date


_AMOUNT_RE = re.compile(
    r"\u20b9\s*([\d,]+(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|cr\b|l\b)?", re.IGNORECASE
)


def parse_amount_details(text: str | None) -> tuple[int, str]:
    """Parse the largest rupee value in a free-text amount and its period.

    Returns (value_in_rupees, period) where period is "year", "month" or
    "one_time". Handles Indian units: "\u20b920 lakh" = 20,00,000.
    """
    if not text:
        return 0, "one_time"
    values = []
    for num, unit in _AMOUNT_RE.findall(text):
        try:
            n = float(num.replace(",", ""))
        except ValueError:
            continue
        unit = (unit or "").lower()
        if unit.startswith(("lakh", "lac")) or unit == "l":
            n *= 100_000
        elif unit.startswith(("crore", "cr")):
            n *= 10_000_000
        values.append(int(n))
    if not values:
        return 0, "one_time"
    low = text.lower()
    if "month" in low:
        period = "month"
    elif "year" in low or "annum" in low or "p.a" in low:
        period = "year"
    else:
        period = "one_time"
    return max(values), period


def parse_amount(text: str | None) -> int:
    """Annual rupee value of a recurring benefit; 0 for one-time or unknown amounts."""
    value, period = parse_amount_details(text)
    if period == "month":
        return value * 12
    if period == "year":
        return value
    return 0


def status_of(m: dict) -> str:
    """Status of a match; older saved runs have no status field."""
    return m.get("status") or ("eligible" if m.get("eligible") else "partial")


def _days_left(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        return (date.fromisoformat(deadline) - date.today()).days
    except ValueError:
        return None


def _urgency_level(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days < 0:
        return "closed"
    if days <= 14:
        return "critical"
    if days <= 45:
        return "soon"
    return "comfortable"


def build_insights(matches: list[dict], owned_documents: list[str] | None = None) -> dict:
    owned = {d.strip().lower() for d in (owned_documents or []) if d.strip()}

    eligible = [m for m in matches if status_of(m) == "eligible"]
    partial = [m for m in matches if status_of(m) == "partial"]
    closed = [m for m in matches if status_of(m) == "closed"]
    needs_review = [m for m in matches if status_of(m) == "needs_review"]

    # Estimated annual benefit: recurring amounts of open, eligible schemes only.
    # One-time grants are reported separately so they don't inflate the yearly figure.
    estimated_benefit = 0
    one_time_benefit = 0
    for m in eligible:
        estimated_benefit += parse_amount(m.get("amount"))
        value, period = parse_amount_details(m.get("amount"))
        if period == "one_time":
            one_time_benefit += value

    # Master, de-duplicated document checklist across all matched schemes.
    doc_map: dict[str, dict] = {}
    for m in matches:
        if status_of(m) == "closed":
            continue
        for doc in m.get("documents", []):
            key = doc.strip().lower()
            if key not in doc_map:
                doc_map[key] = {"document": doc, "schemes": [], "owned": key in owned}
            doc_map[key]["schemes"].append(m["title"])
    master_documents = sorted(
        (
            {
                "document": v["document"],
                "used_by": len(v["schemes"]),
                "schemes": v["schemes"],
                "owned": v["owned"],
            }
            for v in doc_map.values()
        ),
        key=lambda d: (-d["used_by"], d["document"].lower()),
    )

    total_docs = len(master_documents)
    owned_docs = sum(1 for d in master_documents if d["owned"])
    readiness = round(100 * owned_docs / total_docs) if total_docs else 0

    # Deadline urgency (open items only), soonest first.
    urgency = []
    for m in matches:
        days = _days_left(m.get("deadline"))
        urgency.append(
            {
                "title": m["title"],
                "deadline": m.get("deadline"),
                "days_left": days,
                "level": _urgency_level(days),
                "eligible": status_of(m) == "eligible",
            }
        )
    urgency.sort(key=lambda u: (u["days_left"] is None, u["days_left"] if u["days_left"] is not None else 9999))

    # A deadline of today (0 days left) is still open; None means rolling/unknown.
    open_count = sum(1 for u in urgency if u["days_left"] is not None and u["days_left"] >= 0)
    critical = [u for u in urgency if u["level"] == "critical" and u["eligible"]]

    # Category distribution (by scheme id prefix is unreliable; use title-agnostic count of eligible/partial).
    avg_conf = round(sum(m["confidence"] for m in matches) / max(len(matches), 1), 2)

    return {
        "total_opportunities": len(matches),
        "eligible_count": len(eligible),
        "partial_count": len(partial),
        "closed_count": len(closed),
        "needs_review_count": len(needs_review),
        "open_count": open_count,
        "estimated_annual_benefit": estimated_benefit,
        "estimated_benefit_label": f"\u20b9{estimated_benefit:,}",
        "one_time_benefit": one_time_benefit,
        "master_documents": master_documents,
        "documents_total": total_docs,
        "documents_owned": owned_docs,
        "readiness_percent": readiness,
        "urgency": urgency,
        "critical_count": len(critical),
        "avg_confidence": avg_conf,
        "top_pick": eligible[0] if eligible else (partial[0] if partial else None),
    }
