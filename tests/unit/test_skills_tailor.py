"""Skills tailoring (P1.6): reorder by JD relevance, JD spelling, never add."""
from unittest.mock import MagicMock

import docx

from app.analysis.change_proposal import ChangeProposal
from app.analysis.keyword_match import KeywordMatcher
from app.analysis.skills_tailor import SkillsTailor, format_skills, parse_skills, unknown_skills
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Resume
from app.services.run_manager import RunManager
from app.services.tailor import TailorService
from app.validation.factual import FactualValidator

SKILLS = {
    "Tools": ["Excel", "Tableau", "Airflow"],
    "Languages": ["R", "Scala", "Python", "PySpark"],
    "Frameworks": ["Pandas", "Numpy", "XGBoost"],
}


def _report(skills=SKILLS):
    req = "Python, NumPy and XGBoost; Spark or Airflow"
    job = JobDescription(keywords=["Python", "NumPy", "XGBoost", "Spark", "Airflow"],
                         requirements=[Requirement(id="r1", text=req)], raw_text=req)
    return KeywordMatcher().match(job, Resume(candidate=Candidate(name="A"), skills=skills))


def test_jd_skills_first_and_jd_spelling_only_for_the_same_term():
    new = SkillsTailor().tailor(SKILLS, _report())
    # PySpark ranks as the JD's "Spark" but keeps its own name.
    assert new["Languages"] == ["Python", "PySpark", "R", "Scala"]
    assert new["Frameworks"][:2] == ["NumPy", "XGBoost"]  # "Numpy" respelled as the JD writes it
    assert new["Tools"][0] == "Airflow"


def test_category_with_most_jd_skills_moves_up():
    assert list(SkillsTailor().tailor(SKILLS, _report())) == ["Languages", "Frameworks", "Tools"]


def test_nothing_is_added_or_removed():
    new = SkillsTailor().tailor(SKILLS, _report())
    assert sorted(i.lower() for v in new.values() for i in v) == sorted(i.lower() for v in SKILLS.values() for i in v)


def test_format_and_parse_round_trip_keeps_parenthetical_lists():
    skills = {"Languages": ["Python (pandas, NumPy)", "SQL"]}
    assert parse_skills(format_skills(skills)) == skills


def test_validator_rejects_added_skills():
    original = format_skills(SKILLS)
    added = original + ", Kubernetes"
    prop = ChangeProposal(kind="skills", target_semantic_id="skills", original_text=original, proposed_text=added)
    result = FactualValidator().validate_proposal(prop, [])
    assert result.verdict == "REJECT" and "Kubernetes" in result.warnings[0]
    assert unknown_skills(SKILLS, SkillsTailor().tailor(SKILLS, _report())) == []


def test_no_proposal_when_order_already_fits():
    ordered = SkillsTailor().tailor(SKILLS, _report())
    resume = Resume(candidate=Candidate(name="A"), skills=ordered)
    assert SkillsTailor().propose(resume, _report(ordered)) is None


def _service(tmp_path):
    service = TailorService(llm_client=MagicMock(is_available=MagicMock(return_value=False)))
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    return service


def test_applied_in_template_mode_and_skipped_in_preserve(tmp_path):
    original = "Languages: Python, SQL, JavaScript, Bash\nFrameworks & Tools: FastAPI, Django, Docker, Kubernetes, AWS, PostgreSQL, Redis, Git"
    new_skills = "Frameworks & Tools: PostgreSQL, AWS, Docker, FastAPI, Django, Kubernetes, Redis, Git\nLanguages: Python, SQL, JavaScript, Bash"
    prop = ChangeProposal(kind="skills", target_semantic_id="skills", target_source_location_id="skills",
                          original_text=original, proposed_text=new_skills).model_dump()
    for mode in ("ATS_DEFAULT", "PRESERVE"):
        result = _service(tmp_path).tailor_resume(
            "tests/fixtures/resumes/sample.docx", "Requirements:\n- Python.", str(tmp_path / mode),
            mode=mode, preapproved_proposals=[dict(prop)])
        texts = [p.text for p in docx.Document(result["docx"]).paragraphs]
        if mode == "ATS_DEFAULT":
            assert "Frameworks & Tools: PostgreSQL, AWS, Docker, FastAPI, Django, Kubernetes, Redis, Git" in texts
        else:  # the original file is patched in place; skills keep their layout
            assert result["docx"] and not any(t.startswith("Frameworks & Tools: PostgreSQL") for t in texts)
