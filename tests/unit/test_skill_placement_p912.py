"""P9.12: a confirmed skill goes under a category of its own type, a trait is
never a skill, and the JD's spelling is kept. The owner's run put "ci, version
control, unit tests, LLMs, Fast learner, deep curiosity about AI" under
"Frameworks"."""
import pytest

from app.analysis.gap_questions import GapAnswer, infer_kind
from app.analysis.skills_tailor import is_trait, jd_spelling, skill_category, skill_type
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Resume
from app.eval.harness import OfflineLLM
from app.services.tailor import TailorService

JD = ("Data Scientist\nRequirements:\n- Python, SQL and experience with CI, version control and unit tests\n"
      "- Hands-on work with LLMs\n- Fast learner with deep curiosity about AI")


def _resume():
    return Resume(candidate=Candidate(name="A"), skills={
        "Languages": ["Python", "SQL", "PySpark", "R", "SAS"],
        "Frameworks": ["Pandas", "Numpy", "Scikit-Learn", "LightGBM", "XGBoost"],
        "Tools": ["MySQL", "SSMS", "Tableau", "Databricks", "Azure", "AWS Redshift", "Excel", "PowerPoint"]})


def _job():
    lines = [l.lstrip("- ") for l in JD.splitlines()[2:]]
    return JobDescription(raw_text=JD, requirements=[Requirement(id=f"r{i}", text=t) for i, t in enumerate(lines)],
                          keywords=["ci", "version control", "unit tests", "LLMs", "Fast learner",
                                    "deep curiosity about AI"])


def test_the_owners_case_lands_in_the_right_places():
    resume = _resume()
    notes = TailorService(llm_client=OfflineLLM(), keep_run=False)._apply_gap_answers(resume, [], _job(), [GapAnswer(
        confirmed_keywords=["ci", "version control", "unit tests", "LLMs", "Fast learner", "deep curiosity about AI"])])
    assert resume.skills["Frameworks"] == ["Pandas", "Numpy", "Scikit-Learn", "LightGBM", "XGBoost"]  # untouched
    assert resume.skills["Practices"] == ["CI", "version control", "unit tests"]  # the JD's spelling: "CI"
    assert resume.skills["Expertise"] == ["LLMs"]
    listed = " ".join(i for items in resume.skills.values() for i in items).lower()
    assert "learner" not in listed and "curiosity" not in listed
    assert any("Not listed under Skills: Fast learner, deep curiosity about AI" in n for n in notes)


@pytest.mark.parametrize("term, kind", [
    ("Python", "language"), ("PyTorch", "framework"), ("Snowflake", "tool"), ("CI/CD", "practice"),
    ("unit tests", "practice"), ("LLMs", "expertise"), ("NLP", "expertise"), ("Quantum widgets", None)])
def test_skill_types(term, kind):
    assert skill_type(term) == kind


def test_a_skill_never_goes_into_a_category_of_another_type():
    skills = {"Languages": ["Python"], "Cloud & Tools": ["AWS"]}
    assert skill_category(skills, "Rust") == "Languages"
    assert skill_category(skills, "Docker") == "Cloud & Tools"
    assert skill_category(skills, "pytest") == "Frameworks & Libraries"  # new, named for its type
    assert skill_category(skills, "Quantum widgets") == "Other skills"  # unknown: never guessed into a typed one
    assert skill_category({"Skills": ["Excel"]}, "Quantum widgets") == "Skills"


@pytest.mark.parametrize("keyword", ["Fast learner", "deep curiosity about AI", "Self-starter", "team player",
                                     "detail-oriented", "growth mindset", "passionate about data"])
def test_traits_are_never_skills(keyword):
    assert is_trait(keyword) and infer_kind(keyword, "hard") == "soft"


@pytest.mark.parametrize("keyword", ["machine learning", "growth marketing", "data-driven decision making",
                                     "Adobe Creative Cloud", "CI/CD", "learning management systems"])
def test_skills_that_look_like_traits_are_not(keyword):
    assert not is_trait(keyword)


def test_jd_spelling():
    assert jd_spelling("ci", JD) == "CI"
    assert jd_spelling("llms", JD) == "LLMs"
    assert jd_spelling("Kafka", JD) == "Kafka"  # not in the JD: as given
