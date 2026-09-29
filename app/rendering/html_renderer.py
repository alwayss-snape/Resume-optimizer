import html
import os
from typing import Iterable

from app.domain.resume import Resume
from app.domain.resume_document import ResumeDocument

class HtmlResumeRenderer:
    """Render an ATS-safe, printable résumé from the canonical document."""

    def _items(self, values: Iterable[str]) -> str:
        return "".join(f"<li>{html.escape(value)}</li>" for value in values if value)

    def _meta_line(self, *parts: str) -> str:
        """A de-emphasized 'Company · Location' style line under a bolded
        title/degree — joined the same way as the DOCX renderer's meta
        line, so the browser preview and the downloaded PDF read as one
        design rather than two different products."""
        joined = " · ".join(html.escape(p) for p in parts if p)
        return f'<p class="meta">{joined}</p>' if joined else ""

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
                    "<div class='entry-head'>"
                    f"<h3>{html.escape(item.title)}</h3>"
                    f"<span class='dates'>{html.escape(' – '.join(v for v in (item.start_date, item.end_date) if v))}</span>"
                    "</div>"
                    f"{self._meta_line(item.company, item.location)}"
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
                    "<article class='entry'>"
                    "<div class='entry-head'>"
                    f"<h3>{html.escape(item.degree)}</h3>"
                    f"<span class='dates'>{html.escape(item.dates or '')}</span>"
                    "</div>"
                    f"{self._meta_line(item.institution, item.location)}"
                    "</article>"
                    for item in resume.education
                )
                sections.append(f"<section><h2>Education</h2>{entries}</section>")
            elif section_name == "certifications" and resume.certifications:
                cert_names = [c.get("name", "") if isinstance(c, dict) else str(c) for c in resume.certifications]
                sections.append(
                    "<section><h2>Certifications</h2><p>"
                    + html.escape(" · ".join(n for n in cert_names if n))
                    + "</p></section>"
                )
        if resume.achievements:
            sections.append(
                f"<section><h2>Achievements</h2><ul>{self._items(resume.achievements)}</ul></section>"
            )
        if resume.interests:
            sections.append(f"<section><h2>Interests</h2><p>{html.escape(', '.join(resume.interests))}</p></section>")

        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(resume.candidate.name)} — Resume</title>
<style>
@page {{ size: A4; margin: 16mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: {html.escape(presentation.font_family)}, Arial, sans-serif; color: #111827; font-size: 10.5pt; line-height: 1.4; max-width: 780px; margin: 0 auto; padding: 24px 16px; background: #fff; }}
header {{ border-bottom: 2px solid {html.escape(presentation.accent_color)}; padding-bottom: 10px; margin-bottom: 14px; }}
h1 {{ margin: 0; font-size: 25pt; font-weight: 700; letter-spacing: .2px; color: {html.escape(presentation.accent_color)}; }}
.contact {{ margin: 5px 0 0; color: #4b5563; font-size: 10pt; }}
h2 {{ color: {html.escape(presentation.accent_color)}; font-size: 12pt; font-weight: 700; letter-spacing: .8px; text-transform: uppercase; border-bottom: 1px solid #d1d5db; padding-bottom: 4px; margin: 18px 0 8px; }}
h3 {{ font-size: 11pt; font-weight: 700; margin: 0; }}
.entry-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin: 10px 0 0; }}
.dates {{ color: #4b5563; font-weight: 400; font-size: 9.5pt; white-space: nowrap; }}
.meta {{ margin: 1px 0 4px; color: #4b5563; font-style: italic; font-size: 9.5pt; }}
p {{ margin: 4px 0; }}
ul {{ margin: 4px 0 8px; padding-left: 18px; }}
li {{ margin: 2px 0; }}
.entry {{ break-inside: avoid; margin-bottom: 4px; }}
strong {{ font-weight: 700; }}
</style></head><body>
<header><h1>{html.escape(resume.candidate.name)}</h1><p class="contact">{contact}</p></header>
{''.join(sections)}
</body></html>"""

    def write_html(self, document: ResumeDocument, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as output:
            output.write(self.render(document))
        return output_path
