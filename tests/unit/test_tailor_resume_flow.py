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
    # The skills reorder (P1.6) is deterministic, so it's offered without an LLM.
    llm_made = [p for p in out["proposals"] if p.kind != "skills"]
    assert status["failed"] == status["attempted"] - 1 == len(llm_made)
    assert all(p.status == "llm_unavailable" for p in llm_made)
    assert [p.kind for p in out["proposals"] if p.status == "ok"] == ["skills"]
    assert out["llm_usage"] is not None


def test_user_edited_text_is_kept_not_silently_dropped(tmp_path):
    """Regression (F17): the user's own wording went through the fact-checker
    and was silently dropped when it used a word not in the source bullet."""
    service = _service(tmp_path)
    (b, ev), _ = _bullets_with_evidence()[:2]
    prop = _proposal(b, ev, b.text.rstrip(".") + " for Zanzibar Corp.")
    prop["user_edited"] = True

    result = service.tailor_resume(SAMPLE_DOCX, SAMPLE_JD, str(tmp_path / "out"), mode="ATS_DEFAULT",
                                   preapproved_proposals=[prop])
    assert "Zanzibar Corp" in _docx_text(result["docx"])
    assert any("not fact-checked" in w for w in result["warnings"])


def test_generate_proposals_attaches_validation_verdicts(tmp_path):
    from app.llm.schemas import BulletRewriteResult
    service = _service(tmp_path)
    fake = MagicMock(provider="groq", model="m", last_error=None)
    fake.is_available.return_value = True
    fake.generate_json.side_effect = lambda **kw: (
        BulletRewriteResult(rewritten="Successfully " + kw["messages"][1]["content"].split("\n")[1])
        if kw["schema_model"] is BulletRewriteResult else (_ for _ in ()).throw(Exception("no"))
    )
    fake.get_usage_summary.return_value = {}
    service.rewriter.llm_client = fake
    out = service.generate_proposals(SAMPLE_DOCX, SAMPLE_JD)
    assert out["proposals"] and all(p.validation in ("PASS", "NEEDS_CONFIRM", "REJECT") for p in out["proposals"])
    assert any(p.validation == "PASS" for p in out["proposals"])


def test_jd_analysis_is_reused_and_scores_are_keyword_match_rates(tmp_path):
    """The JD analysed for the proposals is passed on, so Apply & Generate
    makes no second JD call and before/after rates use the same keywords."""
    service = _service(tmp_path)
    job = service.jd_analyzer.analyze(SAMPLE_JD)
    service.jd_analyzer.analyze = MagicMock(side_effect=AssertionError("JD must not be re-analysed"))

    result = service.tailor_resume(
        SAMPLE_DOCX, SAMPLE_JD, str(tmp_path / "out"), mode="ATS_DEFAULT",
        preapproved_proposals=[], job_desc=job,
    )
    report = result["keyword_match"]
    assert float(result["alignment_score"]) == report.rate
    assert result["initial_alignment_score"] == result["alignment_score"]  # nothing applied
    changes = open(result["changes_md"], encoding="utf-8").read()
    assert "## Keyword Match" in changes and "| Python |" in changes


def test_page_fit_trims_are_reported_and_rendered(tmp_path, monkeypatch):
    """P2.4: tailor_resume fits the template to the page target and reports
    each step, respecting the per-role bullet minimums."""
    import app.services.tailor as tailor_module
    from app.rendering.page_fit import PAGE_BODY_PT, PageFitter

    service = _service(tmp_path)
    fake_pdf = str(tmp_path / "fake.pdf")
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=fake_pdf)
    service.qa_validator.validate_pdf = MagicMock(return_value=[])
    lengths = iter([(2, 30.0), (1, PAGE_BODY_PT - 50)])  # first render overflows, second fits
    monkeypatch.setattr(tailor_module, "target_pages", lambda resume: 1)  # the fixture has 8+ years
    monkeypatch.setattr(tailor_module, "PageFitter",
                        lambda render: PageFitter(render, measure=lambda _pdf: next(lengths)))

    result = service.tailor_resume(SAMPLE_DOCX, SAMPLE_JD, str(tmp_path / "out"), mode="ATS_DEFAULT")
    # The fixture is already at the bullet minimums (3 and 2), so compact
    # spacing is the only step allowed; no bullet is removed.
    trims = [w for w in result["warnings"] if "to fit the page" in w]
    assert trims == ["Used compact spacing to fit the page."], result["warnings"]
    assert result["pdf"] and result["target_pages"] == 1
    report = open(result["changes_md"], encoding="utf-8").read()
    assert all(t in report for t in trims)
    assert "1 page(s), target 1, 2 render(s)" in report
