"""P11.6: headline and summary aimed at the job, from evidence."""
from unittest.mock import MagicMock

from app.analysis.summary_writer import SummaryWriter
from app.domain.resume import Candidate, Experience, Resume, Role
from app.services.tailor import TailorService


def _resume(summary="Data Scientist with 3.6 years of experience in insurance."):
    return Resume(candidate=Candidate(name="A B"), summary=summary, experience=[Experience(
        id="e1", company="Acme", title="Data Scientist II", start_date="August 2022", end_date="Present",
        roles=[Role(title="Data Scientist II", start_date="August 2024", end_date="Present"),
               Role(title="Data Scientist I", start_date="August 2022", end_date="August 2024")])])


def test_the_jobs_title_as_far_as_the_candidates_titles_support_it():
    r = _resume()
    assert SummaryWriter.evidenced_title("Senior Data Scientist, Data & AI, Example Hotels", r) == "Data Scientist"
    assert SummaryWriter.evidenced_title("Data Scientist II", r) == "Data Scientist II"
    assert SummaryWriter.evidenced_title("Machine Learning Engineer", r) == ""


def test_a_years_claim_the_dated_roles_have_outgrown_is_stale():
    from datetime import date
    from app.analysis.experience import years_of_experience
    r = _resume()
    computed = years_of_experience(r, date(2026, 10, 9))
    assert SummaryWriter.years_claim(r, computed) == "3.6 years"  # the resume's own figure stands (P9.9)
    r.experience[0].id = "exp_user_abc123"  # ... until this run adds a job: then the dates win
    assert computed >= 4 and SummaryWriter.years_claim(r, computed) is None
    assert SummaryWriter.years_claim(_resume("Data Scientist with 4+ years of experience."), computed) == "4+ years"


def test_the_confirmed_headline_goes_under_the_name(tmp_path):
    service = TailorService(llm_client=None)
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    resume_path = "tests/fixtures/resumes/replica_layout.pdf"
    parsed = service.parse_resume(resume_path)
    result = service.tailor_resume(resume_path, "Senior Data Scientist. Forecasting.", str(tmp_path), parsed=parsed,
                                   preapproved_proposals=[], remember_answers=False,
                                   brief_edits={"title": "Data Scientist", "positioning": ""})
    assert result["arrange"]["full_doc"].resume.candidate.headline == "Data Scientist"
    assert result["coverage"]["lost"] == []
