import os

import docx
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from typing import Any

from app.domain.resume_document import ResumePresentation
from app.rendering.layout import (SECTION_TITLES, fallback_font, contact_parts, date_range, display_skills, format_date_text,
                                  ordered_sections, other_section)


# Shared visual language with HtmlResumeRenderer's default accent (#1F4E79)
# so the DOCX/PDF download and the in-app HTML preview don't look like two
# different products.
ACCENT_COLOR = RGBColor(0x1F, 0x4E, 0x79)
META_COLOR = RGBColor(0x4B, 0x55, 0x63)  # dates/company/location — de-emphasized
BODY_COLOR = RGBColor(0x11, 0x18, 0x27)


class TemplateRenderer:
    """Standard single-column, ATS-safe DOCX renderer with support for ResumeDocument."""

    _gap = 1.0  # vertical spacing factor; 0.5 in compact mode

    def render_ats_default(self, resume_or_doc: Any, output_path: str) -> str:
        """Render the ATS template (P2.1): A4, single column, Arial,
        standard headings in `presentation.section_order`. Accepts a Resume
        or a ResumeDocument."""
        if hasattr(resume_or_doc, "resume"):
            resume, presentation = resume_or_doc.resume, resume_or_doc.presentation
        else:
            resume, presentation = resume_or_doc, ResumePresentation()

        doc = docx.Document()
        # Compact spacing (page-fit, P2.4): vertical gaps are halved.
        self._gap = 0.5 if presentation.compact else 1.0
        self._set_document_defaults(doc, presentation)
        content_width = self._content_width(doc)
        self._add_header(doc, resume)

        sections = {
            "summary": self._add_summary,
            "experience": self._add_experience,
            "skills": self._add_skills,
            "education": self._add_education,
            "projects": self._add_projects,
            "certifications": self._add_certifications,
            "achievements": self._add_achievements,
            "interests": self._add_interests,
        }
        for name in ordered_sections(resume, presentation.section_order):
            if name in sections:
                sections[name](doc, resume, content_width)
            elif name.startswith("other:"):
                self._add_other(doc, other_section(resume, name))

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        return output_path

    # -- sections -----------------------------------------------------

    def _add_header(self, doc, resume) -> None:
        candidate = resume.candidate
        if candidate.name:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(candidate.name)
            run.bold = True
            run.font.size = Pt(22)
            run.font.color.rgb = ACCENT_COLOR
        if candidate.headline:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(candidate.headline)
            run.font.size = Pt(12)
            run.font.color.rgb = ACCENT_COLOR
        parts = contact_parts(candidate)
        if parts:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(" | ".join(parts))
            run.font.size = Pt(10)
            run.font.color.rgb = META_COLOR
            if not candidate.details:
                self._add_bottom_border(p, size=4)
        if candidate.details:  # kept as written: address, date of birth, clearance (P8.3)
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(" | ".join(candidate.details))
            run.font.size = Pt(9.5)
            run.font.color.rgb = META_COLOR
            self._add_bottom_border(p, size=4)

    def _add_summary(self, doc, resume, content_width) -> None:
        if resume.summary:
            self._add_section_heading(doc, SECTION_TITLES["summary"])
            p = doc.add_paragraph(resume.summary)
            p.paragraph_format.space_after = Pt(4)

    def _add_experience(self, doc, resume, content_width) -> None:
        if not resume.experience:
            return
        self._add_section_heading(doc, SECTION_TITLES["experience"])
        for i, exp in enumerate(resume.experience):
            roles = exp.all_roles()
            company = exp.company or ""
            first = roles[0] if roles else None
            # No title found in the file: the company takes the bold line
            # rather than printing a placeholder.
            heading = (first.title if first and first.title else "") or company
            self._add_title_dates_line(doc, heading, self._role_dates(first), content_width,
                                       space_before=0 if i == 0 else 6)
            meta = " · ".join(v for v in (company if heading != company else "", exp.location) if v)
            if meta:
                self._add_meta_line(doc, meta)
            for line in exp.details:  # "40 hours per week | Salary: ..." as written (P8.5)
                dp = doc.add_paragraph()
                dp.paragraph_format.space_after = Pt(2)
                drun = dp.add_run(line)
                drun.font.size = Pt(9.5)
                drun.font.color.rgb = META_COLOR
            # Earlier roles at the same company (promotions).
            for role in roles[1:]:
                self._add_title_dates_line(doc, role.title, self._role_dates(role), content_width, bold=False)
            for group, bullets in exp.bullet_groups():
                if group:
                    gp = doc.add_paragraph()
                    gp.paragraph_format.space_before = Pt(3 * self._gap)
                    gp.paragraph_format.space_after = Pt(1)
                    grun = gp.add_run(group)
                    grun.bold = True
                    grun.font.size = Pt(10.5)
                self._add_bullets(doc, (b.text for b in bullets))

    def _add_skills(self, doc, resume, content_width) -> None:
        skills = display_skills(resume.skills or {})
        if not skills:
            return
        self._add_section_heading(doc, SECTION_TITLES["skills"])
        for category, skill_list in skills.items():
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            p.add_run(f"{category}: ").bold = True
            p.add_run(", ".join(skill_list))

    def _add_education(self, doc, resume, content_width) -> None:
        if not resume.education:
            return
        self._add_section_heading(doc, SECTION_TITLES["education"])
        for i, education in enumerate(resume.education):
            self._add_title_dates_line(doc, education.degree or education.institution or "",
                                       format_date_text(education.dates), content_width,
                                       space_before=0 if i == 0 else 4)
            meta = " · ".join(v for v in (education.institution if education.degree else "", education.location) if v)
            if meta:
                self._add_meta_line(doc, meta)
            for line in education.details:
                dp = doc.add_paragraph(line)
                dp.paragraph_format.space_after = Pt(2)

    def _add_projects(self, doc, resume, content_width) -> None:
        if not resume.projects:
            return
        self._add_section_heading(doc, SECTION_TITLES["projects"])
        for i, project in enumerate(resume.projects):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0 if i == 0 else 4)
            p.paragraph_format.space_after = Pt(1)
            run = p.add_run(project.name)
            run.bold = True
            run.font.size = Pt(11)
            if project.description:
                doc.add_paragraph(project.description).paragraph_format.space_after = Pt(2)
            if project.technologies:
                tp = doc.add_paragraph()
                tp.paragraph_format.space_after = Pt(2)
                label_run = tp.add_run("Technologies: ")
                label_run.bold = True
                label_run.font.size = Pt(10)
                val_run = tp.add_run(", ".join(project.technologies))
                val_run.font.size = Pt(10)
            self._add_bullets(doc, (b.text for b in project.bullets))

    def _add_certifications(self, doc, resume, content_width) -> None:
        if not resume.certifications:
            return
        self._add_section_heading(doc, SECTION_TITLES["certifications"])
        self._add_bullets(doc, (" — ".join(v for v in c.values() if v) for c in resume.certifications))

    def _add_other(self, doc, section) -> None:
        """A kept section (P8.3): its own heading, each line as written."""
        if not section or not section.lines:
            return
        self._add_section_heading(doc, section.heading)
        for line in section.lines:
            if line.bullet:
                self._add_bullets(doc, [line.text])
            else:
                doc.add_paragraph(line.text).paragraph_format.space_after = Pt(2)

    def _add_achievements(self, doc, resume, content_width) -> None:
        if resume.achievements:
            self._add_section_heading(doc, SECTION_TITLES["achievements"])
            self._add_bullets(doc, resume.achievements)

    def _add_interests(self, doc, resume, content_width) -> None:
        if resume.interests:
            self._add_section_heading(doc, SECTION_TITLES["interests"])
            doc.add_paragraph(", ".join(resume.interests)).paragraph_format.space_after = Pt(2)

    # -- layout helpers -----------------------------------------------

    def _set_document_defaults(self, doc: "docx.Document", presentation: "ResumePresentation") -> None:
        """A4, the template's margins and font, instead of python-docx's
        stock Letter page and Calibri Normal style."""
        section = doc.sections[0]
        section.page_width, section.page_height = Mm(210), Mm(297)
        section.left_margin = section.right_margin = Inches(presentation.margin_side_in)
        section.top_margin = section.bottom_margin = Inches(presentation.margin_vertical_in)

        for style_name in ("Normal", "List Bullet"):
            try:
                style = doc.styles[style_name]
            except KeyError:
                continue
            style.font.name = presentation.font_family
            # East-Asian and complex scripts in a font that has them (P8.25):
            # Arial has no Chinese, so a CJK name rendered blank.
            fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
            fonts.set(qn("w:eastAsia"), fallback_font())
            fonts.set(qn("w:cs"), fallback_font())
            style.font.size = Pt(10 if presentation.compact else 10.5)
        normal = doc.styles["Normal"]
        normal.font.color.rgb = BODY_COLOR
        normal.paragraph_format.space_after = Pt(4)
        normal.paragraph_format.line_spacing = 1.0 if presentation.compact else 1.1

    def _content_width(self, doc: "docx.Document") -> float:
        section = doc.sections[0]
        return section.page_width - section.left_margin - section.right_margin

    def _add_section_heading(self, doc: "docx.Document", text: str) -> None:
        """A section label in the accent color with a rule underneath —
        the DOCX equivalent of the HTML renderer's <h2>, so both outputs
        read as the same design rather than a plain Word heading."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10 * self._gap)
        p.paragraph_format.space_after = Pt(4 * self._gap)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11.5)
        run.font.color.rgb = ACCENT_COLOR
        self._add_bottom_border(p, size=6)

    @staticmethod
    def _role_dates(role) -> str:
        return date_range(role.start_date, role.end_date) if role else ""

    def _add_meta_line(self, doc, text: str) -> None:
        """'Company · Location' in italic grey under a title line."""
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        run.italic = True
        run.font.size = Pt(10)
        run.font.color.rgb = META_COLOR

    def _add_bullets(self, doc, texts) -> None:
        for text in texts:
            if text:
                doc.add_paragraph(text, style="List Bullet").paragraph_format.space_after = Pt(1)

    def _add_title_dates_line(self, doc: "docx.Document", title: str, dates: str, content_width,
                              bold: bool = True, space_before: float = 0) -> None:
        """Title (bold) on the left, date range right-aligned on the same
        line via a right tab stop — the standard modern-resume layout
        (Novoresume/Overleaf-style templates all do this) instead of
        stacking title and dates as two separate left-aligned lines."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(space_before * self._gap)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.keep_with_next = True
        if dates:
            p.paragraph_format.tab_stops.add_tab_stop(content_width, WD_TAB_ALIGNMENT.RIGHT)
        run = p.add_run(title)
        run.bold = bold
        run.font.size = Pt(11)
        if dates:
            p.add_run("\t")
            date_run = p.add_run(dates)
            date_run.font.size = Pt(10)
            date_run.font.color.rgb = META_COLOR

    @staticmethod
    def _add_bottom_border(paragraph, *, size: int = 6, color: str = "1F4E79") -> None:
        """Adds a single bottom border to a paragraph via raw OOXML — the
        standard python-docx recipe for a section-divider rule, since the
        library has no high-level API for paragraph borders."""
        p = paragraph._p
        p_pr = p.get_or_add_pPr()
        p_bdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), str(size))
        bottom.set(qn("w:space"), "2")
        bottom.set(qn("w:color"), color)
        p_bdr.append(bottom)
        p_pr.append(p_bdr)
