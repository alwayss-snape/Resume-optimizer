import pytest
from app.analysis.rewriter import LLMRewriter, RewriteProposal
from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.tailoring import TailoringAction, TailoringPlan

def test_rewriter_deterministic_fallback():
    rewriter = LLMRewriter(llm_client=None)

    resume = Resume(
        candidate=Candidate(name="Jane Doe"),
        experience=[
            Experience(
                id="exp_001",
                company="Acme",
                title="Engineer",
                bullets=[
                    ResumeBullet(id="exp_001_b01", text="Built API microservices in Python processing 50M requests."),
                ],
            )
        ],
    )

    evidence_list = [
        Evidence(id="ev_001", source_type="experience", source_id="exp_001_b01", text="Built API microservices in Python processing 50M requests."),
    ]

    jd = JobDescription(
        job_title="Python Engineer",
        requirements=[Requirement(id="req_001", text="Python API", category="skill")],
        raw_text="Test JD",
    )

    plan = TailoringPlan(
        actions=[
            TailoringAction(
                action="REWRITE",
                source_id="exp_001_b01",
                evidence_ids=["ev_001"],
                rationale="Align with API requirement",
            )
        ]
    )

    proposals = rewriter.execute_plan(resume, plan, evidence_list, jd)
    assert len(proposals) == 1
    prop = proposals[0]
    assert isinstance(prop, RewriteProposal)
    assert prop.source_id == "exp_001_b01"
    # Fallback preserves original text when LLM unavailable
    assert prop.rewritten_text == prop.original_text
