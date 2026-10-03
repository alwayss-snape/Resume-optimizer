"""P8.18: JD cleanup, an honest offline fallback, and requirement statuses
that agree with the keyword table."""
from app.analysis.jd_analyzer import JDAnalyzer
from app.analysis.keyword_match import KeywordMatcher, reconcile
from app.domain.report import Match
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet

JD = """Senior Accountant
<p>🚀 Join us! 💼</p>
Requirements:
- Knowledge of Generally Accepted Accounting Principles and Lean Six Sigma
- forklift and wound care
- Supply Chain planning in SAP
Benefits
Dental, Vision, PTO, 401(k), tuition reimbursement
We are an Equal Opportunity Employer and ADA compliant."""


def test_clean_text_drops_html_entities_and_emoji():
    assert JDAnalyzer.clean_text("<h2>🚀 Senior Accountant 💼</h2><li>US GAAP &amp; SOX</li>") == \
        "Senior Accountant\n\n- US GAAP & SOX"


def test_offline_keywords_keep_phrases_and_trade_terms_but_no_perks():
    job = JDAnalyzer().analyze(JD)
    low = [k.lower() for k in job.keywords]
    for kept in ("generally accepted accounting principles", "lean six sigma", "supply chain", "forklift", "wound care"):
        assert kept in low, (kept, low)
    for perk in ("dental", "vision", "pto", "ada", "chain", "sigma"):
        assert perk not in low, perk
    assert job.analysis_source == "heuristic"


def test_too_short_and_approximate_flag():
    assert JDAnalyzer.too_short("Data Analyst") and not JDAnalyzer.too_short(JD)
    resume = Resume(candidate=Candidate(name="A"))
    assert KeywordMatcher().match(JDAnalyzer().analyze(JD), resume).approximate is True


def test_requirement_status_agrees_with_the_keywords():
    """P1.16: all of the line's keywords found -> supported, some -> partly."""
    resume = Resume(candidate=Candidate(name="A"), experience=[Experience(id="e1", company="A", title="DS", bullets=[
        ResumeBullet(id="b1", text="Trained PyTorch and XGBoost models in Python")])])
    job = JDAnalyzer().analyze("ML Engineer\nRequirements:\n- Proficient in Python and libraries like PyTorch and "
                               "XGBoost\n- Experience with Kafka and Python streaming jobs\n- Familiar with Rust")
    report = KeywordMatcher().match(job, resume)
    matches = [Match(requirement_id=r.id, requirement_text=r.text, status="MISSING") for r in job.requirements]
    by = {m.requirement_text[:12]: m.status for m in reconcile(matches, report)}
    assert by["Proficient i"] == "SUPPORTED" and by["Experience w"] == "PARTIAL" and by["Familiar wit"] == "MISSING"
