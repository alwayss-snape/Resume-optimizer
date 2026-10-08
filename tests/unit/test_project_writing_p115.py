"""P11.5: projects written whole, from all their material, and fact-checked."""
from unittest.mock import MagicMock

from app.analysis.rewriter import LLMRewriter, RewriteProposal
from app.domain.evidence import Evidence
from app.domain.job import JobDescription
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.tailoring import TailoringAction, TailoringPlan
from app.llm.schemas import ProjectWriteResult
from app.services.tailor import TailorService
from app.validation.factual import FactualValidator


def _resume():
    bullets = [ResumeBullet(id="b1", text="Built a scoring service for 6 offer types using gradient-boosted "
                                         "propensity models and business rules", group="CDX Offer Scoring"),
               ResumeBullet(id="b2", text="Engineered 140 features from 2.3B transaction rows in PySpark",
                            group="CDX Offer Scoring"),
               ResumeBullet(id="b3", text="Wrote the onboarding guide", group=None)]
    return Resume(candidate=Candidate(name="A B"), experience=[
        Experience(id="e1", company="Acme", title="ML Engineer", start_date="Mar 2026", end_date="Present",
                   bullets=bullets)])


EVIDENCE = [Evidence(id="ev1", source_type="experience", source_id="b1", text="Acme: Built a scoring service "
                     "for 6 offer types using gradient-boosted propensity models and business rules"),
            Evidence(id="ev2", source_type="experience", source_id="b2",
                     text="Acme: Engineered 140 features from 2.3B transaction rows in PySpark"),
            Evidence(id="ev3", source_type="experience", source_id="b3", text="Acme: Wrote the onboarding guide"),
            Evidence(id="ev4", source_type="general", source_id="e1::CDX Offer Scoring",
                     text="Overview: scores 12M users and picks each user's best offer")]


class _WriterLLM:
    provider, model, last_error, on_wait = "fake", "fake", None, None

    def __init__(self, bullets):
        self.bullets, self.calls = bullets, []

    def is_available(self):
        return True

    def generate_json(self, messages, schema_model, **kwargs):
        self.calls.append(schema_model.__name__)
        if schema_model is ProjectWriteResult:
            assert "note: Overview: scores 12M users" in messages[-1]["content"]  # notes reach the writer
            return ProjectWriteResult(projects=[{"project": 0, "heading": "Offer Scoring Service",
                                                 "bullets": self.bullets}])
        from app.llm.schemas import RoleRewriteResult
        return RoleRewriteResult(bullets=[])


def _plan(resume):
    return TailoringPlan(actions=[TailoringAction(action="REWRITE", source_id=b.id, evidence_ids=[f"ev{b.id[1]}"])
                                  for b in resume.experience[0].bullets])


GOOD = ["Built a scoring service that scores 12M users on 6 offer types and picks each user's best offer.",
        "Engineered 140 features from 2.3B transaction rows in PySpark for gradient-boosted propensity models."]


def test_a_project_is_written_whole_and_its_loose_bullets_go_bullet_by_bullet():
    resume = _resume()
    llm = _WriterLLM(["Deploy a scoring pipeline", *GOOD[1:]])
    proposals = LLMRewriter(llm).execute_plan(resume, _plan(resume), EVIDENCE, JobDescription(raw_text="x"))
    project = next(p for p in proposals if p.kind == "project")
    assert project.target_semantic_id == "e1::CDX Offer Scoring"
    assert project.proposed_text.splitlines()[0] == "Deploy a scoring pipeline"  # no past form in the originals to restore
    assert set(project.evidence_ids) == {"ev1", "ev2", "ev4"}
    heading = next(p for p in proposals if p.kind == "heading")
    assert heading.proposed_text == "Offer Scoring Service"
    assert not any(p.kind == "bullet" and p.target_semantic_id in ("b1", "b2") for p in proposals)
    assert any(p.kind == "bullet" and p.target_semantic_id == "b3" for p in proposals)  # the loose one
    assert llm.calls[0] == "ProjectWriteResult"


def _project(text):
    return RewriteProposal(kind="project", target_semantic_id="e1::CDX Offer Scoring", proposed_text=text,
                           original_text="\n".join(b.text for b in _resume().experience[0].bullets[:2]),
                           evidence_ids=["ev1", "ev2", "ev4"])


def test_the_project_check_takes_facts_from_the_notes_and_rejects_new_ones():
    v = FactualValidator()
    assert v.validate_proposal(_project("\n".join(GOOD)), EVIDENCE).verdict in ("PASS", "NEEDS_CONFIRM")
    made_up = v.validate_proposal(_project("Built a system scoring 40M users with XGBoost models."), EVIDENCE)
    assert made_up.verdict == "REJECT"
    lost = v.validate_proposal(_project("Built a scoring service on 6 offer types with gradient-boosted propensity models."),
                               EVIDENCE)
    assert any("leaves out 140, 2.3B" in w for w in lost.warnings)


def test_an_accepted_project_replaces_its_bullets_and_nothing_counts_as_lost(tmp_path):
    service = TailorService(llm_client=None)
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    from app.domain.resume_document import ResumeDocument
    resume = _resume()
    doc = ResumeDocument(resume=resume)
    evidence = list(EVIDENCE)
    done = service._apply_projects(resume, doc, [_project("\n".join(GOOD))], evidence)
    texts = [(b.text, b.group) for b in resume.experience[0].bullets]
    assert done == 1 and texts[:2] == [(GOOD[0], "CDX Offer Scoring"), (GOOD[1], "CDX Offer Scoring")]
    assert texts[2] == ("Wrote the onboarding guide", None)
    assert sum(e.text.endswith(GOOD[0]) for e in evidence) == 1
