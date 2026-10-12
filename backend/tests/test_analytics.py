"""Benefit parsing and insight counts."""
from datetime import date, timedelta

import pytest

from app.services.analytics import build_insights, parse_amount, parse_amount_details


@pytest.mark.parametrize("text,annual", [
    ("Up to ₹1,20,000 / year (tuition + maintenance)", 120_000),
    ("₹1,500 / month (hostel/food allowance)", 18_000),
    ("₹12,000 - ₹20,000 / year", 20_000),
    ("₹2.5 lakh per annum", 250_000),
    ("Free training + placement assistance", 0),
    (None, 0),
])
def test_parse_amount(text, annual):
    assert parse_amount(text) == annual


def test_lakh_and_crore_units():
    # "₹50 lakh" used to parse as ₹50
    assert parse_amount_details("Up to ₹20 lakh (grant) / ₹50 lakh (investment)") == (5_000_000, "one_time")
    assert parse_amount_details("₹1 crore") == (10_000_000, "one_time")


def _m(title, status, amount, days):
    d = (date.today() + timedelta(days=days)).isoformat() if days is not None else None
    return {"title": title, "status": status, "eligible": status in ("eligible", "closed"),
            "amount": amount, "deadline": d, "confidence": 0.9, "documents": [f"{title} doc"]}


def test_insights_count_only_open_eligible_recurring_benefit():
    matches = [
        _m("A", "eligible", "₹10,000 / year", 0),       # deadline today: still open
        _m("B", "eligible", "₹20 lakh grant", None),    # one-time: not in annual figure
        _m("C", "closed", "₹99,000 / year", -5),        # closed: excluded
        _m("D", "partial", "₹5,000 / year", 30),
        _m("E", "needs_review", None, None),
    ]
    ins = build_insights(matches)
    assert ins["eligible_count"] == 2
    assert ins["closed_count"] == 1 and ins["needs_review_count"] == 1 and ins["partial_count"] == 1
    assert ins["estimated_annual_benefit"] == 10_000
    assert ins["one_time_benefit"] == 2_000_000
    assert ins["open_count"] == 2  # A (today) and D
    assert "C doc" not in [d["document"] for d in ins["master_documents"]]
