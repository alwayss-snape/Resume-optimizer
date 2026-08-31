import os
import pytest
from app.analysis.jd_analyzer import JDAnalyzer
from app.domain.job import JobDescription

def test_jd_analyzer_heuristic():
    sample_jd_path = "tests/fixtures/jds/sample.txt"
    assert os.path.exists(sample_jd_path)

    with open(sample_jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    analyzer = JDAnalyzer(llm_client=None)  # Test deterministic heuristic mode
    jd = analyzer.analyze(jd_text)

    assert isinstance(jd, JobDescription)
    assert jd.job_title == "Senior Backend Engineer"
    assert jd.company == "CloudScale Inc."
    assert len(jd.requirements) >= 4

    req_priorities = [r.priority for r in jd.requirements]
    assert "required" in req_priorities
    assert "preferred" in req_priorities


def test_heading_variants_are_not_extracted_as_requirements():
    """Headings with a qualifier prefix (Minimum/Preferred/Required/Technical
    + Qualifications/Skills/Requirements) must be filtered out, not treated
    as literal requirement text. This was a real regression found when
    testing against a live JD: 'Minimum Qualifications' was extracted as its
    own nonsensical requirement."""
    jd_text = (
        "Minimum Qualifications\n"
        "- 3+ years of experience with Python.\n"
        "Preferred Qualifications\n"
        "- Experience with Kubernetes.\n"
        "Technical Skills\n"
        "- SQL proficiency.\n"
    )
    jd = JDAnalyzer().analyze(jd_text)
    requirement_texts = [r.text.lower() for r in jd.requirements]
    assert not any("minimum qualifications" in t for t in requirement_texts)
    assert not any("preferred qualifications" in t for t in requirement_texts)
    assert not any("technical skills" in t for t in requirement_texts)
    # But the actual content beneath each heading must still come through.
    assert any("python" in t for t in requirement_texts)
    assert any("kubernetes" in t for t in requirement_texts)
    assert any("sql" in t for t in requirement_texts)


def test_heading_like_words_inside_real_requirements_are_not_filtered():
    """A genuine requirement sentence that happens to contain a heading-like
    word (e.g. 'skills', 'required') must NOT be mistaken for a heading and
    dropped entirely, since it has real content beyond just that word.
    (Note: whether it gets segmented into multiple fragments is a separate,
    pre-existing concern in _segment_line, not what this test checks.)"""
    jd_text = "Requirements:\n- Skills in Python and machine learning are required for this role.\n"
    jd = JDAnalyzer().analyze(jd_text)
    combined_text = " ".join(r.text for r in jd.requirements)
    assert "Skills in Python" in combined_text
    assert "required for this role" in combined_text
