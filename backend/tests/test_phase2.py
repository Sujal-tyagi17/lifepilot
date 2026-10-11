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
    job = {"title": "Dev", "description": "Requirements: Django or FastAPI, SQL, Git."}
    r = score_with(job, candidate({}, "", user_skills=["FastAPI", "SQL", "Git"]))
    assert r["skills_missing"] == [] and r["skills_matched"] == ["FastAPI", "SQL", "Git"]
    r = score_with(job, candidate({}, "", user_skills=["Java", "SQL", "Git"]))
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


# ── Locations and live postings ──────────────────────────────

def test_location_ranking():
    from app.jobs.locations import find_state, location_rank
    assert find_state("Bangalore Urban") == "Karnataka"
    assert find_state("Gurgaon, Haryana, India") == "Haryana"
    assert find_state("New Delhi") == "Delhi"
    assert location_rank({"location": "Bengaluru, Karnataka"}, "Karnataka") == (0, "near")
    assert location_rank({"location": "Remote"}, "Karnataka") == (1, "remote")
    assert location_rank({"location": "Pune"}, "Karnataka") == (2, "india")
    assert location_rank({"location": "London"}, "Karnataka") == (3, "other")


def test_posting_titles_parsed():
    from app.jobs.sources import parse_posting_title
    assert parse_posting_title("Acme Analytics hiring Data Analyst in Bengaluru, Karnataka, India | LinkedIn") == \
        ("Data Analyst", "Acme Analytics", "Bengaluru, Karnataka, India")
    assert parse_posting_title("Data Analyst - Acme Pvt Ltd - 1 to 3 years - Pune") == ("Data Analyst", "Acme Pvt Ltd", "Pune")
    assert parse_posting_title("Python Developer - Zeta - Hyderabad, Telangana - Indeed.com") == \
        ("Python Developer", "Zeta", "Hyderabad, Telangana")
    assert parse_posting_title("Data Science internship at Foo Labs in Mumbai | Internshala") == \
        ("Data Science", "Foo Labs", "Mumbai")


def test_only_single_postings_are_kept(monkeypatch):
    import httpx
    from app.jobs import sources
    from app.config import settings
    monkeypatch.setattr(settings, "serper_api_key", "test")
    sources.clear_cache()
    organic = [
        {"title": "15759 Python Data Analytics Job Vacancies In Bangalore", "link": "https://www.naukri.com/python-data-analytics-jobs-in-bangalore", "snippet": "Apply"},
        {"title": "Acme hiring Data Analyst in Mysuru, Karnataka, India | LinkedIn", "link": "https://in.linkedin.com/jobs/view/data-analyst-at-acme-123", "snippet": "SQL, Excel, Power BI. 0-2 years.", "date": "2 days ago"},
    ]

    class Resp:
        status_code = 200
        def json(self):
            return {"organic": organic}

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): return Resp()

    monkeypatch.setattr(httpx, "Client", Client)
    jobs = sources.web_job_postings("Data analyst", "Karnataka")
    assert len(jobs) == 1
    j = jobs[0]
    assert (j["title"], j["company"], j["site"], j["source"]) == ("Data Analyst", "Acme", "LinkedIn", "web_job")
    rep = match_report(jobs + sample_jobs(), {"state": "Karnataka"}, "", "Data analyst")
    assert rep["jobs"][0]["id"] == j["id"] and rep["jobs"][0]["location_tag"] == "near"
    sources.clear_cache()


def test_company_named_after_a_city_is_not_the_location():
    from app.jobs.sources import parse_posting_title
    assert parse_posting_title("Junior Data Analyst - Mysore Infotech - 0 to 1 years - Mysuru") == \
        ("Junior Data Analyst", "Mysore Infotech", "Mysuru")


def test_search_failure_is_reported(monkeypatch):
    import httpx
    from app.jobs import sources
    from app.config import settings
    monkeypatch.setattr(settings, "serper_api_key", "bad")
    sources.clear_cache()

    class Resp:
        status_code = 403
        def json(self): return {"message": "Unauthorized"}

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): return Resp()

    monkeypatch.setattr(httpx, "Client", Client)
    assert sources.web_job_postings("Data analyst", "Karnataka") == []
    assert "key not accepted" in sources.source_status()["Google · Karnataka"]
    sources.clear_cache()


def test_company_career_pages_count_as_postings():
    from app.jobs.sources import _site_of
    assert _site_of("https://jobs.lever.co/acme/3f1c2a9e-1111-2222-3333-444455556666") == "Company site"
    assert _site_of("https://boards.greenhouse.io/acme/jobs/123456") == "Company site"
    assert _site_of("https://www.naukri.com/data-analyst-jobs-in-bangalore") is None


def test_fresher_does_not_get_senior_roles():
    fresher = candidate({"education_level": "Undergraduate"}, "Skills\nPython, SQL\nEducation\nB.Tech 2022-2026")
    senior = {"title": "Senior Software Engineer", "description": "Python, SQL."}
    junior = {"title": "Junior Python Developer", "description": "Python, SQL."}
    s, j = score_with(senior, fresher), score_with(junior, fresher)
    assert s["too_senior"] and s["group"] == "weak" and any("Senior role" in u for u in s["unmet"])
    assert not j["too_senior"] and j["group"] != "weak" and j["fit_score"] > s["fit_score"]
    # an experienced person still sees it
    pro = candidate({}, "Experience\nDeveloper, Acme  Jan 2018 - Dec 2023\nUsed Python and SQL")
    assert not score_with(senior, pro)["too_senior"]


