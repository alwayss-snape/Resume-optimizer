import html
import os
from typing import Iterable

from app.domain.resume import Resume
from app.domain.resume_document import ResumeDocument
from app.analysis.cv_mode import experience_heading, is_publications
from app.rendering.layout import (SECTION_TITLES, page_spec, contact_parts, date_range, display_skills, format_date_text,
                                  ordered_sections, other_section, skill_label)

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

    _date_style = "month"  # the presentation's, set by render() (P10.3)
    _academic = False  # Academic CV (P10.6)

    def _dates(self, role) -> str:
        return date_range(role.start_date, role.end_date, self._date_style) if role else ""

    def _experience_entry(self, item) -> str:
        roles = item.all_roles()
        first = roles[0] if roles else None
        # No title found in the file: the company takes the heading rather
        # than printing a placeholder.
        heading = (first.title if first and first.title else "") or item.company
        parts = [
            "<article class='entry'><div class='entry-head'>"
            f"<h3>{html.escape(heading)}</h3>"
            f"<span class='dates'>{html.escape(self._dates(first))}</span></div>",
            self._meta_line(item.company if heading != item.company else "", item.location),
            *(f"<p class='meta'>{html.escape(d)}</p>" for d in item.details),
        ]
        for role in roles[1:]:
            parts.append(
                "<div class='entry-head role'>"
                f"<span>{html.escape(role.title)}</span>"
                f"<span class='dates'>{html.escape(self._dates(role))}</span></div>"
            )
        for group, bullets in item.bullet_groups():
            if group:
                parts.append(f"<p class='group'>{html.escape(group)}</p>")
            parts.append(f"<ul>{self._items(bullet.text for bullet in bullets)}</ul>")
        parts.append("</article>")
        return "".join(parts)

    def _section(self, name: str, body: str, title: str = "") -> str:
        return f"<section><h2>{html.escape(title) if title else SECTION_TITLES[name]}</h2>{body}</section>"

    def _other(self, section) -> str:
        """A kept section (P8.3), each line as written."""
        if not section or not section.lines:
            return ""
        parts, bullets = [], []
        tag = "ol" if self._academic and is_publications(section.heading) else "ul"  # P10.6
        for line in section.lines:
            if line.bullet:
                bullets.append(line.text)
                continue
            if bullets:
                parts.append(f"<{tag}>{self._items(bullets)}</{tag}>")
                bullets = []
            parts.append(f"<p>{html.escape(line.text)}</p>")
        if bullets:
            parts.append(f"<{tag}>{self._items(bullets)}</{tag}>")
        return self._section("other", "".join(parts), title=section.heading)

    def render(self, document: ResumeDocument) -> str:
        """Same sections, order and headings as the DOCX template (P2.1)."""
        resume: Resume = document.resume
        presentation = document.presentation
        page = page_spec(presentation)
        self._date_style = presentation.date_style
        self._academic = presentation.cv_mode == "academic"
        contact = " | ".join(html.escape(value) for value in contact_parts(resume.candidate))
        headline = (f'<p class="headline">{html.escape(resume.candidate.headline)}</p>'
                    if resume.candidate.headline else "")
        details = (f'<p class="contact">{" | ".join(html.escape(d) for d in resume.candidate.details)}</p>'
                   if resume.candidate.details else "")
        sections = []

        for section_name in ordered_sections(resume, presentation.section_order):
            if section_name.startswith("other:"):
                sections.append(self._other(other_section(resume, section_name)))
            elif section_name == "summary" and resume.summary:
                sections.append(self._section("summary", f"<p>{html.escape(resume.summary)}</p>"))
            elif section_name == "experience" and resume.experience:
                entries = "".join(self._experience_entry(item) for item in resume.experience)
                sections.append(self._section("experience", entries,
                                              experience_heading(resume) if self._academic else ""))
            elif section_name == "projects" and resume.projects:
                entries = "".join(
                    "<article class='entry'>"
                    f"<h3>{html.escape(project.name)}</h3>"
                    + (f"<p>{html.escape(project.description)}</p>" if project.description else "")
                    + f"<ul>{self._items(bullet.text for bullet in project.bullets)}</ul></article>"
                    for project in resume.projects
                )
                sections.append(self._section("projects", entries))
            elif section_name == "skills" and resume.skills:
                shown = display_skills(resume.skills)
                skills = "".join(
                    "<p>" + (f"<strong>{html.escape(label)}:</strong> " if (label := skill_label(category, shown)) else "")
                    + f"{html.escape(', '.join(values))}</p>"
                    for category, values in shown.items()
                )
                sections.append(self._section("skills", skills))
            elif section_name == "education" and resume.education:
                entries = "".join(
                    "<article class='entry'>"
                    "<div class='entry-head'>"
                    f"<h3>{html.escape(item.degree or item.institution)}</h3>"
                    f"<span class='dates'>{html.escape(format_date_text(item.dates, self._date_style))}</span>"
                    "</div>"
                    f"{self._meta_line(item.institution if item.degree else '', item.location)}"
                    + "".join(f"<p>{html.escape(d)}</p>" for d in item.details)
                    + "</article>"
                    for item in resume.education
                )
                sections.append(self._section("education", entries))
            elif section_name == "certifications" and resume.certifications:
                certs = [" — ".join(v for v in c.values() if v) for c in resume.certifications]
                sections.append(self._section("certifications", f"<ul>{self._items(certs)}</ul>"))
            elif section_name == "achievements" and resume.achievements:
                sections.append(self._section("achievements", f"<ul>{self._items(resume.achievements)}</ul>"))
            elif section_name == "interests" and resume.interests:
                sections.append(self._section("interests", f"<p>{html.escape(', '.join(resume.interests))}</p>"))

        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(resume.candidate.name)} — Resume</title>
