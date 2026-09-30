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


def test_check_llm_reports_success_and_failure(capsys):
    from unittest.mock import MagicMock, patch
    from app.cli import check_llm
    from app.llm.schemas import BulletRewriteResult

    ok_client = MagicMock(provider="groq", model="m", last_error=None)
    ok_client.is_available.return_value = True
    ok_client.generate_json.return_value = BulletRewriteResult(rewritten="Built Python pipelines for 2M events/day.")
    ok_client.get_usage_summary.return_value = {"total_prompt_tokens": 10, "total_completion_tokens": 5}
    with patch("app.llm.client.LLMClient", return_value=ok_client):
        assert check_llm() == 0
    assert "OK in" in capsys.readouterr().out

    bad_client = MagicMock(provider="groq", model="m", last_error="GROQ_API_KEY is not set")
    bad_client.is_available.return_value = False
    with patch("app.llm.client.LLMClient", return_value=bad_client):
        assert check_llm() == 1
    assert "GROQ_API_KEY is not set" in capsys.readouterr().out
