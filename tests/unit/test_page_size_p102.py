"""P10.2: one PageSpec decides the paper for the DOCX template, the HTML
preview and page-fit. A4 stays the default; Letter is the same layout on
a US page."""
import docx
from docx.shared import Mm

from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument, ResumePresentation
from app.rendering.html_renderer import HtmlResumeRenderer
from app.rendering.layout import PAGE_SPECS, page_spec
from app.rendering.page_fit import PAGE_BODY_PT, PageFitter, bullet_height
from app.rendering.template_renderer import TemplateRenderer


def _doc(page_size="A4", bullets=6):
    exp = Experience(id="e1", company="Acme", title="Engineer", bullets=[
        ResumeBullet(id=f"b{i}", text="Led a team that shipped a billing service used by 40 clients " * 2)
        for i in range(bullets)])
    return ResumeDocument(resume=Resume(candidate=Candidate(name="A Person"), experience=[exp]),
                          presentation=ResumePresentation(page_size=page_size))


def test_a4_is_the_default_and_unchanged():
    assert ResumePresentation().page_size == "A4"
    a4 = page_spec()
    assert (a4.width_mm, a4.height_mm, a4.bullet_chars_per_line) == (210.0, 297.0, 92)
    assert abs(a4.height_pt - 841.89) < 0.01
    assert PAGE_BODY_PT == a4.body_pt(0.6)


def test_the_docx_page_follows_the_presentation(tmp_path):
    for size, (w, h) in {"A4": (210, 297), "Letter": (215.9, 279.4)}.items():
        path = str(tmp_path / f"{size}.docx")
        TemplateRenderer().render_ats_default(_doc(size), path)
        section = docx.Document(path).sections[0]
        # Word stores twips, so allow the rounding.
        assert abs(section.page_width - Mm(w)) < Mm(0.1) and abs(section.page_height - Mm(h)) < Mm(0.1)


def test_the_html_preview_uses_the_same_page():
    a4 = HtmlResumeRenderer().render(_doc("A4"))
    letter = HtmlResumeRenderer().render(_doc("Letter"))
    assert "size: A4;" in a4 and "max-width: 210mm;" in a4
    assert "size: letter;" in letter and "max-width: 215.9mm;" in letter


def test_page_fit_measures_overflow_on_the_letter_page():
    """A Letter page holds less height, so the same overflow on page 2 asks
    for more trimming; and a Letter line holds more characters."""
    letter = PAGE_SPECS["Letter"]
    assert letter.body_pt(0.6) < PAGE_BODY_PT
    text = "x" * 94
    assert bullet_height(text, letter.bullet_chars_per_line) < bullet_height(text)

    asked = []
    for size in ("A4", "Letter"):
        fitter = PageFitter(lambda *_: "fake.pdf", lambda _pdf: (3, 100.0))
        real_trim = fitter._trim_bullets
        fitter._trim_bullets = lambda resume, need, *args, real=real_trim: (asked.append(need), real(resume, need, *args))[1]
        fitter.fit(_doc(size, 8), "x.docx", "out", 1, {})
    # Three pages for a one-page target: one whole page plus 100 pt over.
    assert asked[0] == PAGE_BODY_PT + 100.0
    assert asked[1] == letter.body_pt(0.6) + 100.0
