"""P3.4: the proposal review screen (diff, badges, breakdown, gap table,
accept/reject all, recalculated match rate)."""
import os
import shutil
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.analysis.change_proposal import ChangeProposal
from app.analysis.keyword_match import KeywordMatcher
from app.domain.job import JobDescription, Requirement
from app.domain.report import KeywordMatchReport, KeywordRow
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument
from app.rendering.review_view import diff_html, gap_table, score_breakdown, status_badge
from app.services.tailor import TailorService


def test_diff_marks_removed_added_and_keywords_and_escapes():
    left, right = diff_html("Built <fast> pipelines in python", "Built Spark pipelines in Python on AWS",
                            keywords=["Spark", "Python", "AWS"])
    assert "line-through" in left and "&lt;fast&gt;" in left and "<fast>" not in left
    assert "dcfce7" in right  # added words highlighted
    assert right.count("font-weight:700") == 3  # Spark, Python, AWS
    assert "font-weight:700" in left  # "python" is a keyword on the left too


def test_multi_word_keyword_is_highlighted_whole():
    _, right = diff_html("x", "Built feature stores for ML.", keywords=["feature stores"])
    assert right.count("font-weight:700") == 2


def test_status_badges():
    assert status_badge("llm_error", "PASS", True)[0].startswith("❌")
    assert status_badge("ok", "REJECT", True)[0].startswith("⛔")
    assert status_badge("ok", "NEEDS_CONFIRM", True)[0].startswith("⚠️")
    assert status_badge("unchanged", "PASS", False)[0].startswith("➖")
    assert status_badge("ok", "PASS", True)[0].startswith("✅")


def _report():
    return KeywordMatchReport(rate=60.0, rows=[
        KeywordRow(keyword="Python", kind="hard", weight=4.5, found=True, credit=1.0),
        KeywordRow(keyword="Kafka", kind="hard", weight=4.5, found=False),
        KeywordRow(keyword="Senior Engineer", kind="title", weight=3.0, found=True, credit=0.5),
        KeywordRow(keyword="mentoring", kind="soft", required=False, weight=1.0, found=False),
    ])


def test_score_breakdown_adds_up_to_the_rate():
    rows = score_breakdown(_report())
    assert [r["Kind"] for r in rows] == ["Hard skills", "Job title", "Soft skills"]
    earned = sum(float(r["Points"].split(" of ")[0]) for r in rows)
    assert abs(earned - (4.5 + 1.5) / 13 * 100) < 0.2  # title counts its partial credit


def test_gap_table_orders_required_first_and_marks_asked():
    rows = gap_table(_report(), asked=["kafka"])
    assert [r["Missing keyword"] for r in rows] == ["Kafka", "mentoring"]
    assert rows[0]["Asked below"] == "yes" and rows[1]["Asked below"] == "—"


def _parsed():
    resume = Resume(candidate=Candidate(name="A"), summary="Engineer.", experience=[Experience(
        id="e1", company="Acme", title="Engineer",
        bullets=[ResumeBullet(id="b1", text="Built pipelines.")])], skills={"Languages": ["Python"]})
    return (None, ResumeDocument(resume=resume), [])


def _job():
    return JobDescription(requirements=[Requirement(id="r1", text="Kafka and Python")],
                          keywords=["Kafka", "Python"], raw_text="Kafka and Python")


def test_preview_applies_ticked_edits_without_touching_the_parse():
    parsed = _parsed()
    service = TailorService(llm_client=None)
    before = service.preview_keyword_match(parsed, _job(), [])
    after = service.preview_keyword_match(parsed, _job(), [
        {"kind": "bullet", "target_semantic_id": "b1", "proposed_text": "Built Kafka pipelines."}])
    assert after.rate > before.rate
    assert parsed[1].resume.experience[0].bullets[0].text == "Built pipelines."  # original untouched


def _proposal(i, text, new, validation="PASS", status="ok"):
    return ChangeProposal(id=f"p{i}", target_semantic_id="b1", target_source_location_id="b1",
                          original_text=text, proposed_text=new, validation=validation, status=status)