def test_short_posts_are_not_overconfident():
    cand = candidate({}, "", user_skills=["Python"])
    thin = score_with({"title": "Python developer", "description": ""}, cand)
    assert thin["fit_score"] < 0.8


def test_closed_and_old_postings_are_dropped():
    from app.jobs.sources import is_open, posting_key
    assert not is_open({"title": "AI Software Engineer", "snippet": "No longer accepting applications", "date": "2 days ago"})
    assert not is_open({"title": "AI Software Engineer", "snippet": "Posted 10 months ago. Python."})
    assert not is_open({"title": "x", "snippet": "", "date": "3 months ago"})
    assert is_open({"title": "x", "snippet": "Apply now", "date": "5 days ago"})
    assert is_open({"title": "x", "snippet": "Apply now"})
    assert posting_key("https://in.linkedin.com/jobs/view/ai-software-engineer-at-zephy-4123456789?trk=x") == \
        posting_key("https://www.linkedin.com/jobs/view/4123456789")


def test_experience_from_the_form_without_resume():
    senior = {"title": "Senior Software Engineer", "description": "Python, SQL."}
    told_fresher = candidate({}, "", user_skills=["Python"], experience_years=0)
    told_five = candidate({}, "", user_skills=["Python"], experience_years=5)
    assert score_with(senior, told_fresher)["too_senior"]
    r = score_with(senior, told_five)
    assert not r["too_senior"] and any(b["signal"] == "experience" and b["value"] == 1 for b in r["fit_breakdown"])


def test_duplicate_without_company_is_dropped(monkeypatch):
    from app.jobs import sources
    a = sources._job(id="1", title="AI Software Engineer", company="Zephy", location="New Delhi, Delhi, India",
                     description="", url="https://www.linkedin.com/jobs/view/1111111", source="web_job")
    b = sources._job(id="2", title="AI Software Engineer", company=None, location="New Delhi",
                     description="", url="https://example.com/x", source="web_job")
    monkeypatch.setattr(sources, "sample_jobs", lambda: [])
    monkeypatch.setattr(sources.settings, "scraping_enabled", True)
    monkeypatch.setattr(sources, "web_job_postings", lambda q, w, fresher=False: [a, b])
    for name in ("adzuna_jobs", "jooble_jobs", "google_jobs"):
        monkeypatch.setattr(sources, name, lambda q, w, fresher=False: [])
    out = sources.search_jobs("AI engineer", location=None, include_rss=False, limit=0)
    assert [j["id"] for j in out] == ["1"]


def test_listing_pages_by_title_are_not_jobs():
    from app.jobs.sources import LISTING_TITLE
    for t in ["91758 Developer Job Vacancies In India", "Data Analyst Jobs in Bangalore - Apply Now",
              "1,200+ Python jobs in Pune", "Latest Software Engineer Jobs"]:
        assert LISTING_TITLE.search(t), t
    for t in ["Acme hiring Data Analyst in Pune | LinkedIn", "Python Developer - Zeta - Hyderabad"]:
        assert not LISTING_TITLE.search(t), t


def test_plan_for_a_thin_post_uses_typical_skills_and_experience():
    job = {"title": "Software Developer", "description": "Apply now."}
    fresher = candidate({}, "", desired_role="Software engineer", user_skills=["Python"], experience_years=0)
    plan = build_plan(job, fresher, 8)
    assert plan["typical_skills"] and len(plan["focus"]["learn"]) >= 2
    senior_job = {"title": "Software Developer", "description": "Python, SQL, Git, REST APIs. 3+ years of experience."}
    plan2 = build_plan(senior_job, fresher, 8)
    assert any(s["id"] == "experience" for s in plan2["steps"])
    pro = candidate({}, "", desired_role="Software engineer", user_skills=["Git"], experience_years=4)
    plan3 = build_plan({"title": "Django developer", "description": "Django, SQL, Git."}, pro, 8)
    assert any(s["title"].startswith("Brush up on") for s in plan3["steps"])
    slow, fast = build_plan(job, fresher, 4), build_plan(job, fresher, 30)
    assert slow["total_weeks"] > fast["total_weeks"]


def test_more_hours_never_makes_the_plan_longer():
    cand = candidate({"education_level": "Undergraduate"}, "", desired_role="Software engineer", user_skills=["Python"], experience_years=0)
    for job in [{"title": "Software Engineering Intern", "company": "Acme", "description": "Apply now."},
                next(j for j in sample_jobs() if j["id"] == "sample-001")]:
        weeks = [build_plan(job, cand, h)["total_weeks"] for h in (3, 6, 10, 16, 24, 32, 40)]
        assert weeks == sorted(weeks, reverse=True) and weeks[0] > weeks[-1], weeks
    a = build_plan({"title": "Software Engineering Intern", "company": "Acme", "description": "Apply now."}, cand, 10)
    b = build_plan({"title": "AI Software Engineer", "company": "Zephy", "description": "Python, machine learning, SQL."}, cand, 10)
    assert [s["title"] for s in a["steps"]] != [s["title"] for s in b["steps"]]
