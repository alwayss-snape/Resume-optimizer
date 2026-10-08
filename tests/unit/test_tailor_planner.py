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


# -- Planner v2 (P1.3) ---------------------------------------------------

def _v2_resume():
    return Resume(
        candidate=Candidate(name="Jane Doe"),
        experience=[Experience(id="exp_001", company="Acme", title="Data Scientist", bullets=[
            ResumeBullet(id="b1", text="Organised the team offsite.", group="Platform"),
            ResumeBullet(id="b2", text="Built a PySpark feature pipeline for churn models.", group="Platform"),
            ResumeBullet(id="b3", text="Trained LightGBM ranking models in Python.", group="Ranking"),
        ])],
    )


def _v2_job():
    reqs = [
        Requirement(id="r1", text="Build ranking models with LightGBM or PyTorch", priority="required"),
        Requirement(id="r2", text="Experience with Spark feature pipelines", priority="required"),
        Requirement(id="r3", text="Kubernetes deployments", priority="required"),
    ]
    return JobDescription(job_title="ML Engineer", requirements=reqs, keywords=["LightGBM", "PyTorch", "Spark", "Python"],
                          raw_text="\n".join(r.text for r in reqs))


def _v2_plan(embedder=None):
    resume = _v2_resume()
    evidence = [Evidence(id=f"ev_{b.id}", source_type="experience", source_id=b.id, text=b.text)
                for b in resume.experience[0].bullets]
    return TailoringPlanner(embedder=embedder).create_plan(resume, _v2_job(), evidence, matches=[])


def test_v2_rewrites_relevant_bullets_without_requirement_matches():
    actions = {a.source_id: a for a in _v2_plan().actions}
    assert actions["b2"].action == actions["b3"].action == "REWRITE"
    assert actions["b1"].action == "KEEP" and actions["b1"].trim_candidate
    assert actions["b3"].relevance > actions["b2"].relevance > actions["b1"].relevance


def test_v2_rewriter_inputs_are_scoped_to_the_bullet():
    actions = {a.source_id: a for a in _v2_plan().actions}
    # Only keywords the bullet already contains (PySpark implies Spark);
    # PyTorch stays out of the LightGBM bullet.
    assert actions["b2"].keywords == ["Spark"]
    assert set(actions["b3"].keywords) == {"LightGBM", "Python"}
    assert actions["b3"].requirement_ids[0] == "r1"
    assert "r3" not in actions["b3"].requirement_ids  # no overlap at all with Kubernetes


def test_v2_orders_bullets_within_sub_headings():
    plan = _v2_plan()
    # b2 outranks b1 inside "Platform", but b1 opens the project (what it is)
    # and stays first (P11.8); the "Ranking" group stays after it.
    assert plan.bullet_order["exp_001"] == ["b1", "b2", "b3"]


def test_v2_uses_embeddings_when_given_and_falls_back_on_error():
    def fake_embed(texts):
        # 1-D "embedding": similar iff both mention ranking.
        return [[1.0, 0.0] if "ranking" in t.lower() else [0.0, 1.0] for t in texts]
    actions = {a.source_id: a for a in _v2_plan(fake_embed).actions}
    assert actions["b3"].requirement_ids[0] == "r1"

    def broken(texts):
        raise RuntimeError("no model")
    assert {a.source_id: a.action for a in _v2_plan(broken).actions}["b3"] == "REWRITE"


def test_v2_rewriter_gets_only_scoped_requirements_and_keywords():
    from unittest.mock import MagicMock
    from app.analysis.rewriter import LLMRewriter
    resume = _v2_resume()
    evidence = [Evidence(id=f"ev_{b.id}", source_type="experience", source_id=b.id, text=b.text)
                for b in resume.experience[0].bullets]
    plan = TailoringPlanner().create_plan(resume, _v2_job(), evidence, matches=[])
    rewriter = LLMRewriter()
    rewriter.rewrite_role = MagicMock(return_value=({}, None, "unchanged"))
    proposals = rewriter.execute_plan(resume, plan, evidence, _v2_job())
    rewriter.rewrite_role.assert_called_once()  # one call for the whole role
    items = {i["text"]: i for i in rewriter.rewrite_role.call_args.args[1]}
    item = items["Trained LightGBM ranking models in Python."]
    assert item["requirements"][0] == "Build ranking models with LightGBM or PyTorch" and len(item["requirements"]) <= 3
    assert "PyTorch" not in item["keywords"]
    assert "Organised the team offsite." not in items  # KEEP bullets aren't sent
    assert {p.original_text: p.relevance for p in proposals}["Trained LightGBM ranking models in Python."] > 0
