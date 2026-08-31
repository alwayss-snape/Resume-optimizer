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


def test_semantic_only_match_produces_rewrite_with_labeled_rationale():
    """A bullet whose only match is SEMANTIC_PARTIAL (an inferred, not exact,
    match) should still be selected for REWRITE — but the rationale must
    plainly say it's inferred via semantic similarity, not present it as an
    exact requirement match."""
    resume = Resume(
        candidate=Candidate(name="Jane Doe"),
        experience=[
            Experience(
                id="exp_001",
                company="Acme",
                title="Engineer",
                bullets=[
                    ResumeBullet(id="exp_001_b01", text="Worked closely with product and design teams."),
                ],
            )
        ],
    )

    evidence_list = [
        Evidence(id="ev_001", source_type="experience", source_id="exp_001_b01",
                 text="Worked closely with product and design teams."),
    ]

    jd = JobDescription(
        job_title="Engineer",
        requirements=[
            Requirement(id="req_001", text="Collaborate with cross-functional stakeholders",
                        category="responsibility", priority="required"),
        ],
        raw_text="Test",
    )

    matches = [
        Match(requirement_id="req_001", requirement_text="Collaborate with cross-functional stakeholders",
              status="SEMANTIC_PARTIAL", evidence_ids=["ev_001"], confidence=0.65,
              explanation="Semantically similar to resume evidence ev_001 (similarity 0.65)."),
    ]

    planner = TailoringPlanner()
    plan = planner.create_plan(resume, jd, evidence_list, matches)

    rewrite_actions = [a for a in plan.actions if a.action == "REWRITE"]
    assert len(rewrite_actions) == 1
    assert "inferred via semantic similarity" in rewrite_actions[0].rationale
    assert "Collaborate with cross-functional stakeholders" in rewrite_actions[0].rationale


def test_deterministic_match_preferred_over_semantic_for_rationale():
    """If a bullet has BOTH a deterministic match and a semantic match (to
    different requirements), the rationale should cite the deterministic one
    — it's the stronger, non-inferred signal."""
    resume = Resume(
        candidate=Candidate(name="Jane Doe"),
        experience=[
            Experience(
                id="exp_001",
                company="Acme",
                title="Engineer",
                bullets=[
                    ResumeBullet(id="exp_001_b01", text="Built Python microservices."),
                ],
            )
        ],
    )

    evidence_list = [
        Evidence(id="ev_001", source_type="experience", source_id="exp_001_b01", text="Built Python microservices."),
    ]

    jd = JobDescription(
        job_title="Engineer",
        requirements=[
            Requirement(id="req_001", text="Python", category="skill", priority="required"),
            Requirement(id="req_002", text="Collaborate with cross-functional stakeholders",
                        category="responsibility", priority="required"),
        ],
        raw_text="Test",
    )

    matches = [
        Match(requirement_id="req_001", requirement_text="Python", status="EXPLICIT", evidence_ids=["ev_001"]),
        Match(requirement_id="req_002", requirement_text="Collaborate with cross-functional stakeholders",
              status="SEMANTIC_PARTIAL", evidence_ids=["ev_001"], confidence=0.6),
    ]

    planner = TailoringPlanner()
    plan = planner.create_plan(resume, jd, evidence_list, matches)

    rewrite_actions = [a for a in plan.actions if a.action == "REWRITE"]
    assert len(rewrite_actions) == 1
    assert "inferred via semantic similarity" not in rewrite_actions[0].rationale
    assert "Python" in rewrite_actions[0].rationale
