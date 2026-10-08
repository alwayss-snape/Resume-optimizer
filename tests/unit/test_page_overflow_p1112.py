"""P11.12: kept projects that don't fit the page target are a choice, not a silent second page."""
from unittest.mock import MagicMock

from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument
from app.rendering.page_fit import MIN_BULLETS_PER_KEPT_PROJECT, PageFitter
from app.services.tailor import TailorService

from tests.unit.test_project_select_p1013 import BANK, JD, REPLICA


def _job(exp_id, groups):
    bullets = [ResumeBullet(id=f"{exp_id}_{g[:3]}{n}", text=f"{g} line {n} " + "word " * 20, group=g)
               for g, count in groups for n in range(count)]
    return Experience(id=exp_id, company="Northwind", title="Engineer", start_date="Jan 2020", end_date="Present",
                      bullets=bullets)


def _doc(resume):
    return ResumeDocument(resume=resume)


def test_kept_projects_are_cut_to_their_minimum_then_offered_as_a_choice(tmp_path):
    resume = Resume(candidate=Candidate(name="A B"), experience=[_job("now", [("Alpha", 4), ("Beta", 4)])])
    fitter = PageFitter(lambda d, p, o: "x.pdf", measure=lambda _: (2, 200.0))  # never fits
    fit = fitter.fit(_doc(resume), str(tmp_path / "r.docx"), str(tmp_path), 1, relevance={},
                     kept_projects={"now::Alpha", "now::Beta"})
    groups = [b.group for b in resume.experience[0].bullets]
    assert groups.count("Alpha") == groups.count("Beta") == MIN_BULLETS_PER_KEPT_PROJECT  # trimmed first
    assert [p["name"] for p in fit.over_with_kept] == ["Alpha", "Beta"]
    assert any("choose a longer page target, or leave a project out" in n for n in fit.notes)


def test_without_kept_projects_the_old_note_stands(tmp_path):
    resume = Resume(candidate=Candidate(name="A B"), experience=[_job("now", [("Alpha", 4)])])
    fit = PageFitter(lambda d, p, o: "x.pdf", measure=lambda _: (2, 200.0)).fit(
        _doc(resume), str(tmp_path / "r.docx"), str(tmp_path), 1, relevance={})
    assert fit.over_with_kept == []
    assert any(n.startswith("Still 2 pages after trimming") for n in fit.notes)


def test_dont_trim_or_a_fit_offers_no_choice(tmp_path):
    resume = Resume(candidate=Candidate(name="A B"), experience=[_job("now", [("Alpha", 4)])])
    kept = {"now::Alpha"}
    untrimmed = PageFitter(lambda d, p, o: "x.pdf", measure=lambda _: (2, 200.0)).fit(
        _doc(resume), str(tmp_path / "r.docx"), str(tmp_path), 1, relevance={}, trim=False, kept_projects=kept)
    fits = PageFitter(lambda d, p, o: "x.pdf", measure=lambda _: (1, 200.0)).fit(
        _doc(resume), str(tmp_path / "r.docx"), str(tmp_path), 1, relevance={}, kept_projects=kept)
    assert untrimmed.over_with_kept == [] and fits.over_with_kept == []


def test_results_offer_a_longer_target_or_leaving_a_project_out_and_lose_nothing(tmp_path, monkeypatch):
    """End to end with a fake page count: 2 pages while the heavy project is in."""
    service = TailorService(llm_client=None)
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    real_render = service._render_template
    heavy = {"name": None}  # None: any project makes it 2 pages
    seen = {}

    def render(doc, docx_path, out_dir):
        real_render(doc, docx_path, out_dir)
        seen["groups"] = {b.group for e in doc.resume.experience for b in e.bullets if b.group}
        return str(tmp_path / "fake.pdf")

    def measure(_pdf):
        over = seen["groups"] if heavy["name"] is None else seen["groups"] & {heavy["name"]}
        return (2 if over else 1), 300.0

    monkeypatch.setattr(service, "_render_template", render)
    monkeypatch.setattr("app.services.tailor.PageFitter", lambda r: PageFitter(r, measure=measure))
    service.qa_validator.validate_pdf = MagicMock(return_value=[])
    service.qa_validator.round_trip = MagicMock(return_value=[])

    parsed, _ = service.apply_parse_corrections(service.parse_resume(REPLICA), {"added_jobs": [BANK]})
    result = service.tailor_resume(REPLICA, JD, str(tmp_path), preapproved_proposals=[], parsed=parsed,
                                   remember_answers=False)
    overflow = result["page_overflow"]
    assert overflow and overflow["pages"] == 2 and overflow["target"] == 1
    state = result["arrange"]
    full_ids = {b.id: b.group for e in state["full_doc"].resume.experience for b in e.bullets}
    first = overflow["projects"][0]
    assert first["bullet_ids"] and all(full_ids[i] == first["name"] for i in first["bullet_ids"])

    heavy["name"] = first["name"]
    layout = state["default_layout"]
    out = service.arrange(state, layout.model_copy(update={
        "removed_bullets": [*layout.removed_bullets, *first["bullet_ids"]]}), str(tmp_path / "a1"))
    assert out["page_overflow"] is None and out["coverage"]["lost"] == []

    two = service.arrange(state, layout.model_copy(update={"page_target": 2}), str(tmp_path / "a2"))
    assert two["page_overflow"] is None and two["coverage"]["lost"] == []


def test_kept_projects_are_cut_even_when_the_renders_run_out_reviewer_p1112(tmp_path):
    """Review finding: the loop stopped at MAX_RENDERS with one kept project still whole."""
    resume = Resume(candidate=Candidate(name="A B"), experience=[
        _job("now", [("Alpha", 8), ("Beta", 8), ("Gamma", 8)])])
    fit = PageFitter(lambda d, p, o: "x.pdf", measure=lambda _: (2, 200.0)).fit(
        _doc(resume), str(tmp_path / "r.docx"), str(tmp_path), 1, relevance={},
        kept_projects={"now::Alpha", "now::Beta", "now::Gamma"})
    groups = [b.group for b in resume.experience[0].bullets]
    assert all(groups.count(g) == MIN_BULLETS_PER_KEPT_PROJECT for g in ("Alpha", "Beta", "Gamma"))
    assert len(fit.over_with_kept) == 3
