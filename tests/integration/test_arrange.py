"""P8.13–P8.16: arrange and edit after tailoring, with no LLM call."""
from app.eval.harness import OfflineLLM
from app.services.arrange import Layout, apply_layout
from app.services.tailor import TailorService
from app.validation.coverage import docx_text

REPLICA = "tests/fixtures/resumes/replica_layout.pdf"
JD = "tests/fixtures/jds/replica_layout_jd.txt"


def _tailored(tmp_path):
    service = TailorService(llm_client=OfflineLLM())
    with open(JD, encoding="utf-8") as f:
        jd = f.read()
    result = service.tailor_resume(REPLICA, jd, str(tmp_path), preapproved_proposals=[],
                                   parsed=service.parse_resume(REPLICA), remember_answers=False)
    return service, result, result["arrange"]


def test_layout_moves_hides_removes_and_edits_without_crossing_jobs(tmp_path):
    service, _result, state = _tailored(tmp_path)
    full = state["full_doc"].resume
    job0, job1 = full.experience[0], full.experience[1]
    layout = state["default_layout"].model_copy(deep=True)
    layout.section_order = ["education", *[k for k in layout.section_order if k != "education"]]
    layout.hidden_sections = ["interests"]
    first, *rest = layout.bullet_order[job0.id]
    layout.bullet_order[job0.id] = [*rest, first]
    layout.bullet_order[job1.id] = [first, *layout.bullet_order[job1.id]]  # another job's bullet: ignored
    layout.removed_bullets = [job1.bullets[-1].id]
    layout.edits = {job0.bullets[1].id: "Rewrote it in my own words for 99 stores."}
    layout.trim = False

    arranged = apply_layout(full, layout)
    assert [b.id for b in arranged.experience[0].bullets][-1] == first
    assert first not in [b.id for b in arranged.experience[1].bullets]
    assert job1.bullets[-1].id not in [b.id for b in arranged.experience[1].bullets]
    assert arranged.interests == []

    out = service.arrange(state, layout, str(tmp_path))
    text = docx_text(out["docx"])
    assert text.index("EDUCATION") < text.index("WORK EXPERIENCE")
    assert "Rewrote it in my own words for 99 stores." in text
    assert out["coverage"]["lost"] == []  # the user's removals and hidden sections aren't losses
    assert any("99" in w and "isn't elsewhere" in w for w in out["warnings"])
    assert out["success"] is True


def test_reordering_jobs_out_of_date_order_is_pointed_out(tmp_path):
    service, _result, state = _tailored(tmp_path)
    layout = state["default_layout"].model_copy(deep=True)
    layout.entry_order["experience"] = list(reversed(layout.entry_order["experience"]))
    out = service.arrange(state, layout, str(tmp_path))
    assert any("newest first" in w for w in out["warnings"])


def test_no_rewrites_accepted_means_no_silent_reorder(tmp_path):
    """P8.14: the file's order stays when nothing was accepted."""
    _service, _result, state = _tailored(tmp_path)
    full, original = state["full_doc"].resume, state["original"]
    assert [[b.id for b in e.bullets] for e in full.experience] == \
           [[b.id for b in e.bullets] for e in original.experience]
