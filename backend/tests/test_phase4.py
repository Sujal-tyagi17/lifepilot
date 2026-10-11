"""Phase 4: what would change it, priority planner, knowledge graph, document check, Hindi answers."""
from datetime import date, timedelta

from app.services import counterfactual, doc_verify, graph, planner
from app.services.doc_types import doc_type, owned_types

from tests.conftest import PROFILE


def _run(client, guest):
    pid, h = guest
    assert client.post(f"/api/agent/run/{pid}", headers=h).status_code == 200
    return pid, h


# ── Document types ──────────────────────────────────────────

def test_document_names_map_to_one_type():
    assert doc_type("Income certificate (< ₹2.5 lakh)") == doc_type("Family income certificate") == "income"
    assert doc_type("Aadhaar card") == "aadhaar"
    assert doc_type("Something unusual").startswith("other:")
    assert owned_types(["aadhaar card", "income certificate"]) == {"aadhaar", "income"}


# ── What would change it ────────────────────────────────────

def test_counterfactuals_never_suggest_protected_attributes():
    res = counterfactual.counterfactuals(dict(PROFILE, category="General", annual_income=900000))
    assert res["suggestions"], "a General-category profile with high income should have something to unlock"
    for s in res["suggestions"]:
        assert s["count"] == len(s["unlocks"]) > 0
        for c in s["changes"]:
            assert c["field"] not in ("category", "gender", "age", "state")
    assert "truthfully" in res["note"]


def test_counterfactual_unlocks_are_really_unlocked():
    from app.services.eligibility import evaluate
    prof = dict(PROFILE, category="General", annual_income=900000)
    schemes = {s["id"]: s for s in counterfactual._schemes()}
    res = counterfactual.counterfactuals(prof)
    s = res["suggestions"][0]
    changed = dict(prof)
    for c in s["changes"]:
        changed[c["field"]] = c["value"]
    for u in s["unlocks"]:
        assert evaluate(changed, schemes[u["id"]]).eligible
        assert not evaluate(prof, schemes[u["id"]]).eligible


def test_counterfactual_endpoint_needs_ownership(client, guest):
    pid, h = _run(client, guest)
    assert client.get(f"/api/counterfactuals/{pid}").status_code in (403, 404)
    r = client.get(f"/api/counterfactuals/{pid}", headers=h)
    assert r.status_code == 200 and "suggestions" in r.json()


# ── Planner ─────────────────────────────────────────────────

def _m(title, deadline_days, docs, amount="₹50,000 per year", status="eligible"):
    return {"opportunity_id": title, "title": title, "status": status, "amount": amount, "confidence": 1.0,
            "deadline": (date.today() + timedelta(days=deadline_days)).isoformat() if deadline_days is not None else None,
            "documents": docs}


def test_planner_gets_shared_document_first_and_respects_hours():
    matches = [_m("A", 40, ["Income certificate", "Aadhaar card"]), _m("B", 50, ["Family income certificate"]),
               _m("C", 60, ["Bonafide certificate"], amount="₹5,000 per year")]
    res = planner.plan(matches, hours_per_week=6, owned=["aadhaar card"])
    assert res["totals"]["documents"] == 2 and res["totals"]["schemes"] == 3
    first = [t["id"] for t in res["weeks"][0]["tasks"]]
    assert "doc:income" in first                       # one document unblocks two schemes
    for w in res["weeks"]:
        assert w["hours_used"] <= 6 + 1e-9
    # a scheme is never planned before the documents it needs
    seen = set()
    for w in res["weeks"]:
        for t in w["tasks"]:
            if t["id"] == "scheme:A":
                assert "doc:income" in seen
        seen |= {t["id"] for t in w["tasks"]}


def test_planner_more_hours_means_fewer_weeks():
    matches = [_m(f"S{i}", 70, [f"Income certificate", "Bonafide certificate"]) for i in range(5)]
    slow = planner.plan(matches, hours_per_week=2)
    fast = planner.plan(matches, hours_per_week=20)
    assert len(fast["weeks"]) < len(slow["weeks"])


def test_planner_flags_missed_and_ignores_partial():
    matches = [_m("Soon", 2, ["Disability certificate"]), _m("Partial", 30, [], status="partial")]
    res = planner.plan(matches, hours_per_week=2)
    titles = [t["title"] for w in res["weeks"] for t in w["tasks"]] + [t["title"] for t in res["missed"]]
    assert not any("Partial" in t for t in titles)
    assert any("Soon" in t for t in [t["title"] for t in res["missed"]]) or res["totals"]["at_risk"]


