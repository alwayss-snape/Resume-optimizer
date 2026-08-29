from app.analysis.matcher import EvidenceMatcher
from app.analysis.scoring import AlignmentScorer
from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.report import Match

def test_evidence_matcher_exact_and_alias():
    jd = JobDescription(job_title="Backend Engineer", company="TechCorp", requirements=[
        Requirement(id="req_001", text="Python", category="skill", priority="required"),
        Requirement(id="req_002", text="Postgres", category="skill", priority="required"),
        Requirement(id="req_003", text="React", category="skill", priority="required"),
    ], keywords=["Python", "PostgreSQL"], raw_text="Test JD")
    evidence = [
        Evidence(id="ev_001", source_type="skill", source_id="s1", text="Python"),
        Evidence(id="ev_002", source_type="skill", source_id="s2", text="PostgreSQL"),
    ]

    matches = {m.requirement_id: m for m in EvidenceMatcher().match(jd, evidence)}
    assert matches["req_001"].status == "EXPLICIT"
    assert matches["req_001"].evidence_ids == ["ev_001"]
    assert matches["req_002"].status == "EXPLICIT"
    assert matches["req_003"].status == "MISSING"

def test_one_generic_word_cannot_create_a_strong_match():
    jd = JobDescription(job_title="AI Engineer", company="Company", requirements=[
        Requirement(id="req_001", text="Develop machine learning systems", category="responsibility", priority="required"),
    ], keywords=[], raw_text="")
    evidence = [Evidence(id="ev_001", source_type="experience", source_id="b1",
                         text="Developed reporting dashboards for finance.")]
    match = EvidenceMatcher().match(jd, evidence)[0]
    assert match.status == "MISSING"
    assert match.evidence_ids == []

def test_alignment_scorer_requires_cited_evidence():
    requirement = Requirement(id="req_001", text="Python", category="skill", priority="required")
    uncited = Match(requirement_id="req_001", requirement_text="Python",
                    status="EXPLICIT", evidence_ids=[])
    assert AlignmentScorer().calculate_score([uncited], [requirement]) == 0.0
