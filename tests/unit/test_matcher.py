import pytest
from app.analysis.matcher import EvidenceMatcher
from app.analysis.scoring import AlignmentScorer
from app.domain.evidence import Evidence
from app.domain.job import JobDescription, Requirement
from app.domain.report import Match

def test_evidence_matcher_exact_and_alias():
    jd = JobDescription(
        job_title="Backend Engineer",
        company="TechCorp",
        requirements=[
            Requirement(id="req_001", text="Python", category="skill", priority="required"),
            Requirement(id="req_002", text="Postgres", category="skill", priority="required"),
            Requirement(id="req_003", text="React", category="skill", priority="required"),
        ],
        keywords=["Python", "PostgreSQL"],
        raw_text="Test JD",
    )

    evidence_list = [
        Evidence(id="ev_001", source_type="skill", source_id="s1", text="Python"),
        Evidence(id="ev_002", source_type="skill", source_id="s2", text="PostgreSQL"),
    ]

    matcher = EvidenceMatcher()
    matches = matcher.match(jd, evidence_list)

    assert len(matches) == 3
    match_dict = {m.requirement_id: m for m in matches}

    # Python -> EXPLICIT
    assert match_dict["req_001"].status in ("EXPLICIT", "SUPPORTED")
    assert "ev_001" in match_dict["req_001"].evidence_ids

    # Postgres -> PostgreSQL alias match
    assert match_dict["req_002"].status in ("EXPLICIT", "SUPPORTED")

    # React -> MISSING
    assert match_dict["req_003"].status == "MISSING"

def test_alignment_scorer():
    requirements = [
        Requirement(id="req_001", text="Python", category="skill", priority="required"),
        Requirement(id="req_002", text="Postgres", category="skill", priority="required"),
        Requirement(id="req_003", text="React", category="skill", priority="required"),
    ]

    matches = [
        Match(requirement_id="req_001", requirement_text="Python", status="EXPLICIT", evidence_ids=["ev_1"]),
        Match(requirement_id="req_002", requirement_text="Postgres", status="SUPPORTED", evidence_ids=["ev_2"]),
        Match(requirement_id="req_003", requirement_text="React", status="MISSING", evidence_ids=[]),
    ]

    scorer = AlignmentScorer()
    score = scorer.calculate_score(matches, requirements)
    assert 0.0 <= score <= 100.0
    assert score > 50.0  # 2 of 3 matched should score > 50
