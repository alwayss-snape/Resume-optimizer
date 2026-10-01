"""P3.5: "Check parsed resume" step: corrections applied by the service
(the web flow over HTTP is covered in test_api.py)."""
from app.services.tailor import TailorService

REPLICA = "tests/fixtures/resumes/replica_layout.pdf"


def _service():
    return TailorService(llm_client=None)


def test_corrections_change_header_and_roles_but_not_the_input():
    service = _service()
    parsed = service.parse_resume(REPLICA)
    corrections = {
        "candidate": {"name": "Jordan A. Avery", "headline": "Senior Data Scientist", "email": "jordan.avery@example.com",
                      "phone": "+91-9000000000", "location": "Pune, India",
                      "links": ["linkedin.com/in/jordan-avery", "  "]},
        "experience": [{"id": "exp_002", "company": "Blue Harbor Bank Ltd", "location": "Mumbai, India",
                        "roles": [{"title": "Analytics Intern", "start_date": "Jan 2021", "end_date": "Jun 2021"}]}],
    }
    (raw, doc, evidence), changed = service.apply_parse_corrections(parsed, corrections)
    cand = doc.resume.candidate
    assert changed
    assert (cand.name, cand.headline, cand.links) == ("Jordan A. Avery", "Senior Data Scientist",
                                                      ["linkedin.com/in/jordan-avery"])
    exp = doc.resume.experience[1]
    assert (exp.company, exp.start_date, exp.end_date) == ("Blue Harbor Bank Ltd", "Jan 2021", "Jun 2021")
    # Evidence for that job's bullets follows the new company name.
    assert any(e.text.startswith("Blue Harbor Bank Ltd: Cleaned loan") for e in evidence)
    assert doc.revisions[-1].actor == "user"
    # The parse kept in session state is not modified.
    assert parsed[1].resume.candidate.name == "Jordan Avery"
    assert parsed[1].resume.experience[1].company == "Blue Harbor Bank"


def test_unchanged_form_is_not_a_correction():
    service = _service()
    parsed = service.parse_resume(REPLICA)
    resume = parsed[1].resume
    c = resume.candidate
    corrections = {
        "candidate": {"name": c.name, "headline": "", "email": c.email, "phone": c.phone,
                      "location": c.location, "links": []},
        "experience": [{"id": e.id, "company": e.company, "location": e.location or "",
                        "roles": [r.model_dump() for r in e.all_roles()]} for e in resume.experience],
    }
    _, changed = service.apply_parse_corrections(parsed, corrections)
    assert changed is False


def test_promotion_roles_can_be_edited():
    service = _service()
    parsed = service.parse_resume(REPLICA)
    fix = {"experience": [{"id": "exp_001", "roles": [
        {"title": "Lead Data Scientist", "start_date": "March 2024", "end_date": "Present"},
        {"title": "Data Scientist", "start_date": "July 2021", "end_date": "March 2024"},
    ]}]}
    (_, doc, _), changed = service.apply_parse_corrections(parsed, fix)
    exp = doc.resume.experience[0]
    assert changed and exp.title == "Lead Data Scientist"
    assert [r.title for r in exp.all_roles()] == ["Lead Data Scientist", "Data Scientist"]


def test_a_dated_role_without_a_title_is_kept():
    """P5.3 review: a role read with dates but no title must survive an
    untouched submit of the details form."""
    from app.domain.resume import Candidate, Experience, Resume
    from app.domain.resume_document import ResumeDocument
    service = _service()
    resume = Resume(candidate=Candidate(name="Avery Lee"), experience=[Experience(id="exp_1", company="Acme", title="", start_date="Jan 2020", end_date="Dec 2021")])
    parsed = (None, ResumeDocument(resume=resume), [])
    fixed, changed = service.apply_parse_corrections(parsed, {"experience": [
        {"id": "exp_1", "company": "Acme", "location": "",
         "roles": [{"title": "", "start_date": "Jan 2020", "end_date": "Dec 2021"}]}]})
    exp = fixed[1].resume.experience[0]
    assert (exp.start_date, exp.end_date) == ("Jan 2020", "Dec 2021")
    assert not changed
