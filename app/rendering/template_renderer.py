import os

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from typing import Any, Optional

from app.domain.resume import Resume
try:
    from app.domain.resume_document import ResumeDocument
except Exception:
    ResumeDocument = None


# Shared visual language with HtmlResumeRenderer's default accent (#1F4E79)
# so the DOCX/PDF download and the in-app HTML preview don't look like two
# different products.
ACCENT_COLOR = RGBColor(0x1F, 0x4E, 0x79)
META_COLOR = RGBColor(0x4B, 0x55, 0x63)  # dates/company/location — de-emphasized
BODY_COLOR = RGBColor(0x11, 0x18, 0x27)


class TemplateRenderer:
    """Standard single-column, ATS-safe DOCX renderer with support for ResumeDocument."""

    def render_ats_default(self, resume_or_doc: Any, output_path: str) -> str:
        # Accept either a Resume or a ResumeDocument; unwrap when necessary
        if hasattr(resume_or_doc, "resume"):
            resume = resume_or_doc.resume
        else:
            resume = resume_or_doc

        doc = docx.Document()
        self._set_document_defaults(doc)
        content_width = self._content_width(doc)

        candidate_name = getattr(resume, "candidate", None) and getattr(resume.candidate, "name", None)
        if candidate_name:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(candidate_name)
            run.bold = True
            run.font.size = Pt(22)
            run.font.color.rgb = ACCENT_COLOR

        headline = getattr(getattr(resume, "candidate", None), "headline", None)
        if headline:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(headline)
            run.font.size = Pt(12)
            run.font.color.rgb = ACCENT_COLOR

        # Contact info
        contact_parts = []
        if getattr(resume, "candidate", None):
            cand = resume.candidate
            if getattr(cand, "email", None):
                contact_parts.append(cand.email)
            if getattr(cand, "phone", None):
                contact_parts.append(cand.phone)
            if getattr(cand, "location", None):
                contact_parts.append(cand.location)
            contact_parts.extend(cand.display_links())
        if contact_parts:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run("  ·  ".join(contact_parts))
            run.font.size = Pt(10)
            run.font.color.rgb = META_COLOR
            self._add_bottom_border(p, size=10)

        # Summary
        if getattr(resume, "summary", None):
            self._add_section_heading(doc, "Professional Summary")
            p = doc.add_paragraph(resume.summary)
            p.paragraph_format.space_after = Pt(8)

        # Experience
        if getattr(resume, "experience", None):
            self._add_section_heading(doc, "Work Experience")
            for i, exp in enumerate(resume.experience):
                roles = exp.all_roles()
                company = getattr(exp, "company", None) or ""
                location = getattr(exp, "location", None)
                first = roles[0] if roles else None
                # No title found in the file: the company takes the bold line
                # rather than printing a placeholder.
                heading = (first.title if first and first.title else "") or company
                self._add_title_dates_line(doc, heading, self._role_dates(first), content_width)

                meta = " · ".join(v for v in (company if heading != company else "", location) if v)
                if meta:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(3)
                    run = p.add_run(meta)
                    run.italic = True
                    run.font.size = Pt(10)
                    run.font.color.rgb = META_COLOR

                # Earlier roles at the same company (promotions).
                for role in roles[1:]:
                    self._add_title_dates_line(doc, role.title, self._role_dates(role), content_width, bold=False)

                for group, bullets in exp.bullet_groups():
                    if group:
                        gp = doc.add_paragraph()
                        gp.paragraph_format.space_before = Pt(3)
                        gp.paragraph_format.space_after = Pt(1)
                        grun = gp.add_run(group)
                        grun.bold = True
                        grun.font.size = Pt(10.5)
                    for bullet in bullets:
                        bp = doc.add_paragraph(getattr(bullet, "text", ""), style="List Bullet")
                        bp.paragraph_format.space_after = Pt(2)
                        for run in bp.runs:
                            run.font.size = Pt(10.5)

                is_last = i == len(resume.experience) - 1
                if not is_last:
                    doc.add_paragraph().paragraph_format.space_after = Pt(2)

        # Projects
        if getattr(resume, "projects", None):
            self._add_section_heading(doc, "Projects")
            for project in resume.projects:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                run = p.add_run(getattr(project, "name", ""))
                run.bold = True
                run.font.size = Pt(11)
                if getattr(project, "description", None):
                    dp = doc.add_paragraph(project.description)
                    dp.paragraph_format.space_after = Pt(2)
                if getattr(project, "technologies", None):
                    tp = doc.add_paragraph()
                    tp.paragraph_format.space_after = Pt(2)
                    label_run = tp.add_run("Technologies: ")
                    label_run.bold = True
                    label_run.font.size = Pt(10)
                    label_run.font.color.rgb = META_COLOR
                    val_run = tp.add_run(", ".join(project.technologies))
                    val_run.font.size = Pt(10)
                    val_run.font.color.rgb = META_COLOR
                for bullet in getattr(project, "bullets", []) or []:
                    bp = doc.add_paragraph(getattr(bullet, "text", ""), style="List Bullet")
                    bp.paragraph_format.space_after = Pt(2)
                    for run in bp.runs:
                        run.font.size = Pt(10.5)

        # Skills
        if getattr(resume, "skills", None):
            self._add_section_heading(doc, "Technical Skills")
            for category, skill_list in resume.skills.items():
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(3)
                label_run = p.add_run(f"{category}: ")
                label_run.bold = True
                label_run.font.size = Pt(10.5)
                val_run = p.add_run(", ".join(skill_list))
                val_run.font.size = Pt(10.5)

        # Education
        if getattr(resume, "education", None):
            self._add_section_heading(doc, "Education")
            for education in resume.education:
                degree = getattr(education, "degree", None) or ""
                dates = getattr(education, "dates", None) or ""
                self._add_title_dates_line(doc, degree, dates, content_width)

                institution = getattr(education, "institution", None) or ""
                location = getattr(education, "location", None)
                meta = " · ".join(v for v in (institution, location) if v)
                if meta:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(6)
                    run = p.add_run(meta)
                    run.italic = True
                    run.font.size = Pt(10)
                    run.font.color.rgb = META_COLOR

        # Certifications
        if getattr(resume, "certifications", None):
            self._add_section_heading(doc, "Certifications")
            for certification in resume.certifications:
                # certification may be dict-like
                try:
                    vals = [v for v in certification.values() if v]
                except Exception:
                    vals = [v for v in certification if v]
                p = doc.add_paragraph(" — ".join(vals), style="List Bullet")
                p.paragraph_format.space_after = Pt(2)

        # Achievements
        if getattr(resume, "achievements", None):
            self._add_section_heading(doc, "Achievements")
            for achievement in resume.achievements:
                p = doc.add_paragraph(achievement, style="List Bullet")
                p.paragraph_format.space_after = Pt(2)

        # Interests
        if getattr(resume, "interests", None):
            self._add_section_heading(doc, "Interests")
            p = doc.add_paragraph(", ".join(resume.interests))
            p.paragraph_format.space_after = Pt(2)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        return output_path

    # -- layout helpers -----------------------------------------------

    def _set_document_defaults(self, doc: "docx.Document") -> None:
        """Tighter, more consistent margins/typography than python-docx's
        stock Normal style, so the doc reads like a real resume template
        instead of a default Word document."""
        section = doc.sections[0]
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)

        normal = doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(10.5)
        normal.font.color.rgb = BODY_COLOR
        normal.paragraph_format.space_after = Pt(4)
        normal.paragraph_format.line_spacing = 1.12

        try:
            bullet_style = doc.styles["List Bullet"]
            bullet_style.font.name = "Calibri"
            bullet_style.font.size = Pt(10.5)
        except KeyError:
            pass

    def _content_width(self, doc: "docx.Document") -> float:
        section = doc.sections[0]
        return section.page_width - section.left_margin - section.right_margin

    def _add_section_heading(self, doc: "docx.Document", text: str) -> None:
        """A section label in the accent color with a rule underneath —
        the DOCX equivalent of the HTML renderer's <h2>, so both outputs
        read as the same design rather than a plain Word heading."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11.5)
        run.font.color.rgb = ACCENT_COLOR
        # A little letter-spacing reads closer to the HTML version's
        # uppercase+tracking treatment than plain uppercase alone.
        self._add_bottom_border(p, size=6)

    @staticmethod
    def _role_dates(role) -> str:
        if role is None:
            return ""
        return " – ".join(v for v in (role.start_date, role.end_date) if v)

    def _add_title_dates_line(self, doc: "docx.Document", title: str, dates: str, content_width,
                              bold: bool = True) -> None:
        """Title (bold) on the left, date range right-aligned on the same
        line via a right tab stop — the standard modern-resume layout
        (Novoresume/Overleaf-style templates all do this) instead of
        stacking title and dates as two separate left-aligned lines."""
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
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
