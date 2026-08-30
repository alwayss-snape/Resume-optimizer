import html
import os
from typing import Iterable

from app.domain.resume import Resume
from app.domain.resume_document import ResumeDocument

class HtmlResumeRenderer:
    """Render an ATS-safe, printable résumé from the canonical document."""

    def _items(self, values: Iterable[str]) -> str:
        return "".join(f"<li>{html.escape(value)}</li>" for value in values if value)

    def render(self, document: ResumeDocument) -> str:
        resume: Resume = document.resume
        presentation = document.presentation
        contact = " · ".join(html.escape(value) for value in (
            resume.candidate.email, resume.candidate.phone, resume.candidate.location, *resume.candidate.links,
        ) if value)
        sections = []

        if resume.summary:
            sections.append(f"<section><h2>Professional Summary</h2><p>{html.escape(resume.summary)}</p></section>")

        for section_name in presentation.section_order:
            if section_name == "experience" and resume.experience:
                entries = "".join(
                    "<article class='entry'>"
                    f"<h3>{html.escape(item.title)} <span>— {html.escape(item.company)}</span></h3>"
                    f"<p class='dates'>{html.escape(' — '.join(v for v in (item.start_date, item.end_date) if v))}</p>"
                    f"<ul>{self._items(bullet.text for bullet in item.bullets)}</ul></article>"
                    for item in resume.experience
                )
                sections.append(f"<section><h2>Experience</h2>{entries}</section>")
            elif section_name == "projects" and resume.projects:
                entries = "".join(
                    "<article class='entry'>"
                    f"<h3>{html.escape(project.name)}</h3>"
                    f"<p>{html.escape(project.description)}</p>"
                    f"<ul>{self._items(bullet.text for bullet in project.bullets)}</ul></article>"
                    for project in resume.projects
                )
                sections.append(f"<section><h2>Projects</h2>{entries}</section>")
            elif section_name == "skills" and resume.skills:
                skills = "".join(
                    f"<p><strong>{html.escape(category)}:</strong> {html.escape(', '.join(values))}</p>"
                    for category, values in resume.skills.items()
                )
                sections.append(f"<section><h2>Skills</h2>{skills}</section>")
            elif section_name == "education" and resume.education:
                entries = "".join(
                    f"<article class='entry'><h3>{html.escape(item.degree)}</h3>"
                    f"<p>{html.escape(item.institution)} {html.escape(item.dates or '')}</p></article>"
                    for item in resume.education
                )
                sections.append(f"<section><h2>Education</h2>{entries}</section>")

        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(resume.candidate.name)} — Resume</title>
<style>
@page {{ size: A4; margin: 16mm; }}
body {{ font-family: {html.escape(presentation.font_family)}, Arial, sans-serif; color: #111827; font-size: 10.5pt; line-height: 1.35; max-width: 780px; margin: 0 auto; }}
header {{ border-bottom: 2px solid {html.escape(presentation.accent_color)}; padding-bottom: 10px; margin-bottom: 14px; }}
h1 {{ margin: 0; font-size: 24pt; letter-spacing: .2px; }} .contact {{ margin: 4px 0 0; color: #4b5563; }}
h2 {{ color: {html.escape(presentation.accent_color)}; font-size: 12pt; letter-spacing: .8px; text-transform: uppercase; border-bottom: 1px solid #d1d5db; padding-bottom: 3px; margin: 15px 0 7px; }}
h3 {{ font-size: 11pt; margin: 8px 0 1px; }} h3 span, .dates {{ color: #4b5563; font-weight: normal; }} .dates {{ margin: 0; font-size: 9.5pt; }}
p {{ margin: 4px 0; }} ul {{ margin: 4px 0 7px; padding-left: 18px; }} li {{ margin: 2px 0; }} .entry {{ break-inside: avoid; }}
</style></head><body>
<header><h1>{html.escape(resume.candidate.name)}</h1><p class="contact">{contact}</p></header>
{''.join(sections)}
</body></html>"""

    def write_html(self, document: ResumeDocument, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as output:
            output.write(self.render(document))
        return output_path
