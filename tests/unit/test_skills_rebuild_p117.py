"""P11.7: the Skills section rebuilt from the candidate's evidence."""
from app.analysis.rewriter import RewriteProposal
from app.analysis.skills_tailor import rebuild_skills
from app.domain.evidence import Evidence
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.llm.schemas import SkillsRebuildResult
from app.validation.factual import FactualValidator

RESUME = Resume(candidate=Candidate(name="A B"), skills={"Tools": ["MySQL", "PowerPoint"], "Languages": ["Python"]},
                experience=[Experience(id="e1", company="Acme", title="DS", bullets=[
                    ResumeBullet(id="b1", text="Engineered features from transaction rows in PySpark on BigQuery"),
                    ResumeBullet(id="b2", text="Measured lift with difference-in-differences t-tests")])])
EVIDENCE = [Evidence(id="n1", source_type="general", source_id="e1::X", text="Tech: LightGBM, MLflow")]


class _SkillsLLM:
    def is_available(self):
        return True

    def generate_json(self, messages, schema_model, **kwargs):
        assert schema_model is SkillsRebuildResult and "Tech: LightGBM, MLflow" in messages[-1]["content"]
        return SkillsRebuildResult(groups=[
            {"category": "Statistics & Experimentation", "items": ["Difference-in-differences", "Causal Forests"]},
            {"category": "Machine Learning", "items": ["LightGBM", "MLflow"]},
            {"category": "Data & Platforms", "items": ["PySpark", "BigQuery", "MySQL", "Python"]}],
            dropped=["PowerPoint", "Excel"])


def test_skills_come_only_from_the_candidates_material():
    p = rebuild_skills(RESUME, EVIDENCE, None, _SkillsLLM())
    assert "Causal Forests" not in p.proposed_text  # named nowhere in the material
    assert p.proposed_text.splitlines()[0] == "Statistics & Experimentation: Difference-in-differences"
    assert "added from your work: Difference-in-differences, LightGBM, MLflow, PySpark, BigQuery" in p.rationale
    assert "left out: PowerPoint" in p.rationale and "Excel" not in p.rationale  # only items it had


def test_the_check_allows_evidenced_skills_and_rejects_others():
    v = FactualValidator()
    ev = EVIDENCE + [Evidence(id="x1", source_type="experience", source_id="b1", text=RESUME.experience[0].bullets[0].text)]
    ok = RewriteProposal(kind="skills", original_text="Tools: MySQL", proposed_text="Data: MySQL, BigQuery, LightGBM")
    assert v.validate_proposal(ok, ev).verdict == "PASS"
    bad = RewriteProposal(kind="skills", original_text="Tools: MySQL", proposed_text="Data: MySQL, Snowflake")
    assert v.validate_proposal(bad, ev).verdict == "REJECT"
