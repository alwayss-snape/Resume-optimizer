from app.domain.resume import Candidate, Experience, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument
from app.rendering.html_renderer import HtmlResumeRenderer

def test_html_renderer_outputs_ats_sections_and_escapes_content(tmp_path):
    document = ResumeDocument(resume=Resume(
        candidate=Candidate(name="Avery <Lee>", email="avery@example.com"),
        summary="Builds reliable systems.",
        experience=[Experience(
            id="exp_1", company="Acme", title="Engineer",
            bullets=[ResumeBullet(id="b1", text="Improved parsing <safely>.")],
        )],
        skills={"Languages": ["Python", "SQL"]},
    ))

    output = HtmlResumeRenderer().write_html(document, str(tmp_path / "resume.html"))
    html = open(output, encoding="utf-8").read()

    assert "<h2>Experience</h2>" in html
    assert "<h2>Skills</h2>" in html
    assert "Avery &lt;Lee&gt;" in html
    assert "parsing &lt;safely&gt;" in html
    assert "@page" in html
