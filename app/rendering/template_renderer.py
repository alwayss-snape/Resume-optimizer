import os
import docx
from app.domain.resume import Resume

class TemplateRenderer:
    def render_ats_default(self, resume: Resume, output_path: str) -> str:
        doc = docx.Document()

        # Title
        p_name = doc.add_paragraph(resume.candidate.name)
        p_name.style = "Title"

        # Contact info
        contact_parts = []
        if resume.candidate.email:
            contact_parts.append(f"Email: {resume.candidate.email}")
        if resume.candidate.phone:
            contact_parts.append(f"Phone: {resume.candidate.phone}")
        if resume.candidate.location:
            contact_parts.append(f"Location: {resume.candidate.location}")
        if contact_parts:
            doc.add_paragraph(" | ".join(contact_parts))

        # Summary
        if resume.summary:
            doc.add_heading("Professional Summary", level=1)
            doc.add_paragraph(resume.summary)

        # Experience
        if resume.experience:
            doc.add_heading("Work Experience", level=1)
            for exp in resume.experience:
                p_exp = doc.add_paragraph()
                r_title = p_exp.add_run(f"{exp.company} — {exp.title}")
                r_title.bold = True
                
                for bullet in exp.bullets:
                    doc.add_paragraph(f"• {bullet.text}", style="List Bullet")

        # Skills
        if resume.skills:
            doc.add_heading("Technical Skills", level=1)
            for category, skill_list in resume.skills.items():
                doc.add_paragraph(f"{category}: {', '.join(skill_list)}")

        # Education
        if resume.education:
            doc.add_heading("Education", level=1)
            for edu in resume.education:
                doc.add_paragraph(f"{edu.institution} — {edu.degree}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        return output_path
