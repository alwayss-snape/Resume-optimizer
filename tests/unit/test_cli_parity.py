"""P3.6: progress reporting, and the CLI doing what the UI does (review,
gap answers, additions, a new job, strict mode) through an editable file."""
import json
import os
import subprocess
import sys
from unittest.mock import MagicMock

import docx

from app.cli import read_proposals, write_proposals
from app.eval.harness import OfflineLLM
from app.services.profile_store import ProfileStore
from app.services.run_manager import RunManager
from app.services.tailor import TailorService

RESUME = "tests/fixtures/resumes/sample.docx"
JD = "Requirements:\n- Python and FastAPI services.\n- Experience with Kafka or Flink for streaming."


def _service(tmp_path):
    service = TailorService(llm_client=OfflineLLM())
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    service.profile_store = ProfileStore(str(tmp_path / "facts.json"))
    return service


def test_progress_is_reported_for_both_steps(tmp_path):
    service, seen = _service(tmp_path), []
    generated = service.generate_proposals(RESUME, JD, progress=seen.append)
    assert seen[:3] == ["Reading your resume", "Analysing the job description",
                        "Matching your resume to the job's keywords"]
    assert any(m.startswith("Rewriting") for m in seen)
    seen.clear()
    service.tailor_resume(RESUME, JD, str(tmp_path / "out"), job_desc=generated["job_description"],
                          progress=seen.append)
    assert any("template renderer" in m for m in seen)


def test_a_broken_progress_callback_never_breaks_a_run(tmp_path):
    def boom(_message):
        raise RuntimeError("UI went away")
    assert _service(tmp_path).generate_proposals(RESUME, JD, progress=boom)["proposals"] is not None


def test_proposals_file_round_trip_applies_exactly_the_review(tmp_path):
    service, path = _service(tmp_path), str(tmp_path / "proposals.json")
    data = write_proposals(service, RESUME, JD, path)
    assert data["proposals"] and data["gap_questions"] and data["job_description"]["raw_text"]
    with open(path, encoding="utf-8") as f:
        edited = json.load(f)
    bullets = [p for p in edited["proposals"] if p["kind"] == "bullet"]
    bullets[0]["proposed_text"] = "Owned the FastAPI billing service end to end."  # user edit
    for p in bullets[1:]:
        p["apply"] = False
    kafka = next(q for q in edited["gap_questions"] if "Kafka" in q["keywords"])
    kafka["confirmed_keywords"] = ["Kafka"]
    edited["new_role"] = {"company": "Globex", "title": "Intern", "start_date": "Jan 2012", "end_date": "Jun 2012",
                          "description": "Wrote test scripts."}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(edited, f)

    extra = read_proposals(path)
    applied = [p for p in extra["preapproved_proposals"] if p["kind"] == "bullet"]
    assert len(applied) == 1 and applied[0]["user_edited"] is True and "apply" not in applied[0]
    assert extra["gap_answers"][0]["confirmed_keywords"] == ["Kafka"]
    assert extra["job_desc"].raw_text  # the JD isn't analysed again

    result = service.tailor_resume(RESUME, JD, str(tmp_path / "out"), **extra)
    text = "\n".join(p.text for p in docx.Document(result["docx"]).paragraphs)
    assert "Owned the FastAPI billing service end to end." in text
    assert "Kafka" in text and "Wrote test scripts." in text
    assert "Kafka" in service.profile_store.known(["Kafka"])


def test_rejected_proposals_start_unticked(tmp_path):
    data = write_proposals(_service(tmp_path), RESUME, JD, str(tmp_path / "p.json"))
    assert all(p["apply"] == (p.get("validation") != "REJECT") for p in data["proposals"])


def test_cli_propose_and_tailor_end_to_end(tmp_path):
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text(JD, encoding="utf-8")
    proposals = tmp_path / "proposals.json"
    env = {**os.environ, "PROFILE_PATH": str(tmp_path / "facts.json")}
    run = lambda *args: subprocess.run([sys.executable, "-m", "app.cli", *args], capture_output=True, text=True,
                                       env=env, timeout=300)
    out = run("propose", "--resume", RESUME, "--jd", str(jd_path), "--out", str(proposals))
    assert out.returncode == 0, out.stderr[-2000:]
    assert "Review and edit" in out.stdout and "· Analysing the job description" in out.stdout
    out = run("tailor", "--resume", RESUME, "--jd", str(jd_path), "--proposals", str(proposals),
              "--output", str(tmp_path / "out"), "--strict", "--no-remember")
    assert out.returncode == 0, out.stderr[-2000:]
    assert "Keyword match rate:" in out.stdout and "TAILORING COMPLETE" in out.stdout
    assert not (tmp_path / "facts.json").exists()  # --no-remember
