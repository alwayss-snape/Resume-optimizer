"""P3.4: the proposal review screen (diff, badges, breakdown, gap table,
accept/reject all, recalculated match rate)."""

from app.analysis.change_proposal import ChangeProposal
from app.domain.job import JobDescription, Requirement
from app.domain.report import KeywordMatchReport, KeywordRow
from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument
from app.rendering.review_view import diff_spans, gap_table, proposal_state, score_breakdown
from app.services.tailor import TailorService


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


def test_preview_skips_rejected_unless_edited():
    parsed, service = _parsed(), TailorService(llm_client=None)
    rejected = {"kind": "bullet", "target_semantic_id": "b1", "proposed_text": "Built Kafka pipelines.",
                "validation": "REJECT"}
    assert not any(r.keyword == "Kafka" and r.found
                   for r in service.preview_keyword_match(parsed, _job(), [rejected]).rows)
    edited = {**rejected, "user_edited": True}
    assert any(r.keyword == "Kafka" and r.found
               for r in service.preview_keyword_match(parsed, _job(), [edited]).rows)




def _marked(spans, key):
    return [s["text"] for s in spans if s.get(key)]


def test_diff_marks_removed_added_and_keywords():
    """The review diff as data (P5.1): text unescaped (the client escapes it)."""
    left, right = diff_spans("Built <fast> pipelines in python", "Built Spark pipelines in Python on AWS",
                             keywords=["Spark", "Python", "AWS"])
    assert _marked(left, "changed") == ["<fast>"]
    assert _marked(right, "changed") == ["Spark", "on", "AWS"]
    assert _marked(right, "keyword") == ["Spark", "Python", "AWS"]
    assert _marked(left, "keyword") == ["python"]  # a keyword on the original too


def test_multi_word_and_dotnet_keywords_are_marked_whole():
    _, right = diff_spans("x", "Built feature stores for ML.", keywords=["feature stores"])
    assert _marked(right, "keyword") == ["feature", "stores"]
    _, right = diff_spans("", "Built .NET services.", keywords=[".NET"])
    assert _marked(right, "keyword") == [".NET"]


def test_diff_keeps_line_breaks_and_markdown_characters():
    _, right = diff_spans("Cut cost from $2M", "Cut *cost* from $2M_x\nTools: Git")
    assert {"text": "\n"} in right
    assert any(s["text"] == "*cost*" for s in right) and any(s["text"] == "$2M_x" for s in right)


def test_proposal_states():
    assert proposal_state("llm_error", "REJECT", True) == "failed"  # a failed call wins
    assert proposal_state(None, "REJECT", True) == "dropped"
    assert proposal_state(None, "NEEDS_CONFIRM", True) == "check"
    assert proposal_state(None, "PASS", False) == "unchanged"
    assert proposal_state(None, "PASS", True) == "pass"
