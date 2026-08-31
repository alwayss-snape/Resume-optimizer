"""Tests for SemanticMatcher.

Uses a fake, hand-rolled embedder (bag-of-words one-hot-ish vectors) instead
of a real ML model, so these tests are fast, deterministic, and don't require
sentence-transformers/torch to be installed. The real model is exercised only
via the lazy import path in semantic_matcher.py itself, not in these tests.
"""
import math

from app.analysis.semantic_matcher import SemanticMatcher
from app.domain.evidence import Evidence
from app.domain.job import Requirement
from app.domain.report import Match


_CONCEPT_GROUPS = [
    # "teamwork" concept: both a requirement phrase and a differently-worded
    # resume bullet about the same underlying idea land on this one shared
    # dimension, simulating what a real embedding model would do for a
    # genuine paraphrase (different words, same meaning).
    {"collaborate", "cross-functional", "stakeholders", "worked", "closely", "product", "design", "teams"},
    {"python"},
    {"excel"},
    {"unrelated", "gardening", "hobby"},
]


def _fake_embedder(texts):
    """A deterministic 'embedding' for testing: represents each text as a
    vector over a small set of concept groups (not literal shared words),
    so two differently-worded texts about the same concept get high cosine
    similarity — mirroring what we actually need a real embedding model to
    do, without pulling one in for these unit tests."""
    vectors = []
    for text in texts:
        lowered = text.lower()
        vec = [
            float(sum(1 for word in group if word in lowered))
            for group in _CONCEPT_GROUPS
        ]
        vectors.append(vec)
    return vectors


def _missing_match(req_id: str, text: str) -> Match:
    return Match(
        requirement_id=req_id, requirement_text=text,
        status="MISSING", evidence_ids=[], explanation="No resume evidence supports this requirement.",
        confidence=0.0,
    )


def test_semantic_partial_on_paraphrase():
    req = Requirement(id="req_001", text="collaborate cross-functional stakeholders", category="responsibility", priority="required")
    evidence = [Evidence(id="ev_001", source_type="experience", source_id="b1",
                          text="worked closely product design teams")]
    existing = [_missing_match("req_001", req.text)]

    matcher = SemanticMatcher(embedder=_fake_embedder, threshold=0.3)
    result = matcher.match([req], evidence, existing)

    assert len(result) == 1
    assert result[0].status == "SEMANTIC_PARTIAL"
    assert result[0].evidence_ids == ["ev_001"]
    assert result[0].confidence > 0
    assert "ev_001" in result[0].explanation


def test_stays_missing_below_threshold():
    req = Requirement(id="req_001", text="collaborate cross-functional stakeholders", category="responsibility", priority="required")
    evidence = [Evidence(id="ev_001", source_type="experience", source_id="b1",
                          text="unrelated gardening hobby")]
    existing = [_missing_match("req_001", req.text)]

    matcher = SemanticMatcher(embedder=_fake_embedder, threshold=0.3)
    result = matcher.match([req], evidence, existing)

    assert result[0].status == "MISSING"
    assert result[0].evidence_ids == []


def test_never_overrides_non_missing_status():
    req_explicit = Requirement(id="req_001", text="Python", category="skill", priority="required")
    req_missing = Requirement(id="req_002", text="collaborate cross-functional stakeholders", category="responsibility", priority="required")
    evidence = [
        Evidence(id="ev_001", source_type="skill", source_id="s1", text="Python"),
        Evidence(id="ev_002", source_type="experience", source_id="b1", text="worked closely product design teams"),
    ]
    existing = [
        Match(requirement_id="req_001", requirement_text="Python", status="EXPLICIT",
              evidence_ids=["ev_001"], explanation="Exact match", confidence=1.0),
        _missing_match("req_002", req_missing.text),
    ]

    matcher = SemanticMatcher(embedder=_fake_embedder, threshold=0.3)
    result = matcher.match([req_explicit, req_missing], evidence, existing)

    by_id = {m.requirement_id: m for m in result}
    # Untouched — even though semantic similarity to ev_001 would also be
    # computable, this match was already EXPLICIT and must pass through as-is.
    assert by_id["req_001"].status == "EXPLICIT"
    assert by_id["req_001"].evidence_ids == ["ev_001"]
    assert by_id["req_001"].confidence == 1.0
    # The genuinely missing one is still upgraded.
    assert by_id["req_002"].status == "SEMANTIC_PARTIAL"


def test_disabled_flag_is_a_no_op():
    req = Requirement(id="req_001", text="collaborate cross-functional stakeholders", category="responsibility", priority="required")
    evidence = [Evidence(id="ev_001", source_type="experience", source_id="b1",
                          text="worked closely product design teams")]
    existing = [_missing_match("req_001", req.text)]

    matcher = SemanticMatcher(embedder=_fake_embedder, threshold=0.3, enabled=False)
    result = matcher.match([req], evidence, existing)

    assert result[0].status == "MISSING"


def test_embedder_exception_falls_back_gracefully():
    def _broken_embedder(texts):
        raise RuntimeError("simulated embedding failure")

    req = Requirement(id="req_001", text="collaborate cross-functional stakeholders", category="responsibility", priority="required")
    evidence = [Evidence(id="ev_001", source_type="experience", source_id="b1", text="worked closely product design teams")]
    existing = [_missing_match("req_001", req.text)]

    matcher = SemanticMatcher(embedder=_broken_embedder, threshold=0.3)
    result = matcher.match([req], evidence, existing)

    # Must not raise, and must fall back to the deterministic result untouched.
    assert result[0].status == "MISSING"


def test_no_missing_requirements_short_circuits():
    req = Requirement(id="req_001", text="Python", category="skill", priority="required")
    existing = [Match(requirement_id="req_001", requirement_text="Python", status="EXPLICIT",
                       evidence_ids=["ev_001"], explanation="Exact match", confidence=1.0)]
    evidence = [Evidence(id="ev_001", source_type="skill", source_id="s1", text="Python")]

    matcher = SemanticMatcher(embedder=_fake_embedder, threshold=0.3)
    result = matcher.match([req], evidence, existing)

    assert result == existing
