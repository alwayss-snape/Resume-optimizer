"""P8.2: tailoring reports source lines that never reach the output, fails
the run for them, and doesn't count the user's own removals as lost."""
from app.services.tailor import TailorService

REPLICA = "tests/fixtures/resumes/replica_layout.pdf"
JD = "tests/fixtures/jds/replica_layout_jd.txt"


def _tailor(service, parsed, tmp_path):
    with open(JD, encoding="utf-8") as f:
        jd = f.read()
    return service.tailor_resume(REPLICA, jd, str(tmp_path), preapproved_proposals=[], parsed=parsed,
                                 remember_answers=False)


def test_clean_resume_keeps_every_line(tmp_path):
    service = TailorService(llm_client=None)
    result = _tailor(service, service.parse_resume(REPLICA), tmp_path)
    assert result["coverage"]["lost"] == [] and result["coverage"]["pct"] == 100.0
    assert not any(w.startswith(TailorService.COVERAGE_PREFIX) for w in result["warnings"])


def test_a_job_the_user_removed_is_not_lost(tmp_path):
    service = TailorService(llm_client=None)
    parsed = service.parse_resume(REPLICA)
    last = parsed[1].resume.experience[-1].id
    parsed, _ = service.apply_parse_corrections(parsed, {"removed_jobs": [last]})
    result = _tailor(service, parsed, tmp_path)
    assert result["coverage"]["lost"] == []
    assert result["coverage"]["reworded"] >= 1


def test_dropped_content_fails_the_run(tmp_path):
    service = TailorService(llm_client=None)
    parsed = service.parse_resume(REPLICA)
    # Simulate a parser that lost a bullet: it never reaches the model.
    exp = parsed[1].resume.experience[0]
    lost = exp.bullets.pop(0)
    result = _tailor(service, parsed, tmp_path)
    assert result["success"] is False
    assert any(lost.text[:40] in line for line in result["coverage"]["lost"])
    assert any(w.startswith(TailorService.COVERAGE_PREFIX) for w in result["warnings"])
