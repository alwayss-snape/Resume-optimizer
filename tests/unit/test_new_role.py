"""P3.3: add a job that isn't on the resume yet."""
from unittest.mock import MagicMock

import docx
import pytest

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


@pytest.mark.parametrize("role, desc, message", [
    ({"start_date": "", "end_date": "Dec 2020"}, "Did X.", "start date"),
    ({"start_date": "Jan 2019", "end_date": ""}, "Did X.", "end date"),
    ({"start_date": "Jan 2021", "end_date": "Dec 2020"}, "Did X.", "before its start"),
    ({"start_date": "Jan 2019", "current": True}, "  ", "at least one thing"),
])
def test_dates_and_description_required(tmp_path, role, desc, message):
    """Review finding: without these the new job reads back wrongly in an ATS."""
    with pytest.raises(ValueError, match=message):
        _service(tmp_path).add_new_role(_resume(), [], JobDescription(),
                                        {"company": "Globex", "title": "Engineer", **role}, desc)


def test_keywords_offered_to_the_polish_are_whole_words(tmp_path):
    service = _service(tmp_path)
    service.add_new_role(_resume(), [], JobDescription(keywords=["R", "Go", "Java", "SQL"]),
                         {"company": "Globex", "title": "Engineer", "start_date": "2019", "end_date": "2020"},
                         "Reduced go-to-market time with SQL and JavaScript.")
    assert service.rewriter.rewrite_bullet.call_args.kwargs["target_keywords"] == ["SQL"]


def test_every_ongoing_job_keeps_the_larger_minimum():
    from app.rendering.page_fit import _is_current
    older_ongoing = Experience(id="x", company="Side gig", title="Advisor",
                               roles=[Role(title="Advisor", start_date="2018", end_date="Ongoing")])
    ended = Experience(id="y", company="Old", title="Dev", roles=[Role(title="Dev", start_date="2015", end_date="2017")])
    assert _is_current(older_ongoing, 1) and not _is_current(ended, 2) and _is_current(ended, 0)


