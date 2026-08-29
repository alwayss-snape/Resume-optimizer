import os
import pytest
from app.services.tailor import TailorService

def test_tailor_service_analyze_only():
    resume_path = "tests/fixtures/resumes/sample.docx"
    jd_path = "tests/fixtures/jds/sample.txt"

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    service = TailorService()
    report = service.analyze_only(resume_path, jd_text)

    assert report.alignment_score > 0.0
    assert len(report.required_matches) > 0

def test_tailor_service_end_to_end_docx(tmp_path):
    resume_path = "tests/fixtures/resumes/sample.docx"
    jd_path = "tests/fixtures/jds/sample.txt"
    out_dir = str(tmp_path / "output")

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    service = TailorService()
    results = service.tailor_resume(resume_path, jd_text, out_dir, mode="PRESERVE")

    assert os.path.exists(results["docx"])
    assert os.path.exists(results["changes_md"])
    assert float(results["alignment_score"]) > 0.0
