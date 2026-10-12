"""Skill extraction and job fit scoring (B2, B3, B4)."""
from app.jobs.matching import score_job
from app.jobs.skills import canonical, extract_skills
from app.jobs.sources import sample_jobs, search_jobs


def test_no_substring_false_positives():
    # B3: "ai" used to match "maintain", "go" matched "good"
    assert extract_skills("We maintain good systems. Go ahead and apply. R&D team, C-suite.") == []


def test_skills_found_with_boundaries():
    found = extract_skills("Requirements: Go, Python, SQL, C++ and C#. Node.js, REST APIs, MySQL.")
    for s in ["Go", "Python", "SQL", "C++", "C#", "Node.js", "REST APIs", "MySQL"]:
        assert s in found
    assert "Java" not in extract_skills("JavaScript only")


def test_canonical_names_for_typed_skills():
    assert canonical("reactjs") == "React"
    assert canonical("ml") == "Machine Learning"
    assert canonical("not-a-skill") is None


JOB = {"title": "Backend Engineer", "description": "Requirements: Python, SQL, Docker, Redis. Bachelor's degree."}


def test_unrelated_job_scores_zero_not_fifty():
    # B4: every job used to start at 50%
    r = score_job({"title": "Chef", "description": "Cook Italian food. Bachelor's degree in hospitality."},
                  {"education_level": "Undergraduate"}, resume_text="Python", desired_role="Backend Engineer")
    assert r["fit_score"] < 0.5
    assert score_job(JOB, {}, resume_text="", desired_role="")["fit_score"] == 0.0


def test_breakdown_explains_score():
    r = score_job(JOB, {"education_level": "Undergraduate"}, resume_text="Python and SQL", desired_role="Backend Engineer")
    assert r["skills_matched"] == ["Python", "SQL"]
    assert r["skills_missing"] == ["Docker", "Redis"]
    assert abs(sum(b["points"] for b in r["fit_breakdown"]) - 100 * r["fit_score"]) < 0.6
    assert r["eligible"]


def test_education_gap_detected_with_word_boundaries():
    r = score_job(JOB, {"education_level": "12th"}, resume_text="Python")
    assert not r["eligible"] and any("Bachelor" in u for u in r["unmet"])
    # "mastery" and "scrum master" must not read as a Master's degree requirement
    r2 = score_job({"title": "Dev", "description": "Mastery of Python. Work with the scrum master."},
                   {"education_level": "Undergraduate"}, resume_text="Python")
    assert r2["eligible"]


def test_sample_jobs_never_carry_invented_salary():
    # B2: salaries used to be made up from the job title
    for j in sample_jobs():
        assert j["source"] == "sample"
        assert j["salary"] is None and j["salary_min"] is None


def test_search_offline_uses_samples_only():
    jobs = search_jobs("backend")
    assert jobs and all(j["source"] == "sample" for j in jobs)