def _app(tmp_path, proposals):
    resume_copy = tmp_path / "upload.docx"
    shutil.copy("tests/fixtures/resumes/sample.docx", resume_copy)
    job = _job()
    at = AppTest.from_file(os.path.abspath("app/ui.py"), default_timeout=60)
    for key, value in {"stage": "proposals", "proposals": proposals, "gap_questions": [],
                       "experience_options": [], "resume_path": str(resume_copy), "jd_text": "x",
                       "model_choice": "m", "render_mode": "ATS_DEFAULT", "strict_factual": False,
                       "pre_score": 10.0, "parsed": _parsed(), "job_description": job,
                       "keyword_match": KeywordMatcher().match(job, _parsed()[1].resume)}.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    return at


def test_review_shows_badges_diff_and_gap_table(tmp_path):
    at = _app(tmp_path, [_proposal(1, "Built pipelines.", "Built Kafka pipelines."),
                         _proposal(2, "Built pipelines.", "Built pipelines.", validation="REJECT")])
    md = " ".join(m.value for m in at.markdown)
    assert "✅ Pass" in md and "⛔ Will be dropped" in md
    assert "dcfce7" in md  # the diff is rendered
    assert any("Keyword gaps" in e.label for e in at.expander)


def test_accept_all_and_reject_all(tmp_path):
    at = _app(tmp_path, [_proposal(1, "a", "b"), _proposal(2, "c", "d")])
    next(b for b in at.button if b.label == "✖️ Reject all").click().run()
    assert [c.value for c in at.checkbox if c.label == "Apply"] == [False, False]
    next(b for b in at.button if b.label == "✅ Accept all").click().run()
    assert [c.value for c in at.checkbox if c.label == "Apply"] == [True, True]


def test_recalculate_uses_ticked_edited_text_and_generates_nothing(tmp_path):
    at = _app(tmp_path, [_proposal(1, "Built pipelines.", "Built pipelines.")])
    next(t for t in at.text_area if t.label.startswith("Edit proposed text")).input("Built Kafka pipelines.")
    with patch.object(TailorService, "tailor_resume") as tailor:
        next(b for b in at.button if b.label == "🔄 Recalculate match rate").click().run()
    assert not at.exception and not tailor.called
    live = at.session_state["live_match"]
    assert any(r.keyword == "Kafka" and r.found for r in live.rows)
    assert any(m.label == "Match rate with your current selection" for m in at.metric)


def test_diff_neutralises_markdown_and_latex_and_keeps_lines():
    left, right = diff_html("Cut cost from $2M to $1M", "Cut *cost* from $2M to $1M_x\nTools: Git",
                            keywords=[".NET"])
    for html_out in (left, right):
        assert "$" not in html_out and "*" not in html_out and "_" not in html_out.replace("line-through", "")
    assert "&#36;2M" in left and "<br>" in right


def test_dotnet_highlights():
    _, right = diff_html("", "Built .NET services.", keywords=[".NET"])
    assert "font-weight:700" in right


def test_preview_skips_rejected_unless_edited():
    parsed, service = _parsed(), TailorService(llm_client=None)
    rejected = {"kind": "bullet", "target_semantic_id": "b1", "proposed_text": "Built Kafka pipelines.",
                "validation": "REJECT"}
    assert not any(r.keyword == "Kafka" and r.found
                   for r in service.preview_keyword_match(parsed, _job(), [rejected]).rows)
    edited = {**rejected, "user_edited": True}
    assert any(r.keyword == "Kafka" and r.found
               for r in service.preview_keyword_match(parsed, _job(), [edited]).rows)


def test_new_proposals_clear_the_old_live_rate(tmp_path):
    at = _app(tmp_path, [_proposal(1, "Built pipelines.", "Built pipelines.")])
    next(b for b in at.button if b.label == "🔄 Recalculate match rate").click().run()
    assert "live_match" in at.session_state
    next(b for b in at.sidebar.button if b.label == "🔄 Start Over").click().run()
    assert "live_match" not in at.session_state
