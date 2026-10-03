"""P8.20: job conditions that aren't keywords, apart from the score."""
from datetime import date

from app.analysis.checklist import build_checklist
from app.analysis.jd_analyzer import JDAnalyzer
from app.domain.resume import Candidate, Experience, Resume

JD = """Registered Nurse - ICU
Requirements:
- Current RN license in Arizona or compact (NLC) state
- Minimum 2 years of acute care experience; 1 year ICU preferred
- Ability to work 12-hour night shifts, weekends and holidays
- Ability to lift 50 lbs and stand for extended periods
- Bilingual English/Spanish a plus
- Knowledge of HIPAA regulations"""


def test_conditions_come_from_the_jd_lines_and_years_are_checked():
    resume = Resume(candidate=Candidate(name="M"), experience=[
        Experience(id="e1", company="Banner", title="RN", start_date="Mar 2021", end_date="Present")])
    items = build_checklist(JDAnalyzer().analyze(JD), resume, today=date(2026, 10, 3))
    kinds = [c.kind for c in items]
    assert kinds == ["licence", "years", "schedule", "physical", "language"]  # HIPAA is a keyword, not a condition
    years = next(c for c in items if c.kind == "years")
    assert years.auto == "met" and "5.7 years" in years.note
    assert all(c.text in JD for c in items)  # verbatim
