from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.report import Match
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.services.tailor import TailorService


def _service():
    # No Ollama server reachable in test environments -> LLMClient.is_available()
    # returns False deterministically, so rewrite_bullet/suggest_* fall back to
    # returning the input unchanged. This exercises the structural behavior of
    # incorporate_user_addition (placement + evidence bookkeeping) without
    # depending on a live LLM.
    return TailorService()


def test_incorporate_user_addition_appends_bullet_to_most_recent_experience():
    service = _service()
    resume = Resume(
        candidate=Candidate(name="Jane Doe"),
        experience=[
            Experience(
                id="exp_001",
                company="Acme",
                title="Engineer",
                bullets=[ResumeBullet(id="exp_001_b01", text="Built things.")],
            )
        ],
    )
    evidence_list = [Evidence(id="ev_001", source_type="experience", source_id="exp_001_b01", text="Acme: Built things.")]
    jd = JobDescription(
        job_title="Engineer",
        requirements=[Requirement(id="req_001", text="Python", category="skill")],
        raw_text="Test",
        keywords=["Python"],
    )

    updated_resume, updated_evidence, _note = service.incorporate_user_addition(
        resume, evidence_list, jd, "Led a hackathon project building a Python chatbot.", target="auto",
    )

    assert updated_resume is resume  # mutated in place
    assert len(updated_resume.experience[0].bullets) == 2
    new_bullet = updated_resume.experience[0].bullets[-1]
    assert "hackathon" in new_bullet.text.lower() or "chatbot" in new_bullet.text.lower()
    assert len(updated_evidence) == len(evidence_list) + 1
    assert updated_evidence[-1].source_id == new_bullet.id


def test_incorporate_user_addition_new_project_target():
    service = _service()
    resume = Resume(candidate=Candidate(name="Jane Doe"), experience=[], projects=[])
    jd = JobDescription(job_title="Engineer", requirements=[], raw_text="Test", keywords=[])

    updated_resume, updated_evidence, _note = service.incorporate_user_addition(
        resume, [], jd, "Built a personal finance tracker app.", target="new_project",
    )

    assert len(updated_resume.projects) == 1
    assert len(updated_resume.projects[0].bullets) == 1
    assert len(updated_evidence) == 1


def test_incorporate_user_addition_falls_back_to_project_when_no_experience():
    """target='auto' with zero Experience entries must not drop the addition."""
    service = _service()
    resume = Resume(candidate=Candidate(name="Jane Doe"), experience=[], projects=[])
    jd = JobDescription(job_title="Engineer", requirements=[], raw_text="Test", keywords=[])

    updated_resume, updated_evidence, _note = service.incorporate_user_addition(
        resume, [], jd, "Volunteered building a nonprofit's website.", target="auto",
    )

    assert len(updated_resume.projects) == 1
    assert len(updated_evidence) == 1


def test_incorporate_user_addition_blank_text_is_noop():
    service = _service()
    resume = Resume(candidate=Candidate(name="Jane Doe"))
    jd = JobDescription(raw_text="")

    resume_out, evidence_out, note = service.incorporate_user_addition(resume, [], jd, "   ")

    assert resume_out is resume
    assert evidence_out == []
    assert note is None


def test_rank_missing_requirements_orders_required_before_preferred():
    service = _service()
    jd = JobDescription(
        job_title="Engineer",
        requirements=[
            Requirement(id="req_001", text="Nice to have", category="skill", priority="preferred"),
            Requirement(id="req_002", text="Must have", category="skill", priority="required"),
        ],
        raw_text="Test",
    )
    missing = [
        Match(requirement_id="req_001", requirement_text="Nice to have", status="MISSING"),
        Match(requirement_id="req_002", requirement_text="Must have", status="MISSING"),
    ]

    ranked = service.planner.rank_missing_requirements(missing, jd, limit=5)
    assert ranked[0].requirement_text == "Must have"
    assert ranked[1].requirement_text == "Nice to have"
