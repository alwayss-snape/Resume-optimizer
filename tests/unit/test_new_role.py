"""P3.3: add a job that isn't on the resume yet."""
import os
import shutil
from datetime import date
from unittest.mock import MagicMock, patch

import docx
import pytest
from streamlit.testing.v1 import AppTest

from app.domain.job import JobDescription
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet, Role
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.services.run_manager import RunManager
from app.services.tailor import TailorService


def _service(tmp_path, polish=None):
    service = TailorService()
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    service.rewriter.rewrite_bullet = MagicMock(side_effect=polish or (lambda text, **kw: (text, "")))
    return service


def _resume():
    return Resume(candidate=Candidate(name="A"), experience=[
        Experience(id="e1", company="Acme", title="Engineer",
                   roles=[Role(title="Engineer", start_date="Jan 2023", end_date="Present")],
                   bullets=[ResumeBullet(id="b1", text="Built things.")]),
        Experience(id="e2", company="Initech", title="Analyst",
                   roles=[Role(title="Analyst", start_date="Jan 2016", end_date="Dec 2018")]),
    ])


def test_split_description():
    split = TailorService._split_description
    assert split("- Built X.\n• Cut Y by 20%.\n\n3) Led Z") == ["Built X.", "Cut Y by 20%.", "Led Z"]
    assert split("Built the API. Migrated it to AWS. Cut costs 10%.") == [
        "Built the API.", "Migrated it to AWS.", "Cut costs 10%."]
    assert split("") == []


def test_new_role_goes_in_date_order_with_bullets(tmp_path):
    resume = _resume()
    job = JobDescription(keywords=["Python", "Kafka"])
    _, evidence, notes = _service(tmp_path).add_new_role(
        resume, [], job, {"company": "Globex", "title": "Data Engineer", "location": "Pune, India",
                          "start_date": "Feb 2019", "end_date": "Dec 2022"},
        "Built Python ingestion jobs.\nRan the Kafka cluster.")
    assert [e.company for e in resume.experience] == ["Acme", "Globex", "Initech"]
    new = resume.experience[1]
    assert (new.title, new.start_date, new.end_date, new.location) == ("Data Engineer", "Feb 2019", "Dec 2022", "Pune, India")
    assert [b.text for b in new.bullets] == ["Built Python ingestion jobs.", "Ran the Kafka cluster."]
    assert {e.source_id for e in evidence} == {b.id for b in new.bullets}
    assert "Data Engineer at Globex" in notes[0]


def test_current_role_goes_first(tmp_path):
    resume = _resume()
    _service(tmp_path).add_new_role(resume, [], JobDescription(),
                                    {"company": "Newco", "title": "Lead", "start_date": "Jan 2021", "current": True},
                                    "Led the team.")
    # Both ongoing: the more recent start (Acme, 2023) stays first.
    assert [e.company for e in resume.experience] == ["Acme", "Newco", "Initech"]
    assert resume.experience[1].end_date == "Present"


def test_polish_that_adds_facts_is_refused(tmp_path):
    service = _service(tmp_path, polish=lambda text, **kw: ("Architected Kafka pipelines serving 5M users.", ""))
    resume = _resume()
    service.add_new_role(resume, [], JobDescription(keywords=["Kafka"]),
                         {"company": "Globex", "title": "Engineer", "start_date": "2019", "end_date": "2020"},
                         "Built data pipelines.")
    new = next(e for e in resume.experience if e.company == "Globex")
    assert new.bullets[0].text == "Built data pipelines."  # the user's words, not the embellishment


def test_company_and_title_required(tmp_path):
    with pytest.raises(ValueError):
        _service(tmp_path).add_new_role(_resume(), [], JobDescription(), {"company": "", "title": "X"}, "Did Y.")


def test_user_added_bullets_are_never_trimmed_first():
    resume = _resume()
    resume.experience[0].bullets.append(ResumeBullet(id="user_b", text="Added by the user."))
    plan = TailoringPlan(actions=[TailoringAction(action="KEEP", source_id="b1", relevance=0.2)])
    relevance = TailorService._fit_relevance(resume, plan)
    assert relevance == {"b1": 0.2, "user_b": 1.0}


def test_tailor_renders_new_role_even_in_preserve_mode(tmp_path):
    service = _service(tmp_path)
    result = service.tailor_resume(
        "tests/fixtures/resumes/sample.docx", "Requirements:\n- Python.", str(tmp_path / "out"), mode="PRESERVE",
        new_role={"company": "Globex Labs", "title": "Platform Engineer", "start_date": "Jan 2012",
                  "end_date": "Dec 2013", "description": "Kept the build farm running."})
    texts = [p.text for p in docx.Document(result["docx"]).paragraphs]
    assert any(t.startswith("Platform Engineer\t") for t in texts)
    assert "Kept the build farm running." in texts
    assert any("Added a new job" in w for w in result["warnings"])


def _app(tmp_path):
    resume_copy = tmp_path / "upload.docx"
    shutil.copy("tests/fixtures/resumes/sample.docx", resume_copy)
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    for key, value in {"stage": "proposals", "proposals": [], "gap_questions": [], "experience_options": [],
                       "resume_path": str(resume_copy), "jd_text": "x", "model_choice": "m",
                       "render_mode": "ATS_DEFAULT", "strict_factual": False, "pre_score": 10.0}.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    return at


def test_ui_sends_new_role(tmp_path):
    at = _app(tmp_path)
    at.text_input(key="nr_company").input("Globex")
    at.text_input(key="nr_title").input("Data Engineer")
    at.checkbox(key="nr_current").check()
    at.date_input(key="nr_start").set_value(date(2021, 3, 1))
    at.text_area(key="nr_desc").input("Built pipelines.")
    with patch.object(TailorService, "tailor_resume", return_value={"success": True}) as tailor:
        next(b for b in at.button if b.label == "Apply & Generate").click().run()
    role = tailor.call_args.kwargs["new_role"]
    assert role == {"company": "Globex", "title": "Data Engineer", "location": "", "current": True,
                    "description": "Built pipelines.", "start_date": "Mar 2021", "end_date": ""}


def test_ui_requires_company_and_title(tmp_path):
    at = _app(tmp_path)
    at.text_area(key="nr_desc").input("Built pipelines.")
    with patch.object(TailorService, "tailor_resume") as tailor:
        next(b for b in at.button if b.label == "Apply & Generate").click().run()
    assert not tailor.called
    assert any("company and the job title" in e.value for e in at.error)
