"""Phase 3: trained models, explanations, describe-yourself, ML Lab endpoints."""
import pytest

from app.config import settings
from app.ml import predict
from app.ml.describe import describe


def test_models_are_trained_and_metrics_are_real(client):
    m = client.get("/api/ml/metrics").json()
    assert m["trained"] and set(m["models"]) == {"fit", "role", "skills", "document", "intent", "search"}
    fit = m["models"]["fit"]
    assert fit["test"]["accuracy"] > fit["rules_baseline"]["accuracy"] - 0.05
    assert abs(sum(fit["weights"]["learned"].values()) - 1) < 0.01
    cm = fit["test"]["confusion_matrix"]
    assert sum(map(sum, cm)) == fit["dataset"]["test"]


def test_role_classifier_and_fallback():
    from app.jobs.catalog import classify_role
    assert classify_role("We need someone to run Instagram ads and SEO campaigns")[0] == "marketing"
    assert classify_role("Staff nurse for the ICU ward")[0] == "healthcare"
    assert classify_role("Chef")[0] is None          # not sure: no family rather than a guess
    r = predict.role_family_explained("Python developer to build REST APIs with Django and SQL")
    assert r["label"] in ("backend", "software") and r["because"]


def test_missing_models_fall_back_to_rules(monkeypatch, tmp_path):
    from app.jobs.catalog import classify_role
    monkeypatch.setattr(predict, "MODELS", tmp_path)
    predict.reload()
    try:
        assert predict.role_family("Data analyst") is None and predict.fit_weights() is None
        assert classify_role("Data analyst")[0] == "data_analyst"     # keyword rules still work
        from app.jobs.matching import HAND_WEIGHTS, weights
        assert weights() == HAND_WEIGHTS
    finally:
        monkeypatch.undo()
        predict.reload()


@pytest.mark.parametrize("q,intent", [
    ("Which schemes do I qualify for?", "eligibility"), ("kaun kaun se documents lagenge", "documents"),
    ("आवेदन की आखिरी तारीख कब है?", "deadlines"), ("how much money will I get", "benefits"),
    ("apply kaise karein", "how_to_apply"), ("which jobs suit my skills", "jobs"),
])
def test_intents_in_english_hindi_hinglish(q, intent):
    from app.knowledge.rag import detect_intent
    assert detect_intent(q)["label"] == intent


def test_assistant_reply_carries_intent(client, guest):
    pid, headers = guest
    client.post(f"/api/agent/run/{pid}", headers=headers)
    r = client.post("/api/agent/assistant", headers=headers, json={"profile_id": pid, "question": "documents kya chahiye"}).json()
    assert r["intent"]["label"] == "documents" and "Instructions" not in r["answer"]


def test_document_type_with_reasons():
    r = predict.document_type("This is to certify that the annual family income is Rs 2,40,000. Tehsildar")
    assert r["label"] == "income" and any(w["term"].lower() == "income" for w in r["because"])


def test_describe_yourself():
    r = describe("I'm Aisha, a 21-year-old girl from Bengaluru doing B.Tech in computer science, OBC, "
                 "family income 3 lakh, I want a job")["profile"]
    assert r == {"name": "Aisha", "age": 21, "gender": "Female", "state": "Karnataka", "category": "OBC",
                 "education_level": "Undergraduate", "field_of_study": "Computer Science", "annual_income": 300000,
                 "goals": "get a job"}
    hi = describe("मेरा नाम प्रिया है, 19 साल की लड़की, उत्तर प्रदेश, बी.कॉम, ओबीसी, आय 2 लाख")["profile"]
    assert hi["state"] == "Uttar Pradesh" and hi["annual_income"] == 200000 and hi["gender"] == "Female"
    assert describe("no disability, 12th pass from Patna")["profile"].get("disability") is None


def test_fuzzy_skills_catch_typos_not_words():
    from app.jobs.skills import extract_skills_fuzzy
    assert {"Python", "JavaScript", "Kubernetes"} <= set(extract_skills_fuzzy("Pyhton, Javascrpt and Kubernets"))
    assert extract_skills_fuzzy("I expressed interest in station management") == []


def test_predict_endpoints(client):
    assert client.post("/api/ml/predict/intent", json={"text": "last date kab hai"}).json()["model"]["label"] == "deadlines"
    fit = client.post("/api/ml/predict/fit", json={"job_text": "Data analyst. Requirements: Excel, SQL, Power BI.",
                                                    "resume_text": "Skills\nExcel, SQL\nProjects\nPower BI dashboard",
                                                    "target_role": "Data analyst"}).json()
    assert set(fit["probabilities"]) == {"Good", "Okay", "Poor"} and 0 <= fit["learned_fit"] <= 1
    assert client.post("/api/ml/describe", json={"text": "SC girl from Delhi"}).json()["profile"]["category"] == "SC"


def test_labelling_writes_team_file_and_is_off_in_production(client, monkeypatch, tmp_path):
    from app.routers import ml
    monkeypatch.setattr(ml, "TEAM_FILE", tmp_path / "team.csv")
    pair = client.get("/api/ml/label/next").json()["pair"]
    body = {k: pair[k] for k in ("job_title", "job_text", "resume_text", "education_level", "target_role")}
    r = client.post("/api/ml/label", json={**body, "label": "Good", "labelled_by": "Sujal"})
    assert r.status_code == 200 and (tmp_path / "team.csv").read_text().count("Sujal") == 1
    monkeypatch.setattr(settings, "environment", "production")
    assert client.post("/api/ml/label", json={**body, "label": "Poor"}).status_code == 403
    assert client.post("/api/ml/retrain").status_code == 403


def test_fixes_from_the_ml_lab_test_sheet():
    from app.jobs.resume import analyse_resume
    from app.knowledge.rag import detect_intent
    # T9: no known words -> no guess, in the Lab and in the app
    assert predict.role_family_explained("Chef for an Italian restaurant") is None
    # T15: small talk has its own intent now
    assert detect_intent("hello how are you")["label"] == "other"
    # T14: two questions in one
    both = detect_intent("When is the last date and what documents do I need?")
    assert {both["label"], both.get("also")} == {"documents", "deadlines"}
    # T16: "Projects: ..." on one line is still the Projects section
    ev = {s["name"]: s["evidence"] for s in analyse_resume(
        "Skills: Pyhton, MS Excel\nProjects: dashboard in Power BI with SQL\nExperience: intern, built REST APIs with FastAPI")["skills"]}
    assert ev["FastAPI"] == "work" and ev["SQL"] == "project" and ev["Python"] == "work"
