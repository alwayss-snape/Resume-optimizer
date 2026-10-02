"""P8.17: a fairer match for non-tech resumes."""
from app.analysis.keyword_match import KeywordMatcher, is_place, tokens
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Education, Experience, Resume, ResumeBullet


def _rows(keywords, text, education=None, raw="", certs=(), edu_kw=()):
    resume = Resume(candidate=Candidate(name="A"), education=education or [],
                    experience=[Experience(id="e1", company="Acme", title="Rep",
                                           bullets=[ResumeBullet(id="b1", text=text)])])
    job = JobDescription(raw_text=raw or " ".join(keywords), keywords=list(keywords), certifications=list(certs),
                         education=list(edu_kw), requirements=[Requirement(id="r1", text=raw or " ".join(keywords))])
    return {r.keyword: r for r in KeywordMatcher().match(job, resume).rows}


def test_alternatives_slashes_heads_and_acronyms():
    rows = _rows(["OSHA 10 or 30", "Compact/NLC", "English/Spanish", "Salesforce CRM", "NetSuite or Oracle ERP"],
                 "Holds OSHA 30 and an NLC licence; fluent in Spanish; used Salesforce and NetSuite")
    assert rows["OSHA 10 or 30"].found and rows["Salesforce CRM"].found and rows["NetSuite or Oracle ERP"].found
    assert rows["Compact/NLC"].credit == 0.5 and rows["English/Spanish"].credit == 0.5
    rows = _rows(["GAAP", "LOTO"], "Prepared statements under generally accepted accounting principles; lockout/tagout")
    assert rows["GAAP"].found and rows["LOTO"].found
    rows = _rows(["Revenue Recognition Standard"], "Applied the RRS to contracts",
                 raw="Knowledge of the Revenue Recognition Standard (RRS)")
    assert rows["Revenue Recognition Standard"].found


def test_degree_hierarchy_places_and_unicode():
    rows = _rows([], "x", education=[Education(id="d", institution="Baruch College", degree="Master of Accountancy")],
                 raw="Bachelor's degree in Accounting", edu_kw=["Bachelor's degree"])
    assert rows["Bachelor's degree"].found
    rows = _rows(["Spring Boot"], "Graduated Spring 2019")
    assert not rows["Spring Boot"].found
    assert is_place("Arizona") and not is_place("Epic", "Epic, Cerner")
    rows = _rows(["Arizona", "Epic"], "Charted in Epic", raw="Nurse in Phoenix, Arizona. Epic required.")
    assert "Arizona" not in rows and rows["Epic"].found
    assert tokens("Enfermería")[0].startswith("enfermer") and len(tokens("Enfermería")[0]) > 8
