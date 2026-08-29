import pytest
from app.analysis.tailor_planner import TailoringPlanner
from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.report import Match
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.tailoring import TailoringPlan

def test_tailor_planner():
    resume = Resume(
        candidate=Candidate(name="Jane Doe"),
        experience=[
            Experience(
                id="exp_001",
                company="Acme",
                title="Engineer",
                bullets=[
                    ResumeBullet(id="exp_001_b01", text="Built API microservices in Python."),
                    ResumeBullet(id="exp_001_b02", text="Managed team meetings."),
                ],
            )
        ],
    )

    evidence_list = [
        Evidence(id="ev_001", source_type="experience", source_id="exp_001_b01", text="Built API microservices in Python."),
        Evidence(id="ev_002", source_type="experience", source_id="exp_001_b02", text="Managed team meetings."),
    ]

    jd = JobDescription(
        job_title="Python Engineer",
        requirements=[
            Requirement(id="req_001", text="Python", category="skill", priority="required"),
            Requirement(id="req_002", text="Kubernetes", category="skill", priority="required"),
        ],
        raw_text="Test",
    )

    matches = [
        Match(requirement_id="req_001", requirement_text="Python", status="EXPLICIT", evidence_ids=["ev_001"]),
        Match(requirement_id="req_002", requirement_text="Kubernetes", status="MISSING", evidence_ids=[]),
    ]

    planner = TailoringPlanner()
    plan = planner.create_plan(resume, jd, evidence_list, matches)

    assert isinstance(plan, TailoringPlan)
    assert len(plan.actions) == 2
    assert "Kubernetes" in plan.unsupported_requirements

    rewrite_actions = [a for a in plan.actions if a.action == "REWRITE"]
    assert len(rewrite_actions) == 1
    assert rewrite_actions[0].source_id == "exp_001_b01"
    assert "ev_001" in rewrite_actions[0].evidence_ids
