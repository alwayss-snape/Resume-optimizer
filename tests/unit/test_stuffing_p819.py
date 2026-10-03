"""P8.19: a Skills line pasted from the JD no longer beats real experience."""
from app.analysis.keyword_match import KeywordMatcher
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet

KEYWORDS = ["Salesforce", "MEDDIC", "Gong", "negotiation", "forecasting", "pipeline management", "B2B SaaS"]
JOB = JobDescription(raw_text=" ".join(KEYWORDS), keywords=KEYWORDS,
                     requirements=[Requirement(id="r1", text=", ".join(KEYWORDS))], analysis_source="llm")


def test_stuffed_skills_line_scores_below_real_experience():
    strong = Resume(candidate=Candidate(name="AE"), skills={"Tools": ["Salesforce", "Gong"]}, experience=[
        Experience(id="e1", company="CloudMetrics", title="Account Executive", bullets=[
            ResumeBullet(id="b1", text="Ran B2B SaaS deals in Salesforce using MEDDIC; recorded calls in Gong"),
            ResumeBullet(id="b2", text="Owned pipeline management and forecasting for a $1.2M quota")])])
    stuffed = Resume(candidate=Candidate(name="Barista"), skills={"Skills": KEYWORDS}, experience=[
        Experience(id="e1", company="Cafe", title="Barista", bullets=[ResumeBullet(id="b1", text="Made coffee")])])
    m = KeywordMatcher()
    strong_rate, stuffed_report = m.match(JOB, strong).rate, m.match(JOB, stuffed)
    assert stuffed_report.rate < strong_rate
    assert all(r.skills_only and r.credit == 0.25 for r in stuffed_report.rows if r.found)
