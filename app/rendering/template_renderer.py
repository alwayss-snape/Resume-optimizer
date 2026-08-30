import os

import docx

from app.domain.resume import Resume

class TemplateRenderer:
    """Standard single-column, ATS-safe DOCX renderer with no content omissions."""

    def render_ats_default(self, resume: Resume, output_path: str) -> str:
        doc = docx.Document()
        doc.add_paragraph(resume.candidate.name, style="Title")

        contact = [
            value for value in (resume.candidate.email, resume.candidate.phone,
                                resume.candidate.location, *resume.candidate.links)
            if value
        ]
        if contact:
            doc.add_paragraph(" | ".join(contact))

        if resume.summary:
            doc.add_heading("Professional Summary", level=1)
            doc.add_paragraph(resume.summary)

        if resume.experience:
            doc.add_heading("Work Experience", level=1)
            for exp in resume.experience:
                heading = " — ".join(value for value in (exp.title, exp.company) if value)
                if exp.start_date or exp.end_date:
                    heading += f" | {' — '.join(value for value in (exp.start_date, exp.end_date) if value)}"
                doc.add_paragraph(heading).runs[0].bold = True
                for bullet in exp.bullets:
                    doc.add_paragraph(bullet.text, style="List Bullet")

        if resume.projects:
            doc.add_heading("Projects", level=1)
            for project in resume.projects:
                doc.add_paragraph(project.name).runs[0].bold = True
                if project.description:
                    doc.add_paragraph(project.description)
                if project.technologies:
                    doc.add_paragraph("Technologies: " + ", ".join(project.technologies))
                for bullet in project.bullets:
                    doc.add_paragraph(bullet.text, style="List Bullet")

        if resume.skills:
            doc.add_heading("Skills", level=1)
            for category, skills in resume.skills.items():
                doc.add_paragraph(f"{category}: {', '.join(skills)}")

        if resume.education:
            doc.add_heading("Education", level=1)
            for education in resume.education:
                values = [education.degree, education.institution, education.dates]
                doc.add_paragraph(" — ".join(value for value in values if value))

        if resume.certifications:
            doc.add_heading("Certifications", level=1)
            for certification in resume.certifications:
                doc.add_paragraph(" — ".join(value for value in certification.values() if value))

        if resume.achievements:
            doc.add_heading("Achievements", level=1)
            for achievement in resume.achievements:
                doc.add_paragraph(achievement, style="List Bullet")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        return output_path
