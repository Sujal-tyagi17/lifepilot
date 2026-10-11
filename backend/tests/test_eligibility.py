"""Rule engine and agent-level fixes (B1, B6, B7, B8)."""
from datetime import date, timedelta

from app.agents.eligibility_agent import match_sort_key
from app.services.eligibility import NEEDS_REVIEW_MESSAGE, evaluate

PROFILE = {"category": "OBC", "education_level": "Undergraduate", "annual_income": 300000, "gender": "Female"}


def test_item_without_criteria_is_never_eligible():
    # B1: a web search result with no rules used to come back eligible with score 1.0
    r = evaluate(PROFILE, {"title": "Some web page", "criteria": {}})
    assert r.eligible is False
    assert r.status == "needs_review"
    assert r.score == 0.0
    assert NEEDS_REVIEW_MESSAGE in r.unmet


def test_null_criteria_is_handled():
    assert evaluate(PROFILE, {"title": "x", "criteria": None}).status == "needs_review"


def test_explicit_open_to_all_is_eligible():
    r = evaluate(PROFILE, {"criteria": {"open_to_all": True}})
    assert r.eligible and r.status == "eligible"


def test_rules_decide_eligibility():
    ok = evaluate(PROFILE, {"criteria": {"category": ["OBC"], "max_income": 400000}})
    assert ok.eligible and ok.status == "eligible" and ok.score == 1.0
    no = evaluate(PROFILE, {"criteria": {"category": ["SC"], "max_income": 400000}})
    assert not no.eligible and no.status == "partial" and no.score == 0.5


def _m(status, days, score):
    d = (date.today() + timedelta(days=days)).isoformat() if days is not None else None
    return {"status": status, "deadline": d, "score": score, "title": f"{status}-{days}-{score}"}


def test_sort_order_eligible_soonest_then_closest_partial_then_closed():
    items = [
        _m("closed", -10, 1.0),
        _m("partial", 5, 0.3),
        _m("partial", 50, 0.8),
        _m("eligible", 40, 1.0),
        _m("eligible", 3, 1.0),
        _m("needs_review", None, 0.0),
        _m("eligible", None, 1.0),  # rolling deadline goes after dated ones
    ]
    titles = [m["title"] for m in sorted(items, key=match_sort_key)]
    assert titles == [
        "eligible-3-1.0", "eligible-40-1.0", "eligible-None-1.0",
        "partial-50-0.8", "partial-5-0.3", "needs_review-None-0.0", "closed--10-1.0",
    ]


def test_llm_cannot_override_rule_verdict():
    # B7: an LLM that claims "eligible" with high confidence must not flip the verdict
    from app.agents.eligibility_agent import EligibilityAgent
    from app.agents.state import AgentState

    class FakeLLM:
        name = "fake"

        def generate_json(self, *a, **k):
            return {"eligible": True, "confidence": 0.99, "additional_reasons": ["looks fine"],
                    "additional_gaps": ["confirm income"]}

    state = AgentState(profile=PROFILE, raw_opportunities=[
        {"id": "s1", "title": "SC only", "criteria": {"category": ["SC"]}},
    ])
    EligibilityAgent(FakeLLM()).execute(state)
    m = state.matches[0]
    assert m["eligible"] is False and m["status"] == "partial"
    assert "looks fine" in m["notes"] and "Check: confirm income" in m["notes"]


def test_simulation_mode_skips_llm_regardless_of_name():
    # B6: simulation used to be detected by profile name == "Simulation"
    from app.agents.eligibility_agent import EligibilityAgent
    from app.agents.state import AgentState

    calls = []

    class CountingLLM:
        name = "fake"

        def generate_json(self, *a, **k):
            calls.append(1)
            return {}

    opp = {"id": "s1", "title": "x", "criteria": {"category": ["OBC"]}}
    EligibilityAgent(CountingLLM()).execute(
        AgentState(profile={**PROFILE, "name": "Simulation"}, raw_opportunities=[opp]))
    assert calls == [1]  # a real user named "Simulation" gets the full run
    EligibilityAgent(CountingLLM()).execute(
        AgentState(profile={**PROFILE, "name": "Asha"}, raw_opportunities=[opp], mode="simulate"))
    assert calls == [1]


def test_past_deadline_is_closed():
    from app.agents.eligibility_agent import EligibilityAgent
    from app.agents.state import AgentState
    from app.llm.provider import MockProvider

    past = (date.today() - timedelta(days=1)).isoformat()
    state = AgentState(profile=PROFILE, raw_opportunities=[
        {"id": "a", "title": "A", "deadline": past, "criteria": {"category": ["OBC"]}},
    ])
    EligibilityAgent(MockProvider()).execute(state)
    assert state.matches[0]["eligible"] is True
    assert state.matches[0]["status"] == "closed"
