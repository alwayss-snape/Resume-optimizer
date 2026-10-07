"""P10.5: the CV type (standard, Academic CV, US Federal) is suggested from
the resume and the JD with its evidence, confirmed by the user, and the
academic and federal types have no page cap."""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.analysis.cv_mode import apply_cv_mode, suggest_cv_mode
from app.domain.resume import Candidate, Experience, OtherSection, Resume, ResumeBullet, Role, SectionLine
from app.domain.resume_document import ResumeDocument, ResumePresentation
from app.services.tailor import TailorService


def _academic():
    return Resume(candidate=Candidate(name="Dr. A", details=["ORCID 0000-0002-1234-5678"]),
                  experience=[Experience(id="e1", company="State University", title="Assistant Professor of Biology",
                                         bullets=[ResumeBullet(id="b1", text="Teach microbiology.")])],
                  other_sections=[OtherSection(id="o1", heading="Publications", lines=[SectionLine(text="1. A paper.")])])


def _federal():
    return Resume(candidate=Candidate(name="A", details=["U.S. Citizen | Veterans' Preference: None"]),
                  experience=[Experience(id="e1", company="USDA", title="Analyst (GS-0343-12)",
                                         details=["40 hours per week | Supervisor: J Doe"])])


def test_academic_from_two_resume_signals_with_evidence():
    guess = suggest_cv_mode(_academic(), "Senior Scientist in industry R&D.")
    assert guess.mode == "academic" and guess.label == "Academic CV"
    assert guess.evidence == ["a “Professor” role", "sections “Publications”", "an ORCID iD"]


def test_one_academic_signal_needs_an_academic_job():
    resume = _academic()
    resume.candidate.details, resume.other_sections = [], []
    assert suggest_cv_mode(resume, "Senior Scientist in industry R&D.").mode == "standard"
    guess = suggest_cv_mode(resume, "Tenure-track faculty position in biology.")
    assert guess.mode == "academic" and guess.evidence[0] == "the job says “Tenure-track”"


def test_federal_from_the_jd_or_the_resume():
    assert suggest_cv_mode(Resume(candidate=Candidate(name="A")), "Program Analyst, GS-0343-13").mode == "federal"
    guess = suggest_cv_mode(_federal(), "Program analyst for a consulting firm.")
    assert guess.mode == "federal" and "“40 hours per week”" in guess.evidence


def test_an_ordinary_resume_stays_standard():
    resume = Resume(candidate=Candidate(name="A"), experience=[Experience(
        id="e1", company="Acme", title="Engineer", bullets=[ResumeBullet(id="b", text="Built APIs; taught interns.")])])
    assert suggest_cv_mode(resume, "Senior engineer, Austin, TX. Teaching others is a plus.").mode == "standard"


def test_federal_is_us_letter_with_numeric_dates():
    p = apply_cv_mode(ResumePresentation(), "federal")
    assert (p.cv_mode, p.page_size, p.date_style) == ("federal", "Letter", "numeric")
    p = apply_cv_mode(ResumePresentation(), "academic")
    assert (p.cv_mode, p.page_size, p.date_style) == ("academic", "A4", "month")
    assert apply_cv_mode(ResumePresentation(), "bogus").cv_mode == "standard"


def test_no_page_cap_for_academic_and_federal(tmp_path, monkeypatch):
    """Page-fit renders once without trimming and reports no target."""
    from app.rendering import page_fit
    calls = []
    real_fit = page_fit.PageFitter.fit

    def spy(self, document, *args, **kw):
        calls.append((document.presentation.cv_mode, kw.get("trim", True)))
        return real_fit(self, document, *args, **kw)
    monkeypatch.setattr(page_fit.PageFitter, "fit", spy)
    service = TailorService(llm_client=None, keep_run=False)
    service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
    jd = "Program Analyst, GS-0343-13. Program evaluation, budget execution, briefings."
    out = service.tailor_resume("tests/fixtures/resumes/sample.docx", jd, str(tmp_path / "a"))
    assert calls[-1] == ("federal", False) and out["target_pages"] is None
    out = service.tailor_resume("tests/fixtures/resumes/sample.docx", jd, str(tmp_path / "b"), cv_mode="standard")
    assert calls[-1] == ("standard", True) and out["target_pages"] in (1, 2)


def test_the_api_suggests_the_cv_type_and_arrange_switches_it(tmp_path):
    from app.api.main import create_app
    from app.services.run_manager import RunManager
    from tests.unit.test_api import SAMPLE_DOCX, _events, _upload

    def make_service(model=None):
        service = TailorService(llm_client=None)
        service.run_manager = RunManager(base_runs_dir=str(tmp_path / "runs"))
        service.pdf_converter.convert_docx_to_pdf = MagicMock(return_value=None)
        return service

    jd = ("Management and Program Analyst, GS-0343-13. Program evaluation, budget formulation and execution, "
          "preparing briefings for senior executives, Python and SQL data analysis, supervising staff.")
    with TestClient(create_app(make_service=make_service, serve_web=False)) as client:
        assert client.post("/api/parse", files=_upload(SAMPLE_DOCX), data={"jd_text": jd}).status_code == 200
        drafted = _events(client.post("/api/proposals", json={}))[-1][1]
        assert drafted["cv_mode"] == {"mode": "federal", "label": "US Federal (USAJOBS)",
                                      "evidence": ["the job says “GS-0343-13”"]}
        assert client.post("/api/tailor", json={"cv_mode": "poster"}).status_code == 422
        final = _events(client.post("/api/tailor", json={"cv_mode": "standard"}))[-1][1]
        assert final["cv_mode"] == {"mode": "standard", "label": "Standard resume", "evidence": []}
        assert final["target_pages"] in (1, 2)
        layout = final["arrangement"]["layout"]
        assert layout["cv_mode"] == "standard"
        out = client.post("/api/arrange", json={"layout": {**layout, "cv_mode": "federal"}}).json()
        assert out["cv_mode"]["mode"] == "federal" and out["target_pages"] is None
        assert client.post("/api/arrange", json={"layout": {**layout, "cv_mode": "poster"}}).status_code == 422
