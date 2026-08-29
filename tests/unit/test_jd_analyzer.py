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
