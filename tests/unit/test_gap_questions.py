"""Suggest-and-confirm gaps (P3.1)."""
from unittest.mock import MagicMock

from app.analysis.gap_questions import GapAnswer, build_questions
from app.analysis.keyword_match import KeywordMatcher
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.services.run_manager import RunManager
from app.services.tailor import TailorService


def _resume():
    return Resume(candidate=Candidate(name="A"), skills={"Tools": ["Excel"], "Languages": ["Python"]},
                  experience=[Experience(id="e1", company="Acme", title="Analyst",
                                         bullets=[ResumeBullet(id="b1", text="Built Python reports.")])])


def _job():
    reqs = [
        Requirement(id="r1", text="Proficient in Python and PyTorch or TensorFlow", priority="required"),
        Requirement(id="r2", text="Experience with Kafka streaming is a plus", priority="preferred"),
        Requirement(id="r3", text="Strong SQL skills", priority="required"),
    ]
    return JobDescription(keywords=["Python", "PyTorch", "TensorFlow", "Kafka", "SQL"], requirements=reqs,
                          raw_text="\n".join(r.text for r in reqs))


def test_questions_group_missing_keywords_by_jd_line_required_first():
    questions = build_questions(_job(), KeywordMatcher().match(_job(), _resume()))
    assert [q.keywords for q in questions] == [["PyTorch", "TensorFlow"], ["SQL"], ["Kafka"]]
    assert questions[0].requirement == "Proficient in Python and PyTorch or TensorFlow"
    assert "PyTorch or TensorFlow" in questions[0].question
    assert questions[-1].priority == "preferred"
    assert build_questions(_job(), KeywordMatcher().match(_job(), _resume()), limit=1)[0].id == "gap_1"


def _service(tmp_path, llm=None):
    from app.eval.harness import OfflineLLM
    service = TailorService(llm_client=llm or OfflineLLM())
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    return service


def test_only_ticked_keywords_are_added_to_skills(tmp_path):
    service, resume, evidence = _service(tmp_path), _resume(), []
    notes = service._apply_gap_answers(resume, evidence, _job(), [
        GapAnswer(question_id="gap_1", confirmed_keywords=["PyTorch"]),
        {"question_id": "gap_2", "confirmed_keywords": [], "answer": ""},
    ])
    # A framework goes under a category of its own type, not "Tools" (P9.12).
    assert resume.skills["Frameworks & Libraries"] == ["PyTorch"] and resume.skills["Tools"] == ["Excel"]
    assert "TensorFlow" not in str(resume.skills)
    assert any(e.text == "PyTorch" and e.source_id == "user_confirmed" for e in evidence)
    assert "You confirmed: PyTorch (added to Frameworks & Libraries)" in notes  # plus a nudge to say where (P8.12)


def test_answer_becomes_a_bullet_and_an_embellished_polish_is_refused(tmp_path):
    service = _service(tmp_path)
    service.rewriter.rewrite_bullet = MagicMock(
        return_value=("Trained PyTorch image models on Kubernetes for 2M users.", "r"))
    resume, evidence = _resume(), []
    service._apply_gap_answers(resume, evidence, _job(), [GapAnswer(
        confirmed_keywords=["PyTorch"], answer="Trained PyTorch image models in a course project.", target="e1")])
    # The polish invented "Kubernetes" and "2M users", so the answer is used as written.
    assert resume.experience[0].bullets[-1].text == "Trained PyTorch image models in a course project."
    kwargs = service.rewriter.rewrite_bullet.call_args.kwargs
    assert kwargs["target_keywords"] == ["PyTorch"] and kwargs["jd_requirements"] == []


def test_faithful_polish_is_used(tmp_path):
    service = _service(tmp_path)
    service.rewriter.rewrite_bullet = MagicMock(return_value=("Trained PyTorch image models in a course project", "r"))
    resume = _resume()
    service._apply_gap_answers(resume, [], _job(), [GapAnswer(answer="trained pytorch image models in a course project")])
    assert resume.experience[0].bullets[-1].text == "Trained PyTorch image models in a course project"


