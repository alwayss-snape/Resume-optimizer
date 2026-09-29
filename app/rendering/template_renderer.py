import os

import docx
from typing import Any

from app.domain.resume import Resume
try:
    from app.domain.resume_document import ResumeDocument
except Exception:
    ResumeDocument = None


class TemplateRenderer:
    """Standard single-column, ATS-safe DOCX renderer with support for ResumeDocument."""

    def render_ats_default(self, resume_or_doc: Any, output_path: str) -> str:
        # Accept either a Resume or a ResumeDocument; unwrap when necessary
        if hasattr(resume_or_doc, "resume"):
            resume = resume_or_doc.resume
        else:
            resume = resume_or_doc

        doc = docx.Document()
        candidate_name = getattr(resume, "candidate", None) and getattr(resume.candidate, "name", None)
        if candidate_name:
            doc.add_paragraph(candidate_name, style="Title")

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
            links = getattr(cand, "links", []) or []
            contact_parts.extend([l for l in links if l])
        if contact_parts:
            doc.add_paragraph(" | ".join(contact_parts))

        # Summary
        if getattr(resume, "summary", None):
            doc.add_heading("Professional Summary", level=1)
            doc.add_paragraph(resume.summary)

        # Experience
        if getattr(resume, "experience", None):
            doc.add_heading("Work Experience", level=1)
            for exp in resume.experience:
                company_line = getattr(exp, "company", None) or ""
                if getattr(exp, "location", None):
                    company_line = f"{company_line} — {exp.location}" if company_line else exp.location
                if company_line:
                    p = doc.add_paragraph(company_line)
                    if p.runs:
                        p.runs[0].bold = True

                title_line = getattr(exp, "title", None) or ""
                dates = [getattr(exp, "start_date", None), getattr(exp, "end_date", None)]
                if any(dates):
                    date_str = " – ".join(value for value in dates if value)
                    title_line = f"{title_line} | {date_str}" if title_line else date_str
                if title_line:
                    doc.add_paragraph(title_line)

                for bullet in getattr(exp, "bullets", []) or []:
                    doc.add_paragraph(getattr(bullet, "text", ""), style="List Bullet")

        # Projects
        if getattr(resume, "projects", None):
            doc.add_heading("Projects", level=1)
            for project in resume.projects:
                p = doc.add_paragraph(getattr(project, "name", ""))
                if p.runs:
                    p.runs[0].bold = True
                if getattr(project, "description", None):
                    doc.add_paragraph(project.description)
                if getattr(project, "technologies", None):
                    doc.add_paragraph("Technologies: " + ", ".join(project.technologies))
                for bullet in getattr(project, "bullets", []) or []:
                    doc.add_paragraph(getattr(bullet, "text", ""), style="List Bullet")

        # Skills
        if getattr(resume, "skills", None):
            doc.add_heading("Technical Skills", level=1)
            for category, skill_list in resume.skills.items():
                doc.add_paragraph(f"{category}: {', '.join(skill_list)}")

        # Education
        if getattr(resume, "education", None):
            doc.add_heading("Education", level=1)
            for education in resume.education:
                inst_line = getattr(education, "institution", None) or ""
                if getattr(education, "location", None):
                    inst_line = f"{inst_line} — {education.location}" if inst_line else education.location
                if inst_line:
                    p = doc.add_paragraph(inst_line)
                    if p.runs:
                        p.runs[0].bold = True

                degree_line_parts = [getattr(education, "degree", None), getattr(education, "dates", None)]
                degree_line = " | ".join(value for value in degree_line_parts if value)
                if degree_line:
                    doc.add_paragraph(degree_line)

        # Certifications
        if getattr(resume, "certifications", None):
            doc.add_heading("Certifications", level=1)
            for certification in resume.certifications:
                # certification may be dict-like
                try:
                    vals = [v for v in certification.values() if v]
                except Exception:
                    vals = [v for v in certification if v]
                doc.add_paragraph(" — ".join(vals))

        # Achievements
        if getattr(resume, "achievements", None):
            doc.add_heading("Achievements", level=1)
            for achievement in resume.achievements:
                doc.add_paragraph(achievement, style="List Bullet")

        # Interests
        if getattr(resume, "interests", None):
            doc.add_heading("Interests", level=1)
            doc.add_paragraph(", ".join(resume.interests))

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        return output_path
