from app.analysis.scoring import AlignmentScorer
from app.domain.job import Requirement
from app.domain.report import Match


def _req(id_, category="skill", criticality="required", weight=None):
    return Requirement(id=id_, text=id_, category=category, criticality=criticality,
                        priority="required" if criticality != "preferred" else "preferred", weight=weight)


def _match(req_id, status, evidence_ids=None, confidence=1.0):
    return Match(requirement_id=req_id, requirement_text=req_id, status=status,
                 evidence_ids=evidence_ids or [], explanation="", confidence=confidence)


def test_semantic_partial_excluded_from_headline_score():
    """A requirement matched only via SEMANTIC_PARTIAL must score identically
    to MISSING on the headline number — semantic inference is informational,
    not counted as hard evidence in calculate_score."""
    requirement = _req("req_001")

    semantic = [_match("req_001", "SEMANTIC_PARTIAL", evidence_ids=["ev_001"], confidence=0.65)]
    missing = [_match("req_001", "MISSING")]

    scorer = AlignmentScorer()
    assert scorer.calculate_score(semantic, [requirement]) == scorer.calculate_score(missing, [requirement])
    assert scorer.calculate_score(semantic, [requirement]) == 0.0


def test_semantic_coverage_reflects_semantic_matches_only():
    req_a = _req("req_a")
    req_b = _req("req_b")
    matches = [
        _match("req_a", "SEMANTIC_PARTIAL", evidence_ids=["ev_001"], confidence=0.7),
        _match("req_b", "MISSING"),
    ]
    comps = AlignmentScorer().calculate_components(matches, [req_a, req_b])
    assert comps["semantic_coverage"] > 0.0
    # And it must not have leaked into the hard-evidence coverage buckets.
    assert comps["required_coverage"] == 0.0


def test_explicit_match_unaffected_by_semantic_coverage_field():
    requirement = _req("req_001", criticality="critical")
    matches = [_match("req_001", "EXPLICIT", evidence_ids=["ev_001"])]
    comps = AlignmentScorer().calculate_components(matches, [requirement])
    assert comps["required_coverage"] == 100.0
    assert comps["semantic_coverage"] == 0.0


def test_mixed_requirements_headline_score_matches_pre_semantic_behavior():
    """Adding one SEMANTIC_PARTIAL requirement alongside an EXPLICIT one must
    not change the EXPLICIT requirement's contribution to the score, and must
    not raise the headline score above what pure MISSING would have given."""
    req_explicit = _req("req_explicit")
    req_semantic = _req("req_semantic")

    matches_with_semantic = [
        _match("req_explicit", "EXPLICIT", evidence_ids=["ev_001"]),
        _match("req_semantic", "SEMANTIC_PARTIAL", evidence_ids=["ev_002"], confidence=0.6),
    ]
    matches_with_missing = [
        _match("req_explicit", "EXPLICIT", evidence_ids=["ev_001"]),
        _match("req_semantic", "MISSING"),
    ]

    scorer = AlignmentScorer()
    score_semantic = scorer.calculate_score(matches_with_semantic, [req_explicit, req_semantic])
    score_missing = scorer.calculate_score(matches_with_missing, [req_explicit, req_semantic])
    assert score_semantic == score_missing


def test_default_criticality_requirement_counts_as_required_coverage():
    """Regression: Requirement.criticality defaults to 'required' (not
    'critical'), but the bucket check previously only matched 'critical'.
    An ordinary default-criticality requirement must land in
    required_coverage, not silently fall through to keyword_coverage."""
    requirement = _req("req_001", criticality="required")  # the actual default
    matches = [_match("req_001", "EXPLICIT", evidence_ids=["ev_001"])]
    comps = AlignmentScorer().calculate_components(matches, [requirement])
    assert comps["required_coverage"] == 100.0
    assert comps["keyword_coverage"] == 0.0
