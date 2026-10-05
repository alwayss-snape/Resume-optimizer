"""P9.8: a web run keeps nothing in data/runs; the CLI still keeps its run folder."""
import os
from unittest.mock import MagicMock

from app.api.main import default_service
from app.eval.harness import OfflineLLM
from app.services.run_manager import RunManager
from app.services.tailor import TailorService

SAMPLE_DOCX = os.path.abspath("tests/fixtures/resumes/sample.docx")
with open("tests/fixtures/jds/sample.txt", encoding="utf-8") as _f:
    SAMPLE_JD = _f.read()


def _tailor(service, tmp_path):
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)  # no LibreOffice needed
    steps = []
    results = service.tailor_resume(SAMPLE_DOCX, SAMPLE_JD, str(tmp_path / "out"), progress=steps.append)
    return results, steps


def test_the_web_service_keeps_no_run_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # data/runs would be created here
    assert default_service().run_manager is None  # what the web app uses
    service = TailorService(llm_client=OfflineLLM(), keep_run=False)
    results, steps = _tailor(service, tmp_path)
    assert results["run_dir"] is None
    assert not os.path.exists(tmp_path / "data" / "runs")
    assert not any("Run created" in s for s in steps)  # no server path on the visitor's screen
    assert os.path.exists(results["docx"])


def test_the_cli_keeps_its_run_folder(tmp_path):
    service = TailorService(llm_client=OfflineLLM())
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    results, _ = _tailor(service, tmp_path)
    assert results["run_dir"] and os.path.exists(os.path.join(results["run_dir"], "jd.txt"))
