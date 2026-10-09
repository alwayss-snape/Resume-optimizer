"""P11.16: a LinkedIn-style degree ("Bachelor of Engineering - BE, Computer Science") reads back as one degree."""
import pytest

from app.services.tailor import TailorService

LINKEDIN = "tests/fixtures/resumes/linkedin_export.pdf"


@pytest.mark.parametrize("style", ["standard", "classic"])
def test_the_linkedin_export_reads_back_clean_in_both_templates(tmp_path, style):
    service = TailorService(llm_client=None)
    _raw, doc, _ev = service.parse_resume(LINKEDIN)
    doc.presentation.style = style
    path = str(tmp_path / f"{style}.docx")
    service.template_renderer.render_ats_default(doc, path)
    assert service.qa_validator.round_trip(path, doc.resume) == []
    _raw2, back, _ = service.parse_resume(path)
    assert [(e.degree, e.institution) for e in back.resume.education] == [
        (e.degree, e.institution) for e in doc.resume.education]


def test_a_degree_dash_institution_line_still_splits(tmp_path):
    text = ("Jordan Avery\njordan@example.com\n\nEXPERIENCE\nNorthwind\tJan 2020 – Present\nAnalyst\n"
            "- Built weekly sales reports.\n\nEDUCATION\n"
            "B.Tech - IIT Bombay\t2012 – 2016\n"
            "Bachelor of Science - BS, Statistics\t2008 – 2011\nLakeside College\n")
    path = tmp_path / "r.txt"
    path.write_text(text, encoding="utf-8")
    _raw, doc, _ev = TailorService(llm_client=None).parse_resume(str(path))
    assert [(e.degree, e.institution) for e in doc.resume.education] == [
        ("B.Tech", "IIT Bombay"), ("Bachelor of Science - BS, Statistics", "Lakeside College")]
