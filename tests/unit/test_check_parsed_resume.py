"""P3.5: "Check parsed resume" step: corrections applied by the service,
and the Streamlit stage wired end to end (with the rewrite step mocked)."""
import os
import shutil
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.services.tailor import TailorService

REPLICA = "tests/fixtures/resumes/replica_layout.pdf"
UI_SCRIPT = os.path.abspath("app/ui.py")


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


def test_ui_check_parse_stage_end_to_end(tmp_path):
    # The UI deletes the uploaded temp file on "Start Over", so hand it a copy.
    resume_copy = tmp_path / "upload.pdf"
    shutil.copy(REPLICA, resume_copy)
    parsed = _service().parse_resume(str(resume_copy))
    at = AppTest.from_file(UI_SCRIPT, default_timeout=60)
    at.session_state["stage"] = "check_parse"
    at.session_state["parsed"] = parsed
    at.session_state["parse_issues"] = []
    at.session_state["resume_path"] = str(resume_copy)
    at.session_state["jd_text"] = "Requirements:\n- Python."
    at.session_state["model_choice"] = "openai/gpt-oss-120b"
    at.run()
    assert not at.exception
    assert at.text_input[0].value == "Jordan Avery"
    companies = [t.value for t in at.text_input if t.label == "Company"]
    assert companies == ["Northwind Analytics - A Contoso Group Company", "Blue Harbor Bank"]
    titles = [t.value for t in at.text_input if t.label in ("Title", "Earlier title")]
    assert titles == ["Senior Data Scientist", "Data Scientist", "Analytics Intern"]

    at.text_input[1].set_value("Senior Data Scientist")  # headline
    fake = {"proposals": [], "gap_questions": [], "llm_available": True, "llm_status": {},
            "llm_usage": None, "alignment_score": 50.0, "experience_options": []}
    with patch.object(TailorService, "generate_proposals", return_value=fake) as gen:
        confirm = next(b for b in at.button if b.label.startswith("✅ Looks right"))
        confirm.click().run()
    assert not at.exception
    assert at.session_state["stage"] == "proposals"
    assert at.session_state["parse_corrected"] is True
    sent = gen.call_args.kwargs["parsed"]
    assert sent[1].resume.candidate.headline == "Senior Data Scientist"
