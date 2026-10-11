"""Phase 2: reading resumes and job posts, fit v2, roadmaps."""
from app.jobs.catalog import classify_role
from app.jobs.jobparse import analyse_job, required_education, required_years
from app.jobs.matching import candidate, match_report, score_with
from app.jobs.resume import analyse_resume
from app.jobs.roadmap import build_plan, learning_order, scaled_weeks
from app.jobs.sources import sample_jobs, search_jobs

RESUME = """Asha Verma
Skills
Python, JavaScript, React, SQL, Git
Experience
Software Intern, ABC Pvt Ltd  Jun 2024 - Aug 2024
Built REST APIs with FastAPI and PostgreSQL
Projects
Chat app using Node.js and MongoDB
Education
B.Tech Computer Science 2021-2025
"""


def test_resume_strength_comes_from_where_a_skill_appears():
    r = analyse_resume(RESUME, ["Docker"])
    s = r["strength"]
    assert s["FastAPI"] == 3 and s["Node.js"] == 2 and s["React"] == 1
    assert s["Python"] == 3            # implied: FastAPI at work means Python at work
    assert s["Docker"] == 1 and r["typed_only"] == ["Docker"]
    assert r["internships"] == 1 and r["years"] == 0
    assert r["degree"]["label"] == "Bachelor's degree"
    assert {"experience", "projects", "skills", "education"} <= set(r["sections"])


def test_resume_years_from_dates_and_statements():
    r = analyse_resume("Experience\nDeveloper, XYZ  Jan 2020 - Dec 2022\n")
    assert r["years"] == 3.0
    assert analyse_resume("Experience\n4+ years of experience in sales")["years"] == 4


def test_job_post_must_vs_nice_and_alternatives():
    a = analyse_job({"title": "Backend developer", "description":
                     "Requirements: Python, Django or FastAPI, SQL. Good to have: Docker, AWS. "
                     "Experience: 1-3 years. Education: Bachelor's degree; MBA is a plus."})
    assert ["Django", "FastAPI"] in a["must_units"] and ["Python"] in a["must_units"]
    assert a["nice"] == ["Docker", "AWS"]
    assert (a["min_years"], a["max_years"]) == (1, 3)
    assert a["education"] == (5, "Bachelor's degree")   # the lowest it accepts
    assert a["family"] == "backend"


def test_years_and_education_parsing():
    assert required_years("Freshers welcome.") == (0, None)
    assert required_years("Minimum 2+ years of experience in Java.") == (2, None)
    assert required_years("Founded 50 years ago.") is None
    assert required_education("12th pass or diploma") == (3, "12th pass")


def test_classifier_labels_every_sample_role():
    for j in sample_jobs():
        a = analyse_job({**j, "family": None})
        assert a["family"] == j["family"], j["title"]
    assert classify_role("Accountant")[0] == "accounts"
    assert classify_role("Chef")[0] is None


def test_proof_raises_fit():
    job = {"title": "Python developer", "description": "Requirements: Python, SQL."}
    listed = score_with(job, candidate({}, "Skills\nPython, SQL"))
    worked = score_with(job, candidate({}, "Experience\nUsed Python and SQL daily at ACME"))
    assert worked["fit_score"] > listed["fit_score"]
    assert listed["skills_weak"] == ["Python", "SQL"] and worked["skills_weak"] == []


def test_either_alternative_satisfies_a_requirement():
    job = {"title": "Dev", "description": "Requirements: Django or FastAPI."}
    r = score_with(job, candidate({}, "", user_skills=["FastAPI"]))
    assert r["skills_missing"] == [] and r["skills_matched"] == ["FastAPI"]
    r = score_with(job, candidate({}, "", user_skills=["Java"]))
    assert r["skills_missing"] == ["FastAPI"] and r["alternatives"] == {"FastAPI": ["Django"]}  # fewer weeks to learn


def test_experience_gap_is_shown():
    job = {"title": "Senior developer", "description": "Requirements: Python. Experience: 5+ years."}
    r = score_with(job, candidate({}, RESUME))
    assert any("5+ years" in u for u in r["unmet"])


def test_target_role_first_then_resume_fits():
    jobs = search_jobs("data scientist", live=False, limit=0, filter_samples=False)
    rep = match_report(jobs, {"education_level": "Undergraduate"}, RESUME, "Data scientist")
    groups = [j["group"] for j in rep["jobs"]]
    assert groups == sorted(groups, key=["target", "other", "weak"].index)
    assert rep["jobs"][0]["family"] == "data_scientist"
    assert rep["insight"] and rep["insight"]["fit_after"] > rep["insight"]["fit_before"]


def test_resume_alone_picks_the_family():
    rep = match_report(sample_jobs(), {}, RESUME)
    assert rep["target_family"] == "backend" and rep["target_from"] == "resume"


def test_roadmap_orders_prerequisites_and_scales_time():
    order = [s for s, _ in learning_order(["Kubernetes"], lambda s: False)]
    assert order == ["Linux", "Docker", "Kubernetes"]
    assert scaled_weeks(2, 4) == 4 and scaled_weeks(2, 16) == 1
    job = next(j for j in sample_jobs() if j["id"] == "sample-001")
    cand = candidate({}, "Skills\nGit")
    slow, fast = build_plan(job, cand, 4), build_plan(job, cand, 16)
    assert slow["total_weeks"] > fast["total_weeks"]
    learn = [s["skills"][0] for s in slow["steps"] if s["kind"] == "learn"]
    assert learn.index("Python") < learn.index("FastAPI")
    weeks = [(s["start_week"], s["end_week"]) for s in slow["steps"]]
    assert all(b[0] == a[1] + 1 for a, b in zip(weeks, weeks[1:]))
    assert slow["fit_after"] > slow["fit_start"]
    assert any("Git" in f for f in slow["resume_fixes"])


def test_plan_without_resume_asks_for_one():
    job = next(j for j in sample_jobs() if j["id"] == "sample-001")
    plan = build_plan(job, candidate({}, "", user_skills=["Python"]))
    assert "resume" in plan["resume_fixes"][0].lower()