def test_generate_proposals_asks_instead_of_suggesting(tmp_path):
    out = _service(tmp_path).generate_proposals("tests/fixtures/resumes/sample.docx",
                                                open("tests/fixtures/jds/sample.txt").read())
    assert "missing_suggestions" not in out
    assert out["gap_questions"] and all(q.keywords for q in out["gap_questions"])




def test_questions_are_worded_by_kind_and_skip_what_the_resume_shows():
    """P8.12: no "Have you worked with Bachelor's degree?", nothing already on the resume."""
    from app.analysis.gap_questions import _wording, partly_shown
    from app.analysis.keyword_match import tokens
    resume = tokens("Salesforce and Outreach; OSHA 30; Compact NLC licence; English and Spanish")
    assert partly_shown("Salesforce CRM", resume)
    assert partly_shown("OSHA 10 or 30", resume)
    assert partly_shown("Compact/NLC", resume)
    assert partly_shown("English/Spanish", resume)
    assert not partly_shown("Gong", resume) and not partly_shown("Project management", tokens("Built dashboards"))
    assert partly_shown("Bachelor's degree", [], education_text="Master of Accountancy (MAcc), Baruch College",
                        kind="education")
    assert not partly_shown("Bachelor's degree", [], education_text="High School Diploma", kind="education")
    assert not partly_shown("Bachelor's degree", tokens("Boston, MA"), education_text="")  # MA the state
    assert _wording({"certification"}, "ACLS")[1] == "Tick the ones you hold:"
    assert _wording({"education"}, "a Bachelor's degree")[0].endswith("Do you have it?")
    assert "real example" in _wording({"soft"}, "stakeholder management")[1]


def test_a_ticked_licence_goes_to_certifications(tmp_path):
    from app.analysis.gap_questions import GapAnswer
    from app.domain.job import JobDescription, Requirement
    from app.domain.resume import Candidate, Resume
    service = TailorService(llm_client=None)
    job = JobDescription(raw_text="CCRN certification preferred", keywords=["CCRN"], certifications=["CCRN"],
                         requirements=[Requirement(id="r1", text="CCRN certification preferred")])
    resume = Resume(candidate=Candidate(name="M"), skills={"Skills": ["Epic"]})
    notes = service._apply_gap_answers(resume, [], job, [GapAnswer(confirmed_keywords=["CCRN"])])
    assert resume.certifications == [{"name": "CCRN"}] and resume.skills == {"Skills": ["Epic"]}
    assert not any("where you used it" in n for n in notes)  # a licence is held, not used somewhere


def test_stage_i_review_partly_shown_and_kinds():
    from app.analysis.gap_questions import infer_kind, partly_shown
    from app.analysis.keyword_match import tokens
    r = tokens("Projects; Spring 2019; power distribution; customer discovery; Google Cloud; Adobe Illustrator; "
               "business days; Microsoft Office; tagout")
    for kw in ("Project management", "Spring Boot", "Power BI", "Customer service", "Google Analytics",
               "Adobe Photoshop", "Business development", "Microsoft Azure", "lockout/tagout"):
        assert not partly_shown(kw, r), kw
    assert not partly_shown("MS SQL Server", [], education_text="MBA, Kellogg", kind="hard")
    assert partly_shown("Bachelor's degree", [], education_text="M.S., Computer Science", kind="education")
    assert not partly_shown("Bachelor's degree", [], education_text="to be completed", kind="education")
    assert infer_kind("CCRN", "hard", "BLS and ACLS certification required; CCRN preferred") == "certification"
    assert infer_kind("ICU", "hard", "1 year ICU preferred") == "hard"
    assert infer_kind("High school diploma or GED", "hard") == "education"
