"""tailor_resume orchestration: pre-approved proposals and Strict Factual Mode."""
from unittest.mock import MagicMock

import docx
import pytest

from app.analysis.resume_normalizer import ResumeNormalizer
from app.analysis.rewriter import RewriteProposal
from app.ingestion.docx import DocxParser
from app.services.run_manager import RunManager
from app.services.tailor import TailorService

SAMPLE_DOCX = "tests/fixtures/resumes/sample.docx"
with open("tests/fixtures/jds/sample.txt", encoding="utf-8") as _f:
    SAMPLE_JD = _f.read()


def _service(tmp_path):
    service = TailorService()
    service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)  # no LibreOffice needed
    return service


def _bullets_with_evidence():
    resume_doc, evidence = ResumeNormalizer().normalize(DocxParser().parse(SAMPLE_DOCX))
    pairs = []
    for exp in resume_doc.resume.experience:
        for b in exp.bullets:
            ev = next((e for e in evidence if e.source_id == b.id), None)
            if ev:
                pairs.append((b, ev))
    assert len(pairs) >= 2, "fixture needs at least two evidenced bullets"
    return pairs


def _proposal(bullet, ev, new_text):
    return RewriteProposal(
        target_semantic_id=bullet.id, target_source_location_id=bullet.source_location_id or bullet.id,
        original_text=bullet.text, proposed_text=new_text, evidence_ids=[ev.id], rationale="test",
    ).model_dump()


def _docx_text(path):
    return "\n".join(p.text for p in docx.Document(path).paragraphs)


def test_preapproved_proposals_skip_the_rewriter(tmp_path):
    service = _service(tmp_path)
    service.rewriter.execute_plan = MagicMock(side_effect=AssertionError("rewriter must not run"))
    (b, ev), _ = _bullets_with_evidence()[:2]

    result = service.tailor_resume(
        SAMPLE_DOCX, SAMPLE_JD, str(tmp_path / "out"), mode="ATS_DEFAULT",
        preapproved_proposals=[_proposal(b, ev, "Successfully " + b.text)],
    )
    service.rewriter.execute_plan.assert_not_called()
    assert "Successfully" in _docx_text(result["docx"])


@pytest.mark.parametrize("strict", [False, True])
def test_strict_mode_is_decided_before_rendering(tmp_path, strict):
    service = _service(tmp_path)
    (good_b, good_ev), (bad_b, bad_ev) = _bullets_with_evidence()[:2]
    proposals = [
        _proposal(good_b, good_ev, "Successfully " + good_b.text),          # passes validation
        _proposal(bad_b, bad_ev, bad_b.text.rstrip(".") + " using Zanzibar."),  # unsupported term -> rejected
    ]

    result = service.tailor_resume(
        SAMPLE_DOCX, SAMPLE_JD, str(tmp_path / "out"), mode="ATS_DEFAULT",
        strict_factual=strict, preapproved_proposals=proposals,
    )
    text = _docx_text(result["docx"])
    report = open(result["changes_md"], encoding="utf-8").read()

    assert "Zanzibar" not in text  # rejected rewrite never rendered
    if strict:
        assert "Successfully" not in text  # all-or-nothing: the valid one is withheld too
        assert any("Strict Factual Mode" in w for w in result["warnings"])
        assert "## Accepted Rewrites (0)" in report
    else:
        assert "Successfully" in text
        assert "## Accepted Rewrites (1)" in report
    # The progress log survives and the summary is written exactly once.
    assert "## Progress Log" in report
    assert report.count("## Final Summary") == 1


def test_generate_proposals_reports_llm_status_when_unavailable(tmp_path):
    service = _service(tmp_path)  # conftest pins an unreachable local provider
    out = service.generate_proposals(SAMPLE_DOCX, SAMPLE_JD)
    status = out["llm_status"]
    assert out["llm_available"] is False and status["available"] is False
    assert status["reason"]  # a human-readable cause, shown in the UI
    assert status["failed"] == status["attempted"] == len(out["proposals"])
    assert all(p.status == "llm_unavailable" for p in out["proposals"])
    assert out["llm_usage"] is not None