def test_planner_endpoint_with_jobs(client, guest):
    pid, h = _run(client, guest)
    body = {"hours_per_week": 8, "owned_documents": ["Aadhaar card"],
            "jobs": [{"id": "j1", "title": "Data analyst", "company": "Acme", "fit_score": 0.8}],
            "skill": {"skill": "SQL", "jobs": 4}}
    r = client.post(f"/api/planner/{pid}", headers=h, json=body)
    assert r.status_code == 200
    res = r.json()
    kinds = {t["kind"] for w in res["weeks"] for t in w["tasks"]} | {t["kind"] for t in res["not_scheduled"]}
    assert {"job", "skill"} <= kinds
    assert res["totals"]["value"] >= res["totals"]["naive_value"] * 0.9


# ── Knowledge graph ─────────────────────────────────────────

def test_graph_nodes_edges_and_missing_document():
    g = graph.build_graph(PROFILE, ["aadhaar card"])
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
    kinds = {n["kind"] for n in g["nodes"]}
    assert kinds == {"scheme", "document", "criterion"}
    assert next(n for n in g["nodes"] if n["id"] == "doc:aadhaar")["have"] is True
    top = g["insights"]["most_valuable_missing_document"]
    if top:
        assert top["id"] != "doc:aadhaar" and top["schemes"]


def test_graph_endpoint(client, guest):
    pid, h = _run(client, guest)
    r = client.post(f"/api/graph/{pid}", headers=h, json={"owned_documents": []})
    assert r.status_code == 200 and r.json()["insights"]["counts"]["scheme"] > 0


# ── Document check ──────────────────────────────────────────

INCOME = ("Government of Karnataka Revenue Department INCOME CERTIFICATE This is to certify that Aisha Kumar "
          "resident of Bengaluru has annual family income of Rs. 2,90,000 Issued on {d} Tehsildar")


def test_verify_income_certificate_ok():
    d = (date.today() - timedelta(days=60)).strftime("%d-%m-%Y")
    res = doc_verify.verify(INCOME.format(d=d), PROFILE, [450000, 800000])
    assert res["type"] == "income"
    assert res["fields"]["annual_income"] == 290000
    assert res["verdict"] == "ok", res["checks"]


def test_verify_flags_old_certificate_and_wrong_name():
    d = (date.today() - timedelta(days=500)).strftime("%d-%m-%Y")
    res = doc_verify.verify(INCOME.format(d=d).replace("Aisha Kumar", "Rohan Verma"), PROFILE, [250000])
    bad = {c["check"] for c in res["checks"] if c["ok"] is False}
    assert {"validity", "name", "income_limit_250000"} <= bad
    assert res["verdict"] == "check"


def test_verify_masks_numbers():
    res = doc_verify.verify("Unique Identification Authority of India Aadhaar Aisha Kumar 1234 5678 9012 DOB 01/01/2004", PROFILE)
    assert "1234" not in res["preview"] and "9012" in res["preview"]
    assert res["fields"].get("aadhaar_last4") == "9012"


def test_verify_endpoint_lists_matching_document_names(client, guest):
    pid, h = _run(client, guest)
    d = date.today().strftime("%d-%m-%Y")
    r = client.post("/api/documents/verify", headers=h, json={"profile_id": pid, "text": INCOME.format(d=d)})
    assert r.status_code == 200
    assert all(doc_type(x) == "income" for x in r.json()["documents"])
    # someone else's profile cannot be used
    assert client.post("/api/documents/verify", json={"profile_id": pid, "text": "x"}).status_code in (403, 404)


# ── Jobs: what would change it ──────────────────────────────

def test_skill_counterfactuals():
    from app.jobs import matching
    from app.jobs.sources import sample_jobs
    rep = matching.match_report(sample_jobs(), {"education_level": "Undergraduate", "field_of_study": "Computer Science"},
                                resume_text="Skills: Python, Excel. Projects: built a dashboard in Excel", desired_role="data analyst")
    rows = rep["what_would_change"]
    assert isinstance(rows, list)
    for r in rows:
        assert r["above_after"] == r["above_before"] + r["jobs_gained"]


# ── Hindi answers ───────────────────────────────────────────

def test_hindi_question_gets_hindi_answer():
    from app.knowledge import rag
    assert rag.detect_intent("कौन से दस्तावेज चाहिए?")["label"] == "documents"
    matches = [_m("Test scholarship", 20, ["Income certificate"])]
    ans = rag._offline_answer("मैं किन योजनाओं के लिए पात्र हूँ?", matches, PROFILE)
    assert "पात्र" in ans and "Test scholarship" in ans


def test_planner_beats_nearest_deadline_first_when_time_is_short():
    # Two hours this week, two applications of 1.5 h closing this week: the bigger one should win
    matches = [_m("Small", 3, [], amount="₹5,000 per year"), _m("Big", 5, [], amount="₹2,00,000 per year")]
    res = planner.plan(matches, hours_per_week=2)
    assert res["weeks"][0]["tasks"][0]["title"] == "Apply to Big"
    assert res["totals"]["value"] > res["totals"]["naive_value"]
