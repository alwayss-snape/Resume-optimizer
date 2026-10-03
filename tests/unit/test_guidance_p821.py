"""P8.21: a low match is explained, not just "aim for 75-85%"."""
from app.analysis.keyword_match import KeywordMatcher
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet


def _report(title, bullets, keywords, job_title):
    resume = Resume(candidate=Candidate(name="A"), experience=[Experience(id="e1", company="X", title=title,
        bullets=[ResumeBullet(id=f"b{i}", text=t) for i, t in enumerate(bullets)])])
    job = JobDescription(job_title=job_title, raw_text=" ".join(keywords), keywords=keywords, analysis_source="llm",
                         requirements=[Requirement(id="r1", text=" ".join(keywords))])
    return KeywordMatcher().match(job, resume)


def test_a_nurse_applying_for_sales_is_told_it_is_another_field():
    r = _report("Registered Nurse", ["Provided patient care in Epic"], ["Salesforce", "MEDDIC", "quota", "Gong"],
                "Enterprise Account Executive")
    assert r.guidance and r.guidance["kind"] == "different_field" and len(r.guidance["tips"]) >= 3


def test_a_good_match_gets_no_guidance_and_a_partial_one_a_stretch_note():
    good = _report("Data Analyst", ["Built SQL and Tableau dashboards in Python"], ["SQL", "Tableau", "Python"],
                   "Data Analyst")
    assert good.guidance is None
    stretch = _report("Data Analyst", ["Built SQL reports"], ["SQL", "Tableau", "Python", "dbt"], "Data Analyst")
    assert stretch.guidance and stretch.guidance["kind"] == "stretch"
