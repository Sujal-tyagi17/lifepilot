"""End-to-end API behaviour with the network off."""
import io

from app.agents import orchestrator


def test_pipeline_statuses_and_order(client, guest):
    pid, headers = guest
    data = client.post(f"/api/agent/run/{pid}", headers=headers).json()
    statuses = [m["status"] for m in data["matches"]]
    assert statuses[0] == "eligible"
    assert statuses[-1] == "closed"  # PM YASASVI's 2026 deadline has passed
    rank = {"eligible": 0, "partial": 1, "needs_review": 2, "closed": 3}
    assert [rank[s] for s in statuses] == sorted(rank[s] for s in statuses)
    rolling = [m for m in data["matches"] if m["opportunity_id"] == "pmkvy-skill"][0]
    assert rolling["deadline"] is None and "Rolling" in rolling["deadline_note"]
    assert data["insights"]["eligible_count"] == statuses.count("eligible")


def test_saved_run_keeps_status(client, guest):
    pid, headers = guest
    client.post(f"/api/agent/run/{pid}", headers=headers)
    runs = client.get(f"/api/agent/runs/{pid}", headers=headers).json()
    assert runs[0]["matches"][0]["status"] in ("eligible", "partial", "needs_review", "closed")


def test_assistant_reuses_saved_run(client, guest, monkeypatch):
    # B5: every chat message used to re-run the whole pipeline
    pid, headers = guest
    client.post(f"/api/agent/run/{pid}", headers=headers)
    calls = []
    original = orchestrator.Orchestrator.run
    monkeypatch.setattr(orchestrator.Orchestrator, "run", lambda self, *a, **k: calls.append(1) or original(self, *a, **k))
    for q in ["which documents do I need?", "any deadlines?"]:
        r = client.post("/api/agent/assistant", json={"profile_id": pid, "question": q}, headers=headers)
        assert r.status_code == 200
    assert calls == []


def test_calendar_excludes_closed(client, guest):
    pid, headers = guest
    ics = client.get(f"/api/agent/calendar/{pid}", headers=headers).text
    assert "BEGIN:VCALENDAR" in ics and "YASASVI" not in ics


def test_simulate_any_name(client):
    body = {"name": "Simulation", "annual_income": 200000, "category": "SC", "education_level": "Undergraduate",
            "gender": "Female", "state": "Karnataka", "field_of_study": "Engineering"}
    r = client.post("/api/agent/simulate", json=body)
    assert r.status_code == 200 and r.json()["insights"]["eligible_count"] >= 1


def test_resume_parse_formats(client):
    import docx

    r = client.post("/api/resume/parse", files={"file": ("cv.txt", b"Python, SQL", "text/plain")})
    assert r.status_code == 200 and "Python" in r.json()["text"]
    buf = io.BytesIO()
    d = docx.Document()
    d.add_paragraph("Skills: React")
    d.save(buf)
    r = client.post("/api/resume/parse", files={"file": ("cv.docx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 200 and "React" in r.json()["text"]
    assert client.post("/api/resume/parse", files={"file": ("cv.exe", b"x", "application/octet-stream")}).status_code == 422
    assert client.post("/api/resume/parse", files={"file": ("cv.txt", b"", "text/plain")}).status_code == 422


def test_job_match_endpoint(client):
    r = client.post("/api/opportunities/jobs/match", json={
        "profile": {"education_level": "Undergraduate"}, "resume_text": "Python SQL", "desired_role": "Backend Engineer"})
    jobs = r.json()
    assert r.status_code == 200 and jobs
    assert jobs[0]["fit_score"] >= jobs[-1]["fit_score"]
    assert all(j["salary"] == "Not disclosed" and j["salary_num"] is None for j in jobs)
    assert "fit_breakdown" in jobs[0]


def test_list_opportunities_returns_curated(client):
    assert len(client.get("/api/opportunities").json()) == 10


def test_latest_run_survives_reload(client, guest):
    pid, headers = guest
    assert client.get(f"/api/agent/latest/{pid}", headers=headers).json() is None
    run = client.post(f"/api/agent/run/{pid}", headers=headers).json()
    latest = client.get(f"/api/agent/latest/{pid}", headers=headers).json()
    assert latest["id"] == run["id"]
    assert latest["insights"]["eligible_count"] == run["insights"]["eligible_count"]
    assert [m["opportunity_id"] for m in latest["matches"]] == [m["opportunity_id"] for m in run["matches"]]
    assert client.get(f"/api/agent/latest/{pid}").status_code == 404