<style>
@page {{ size: {page.css_size}; margin: {presentation.margin_vertical_in}in {presentation.margin_side_in}in; }}
* {{ box-sizing: border-box; }}
body {{ font-family: {html.escape(presentation.font_family)}, Arial, "Noto Sans CJK SC", "Arial Unicode MS", "PingFang SC", sans-serif; color: #111827; font-size: 10.5pt; line-height: 1.4; max-width: {page.width_mm:g}mm; margin: 0 auto; padding: 24px 16px; background: #fff; }}
header {{ border-bottom: 1px solid {html.escape(presentation.accent_color)}; padding-bottom: 8px; margin-bottom: 12px; }}
h1 {{ margin: 0; font-size: 22pt; font-weight: 700; letter-spacing: .2px; color: {html.escape(presentation.accent_color)}; }}
.contact {{ margin: 5px 0 0; color: #4b5563; font-size: 10pt; }}
.headline {{ margin: 2px 0 0; font-size: 12pt; color: {html.escape(presentation.accent_color)}; }}
h2 {{ color: {html.escape(presentation.accent_color)}; font-size: 11.5pt; font-weight: 700; letter-spacing: .8px; text-transform: uppercase; border-bottom: 1px solid {html.escape(presentation.accent_color)}; padding-bottom: 3px; margin: 14px 0 6px; }}
h3 {{ font-size: 11pt; font-weight: 700; margin: 0; }}
.entry-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin: 10px 0 0; }}
.dates {{ color: #4b5563; font-weight: 400; font-size: 9.5pt; white-space: nowrap; }}
.meta {{ margin: 1px 0 4px; color: #4b5563; font-style: italic; font-size: 9.5pt; }}
p {{ margin: 4px 0; }}
ul {{ margin: 4px 0 8px; padding-left: 18px; }}
li {{ margin: 2px 0; }}
.entry {{ break-inside: avoid; margin-bottom: 4px; }}
.entry-head.role {{ margin: 2px 0 0; }}
.group {{ font-weight: 700; margin: 6px 0 0; }}
strong {{ font-weight: 700; }}
</style></head><body>
<header><h1>{html.escape(resume.candidate.name)}</h1>{headline}<p class="contact">{contact}</p>{details}</header>
{''.join(sections)}
</body></html>"""

    def write_html(self, document: ResumeDocument, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as output:
            output.write(self.render(document))
        return output_path
