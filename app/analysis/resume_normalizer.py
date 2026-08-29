import re
from typing import List, Tuple
from app.domain.evidence import Evidence
from app.domain.resume import Candidate, Education, Experience, Project, Resume, ResumeBullet
from app.ingestion.docx import RawDocument

class ResumeNormalizer:
    def normalize(self, raw_doc: RawDocument) -> Tuple[Resume, List[Evidence]]:
        summary_text: List[str] = []
        experiences: List[Experience] = []
        projects: List[Project] = []
        education_list: List[Education] = []
        skills_dict: dict[str, List[str]] = {}
        evidence_list: List[Evidence] = []

        candidate_name = "Candidate"
        candidate_email = None
        candidate_phone = None
        candidate_location = None

        current_section = "Header"
        current_exp: Experience | None = None
        current_proj: Project | None = None

        exp_counter = 0
        bullet_counter = 0
        proj_counter = 0
        edu_counter = 0
        ev_counter = 0

        for block in raw_doc.blocks:
            text = block.text.strip()
            if not text:
                continue

            if block.block_type == "heading":
                current_section = text
                continue

            section_lower = current_section.lower()

            # Header / Candidate info parsing
            if "header" in section_lower or block.location.paragraph_index == 0 or candidate_name == "Candidate":
                if "@" in text:
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                    if email_match:
                        candidate_email = email_match.group(0)
                if re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text):
                    candidate_phone = re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text).group(0)
                if "@" not in text and not re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text) and len(text) < 40 and candidate_name == "Candidate":
                    candidate_name = text

            # Summary section
            elif "summary" in section_lower or "profile" in section_lower:
                summary_text.append(text)
                ev_id = f"ev_{ev_counter:04d}"
                ev_counter += 1
                evidence_list.append(Evidence(
                    id=ev_id,
                    source_type="summary",
                    source_id=block.id,
                    text=text,
                ))

            # Experience section
            elif "experience" in section_lower or "work" in section_lower or "employment" in section_lower:
                if block.block_type == "paragraph" or (current_exp is None and block.block_type != "bullet"):
                    # Header line for job entry: Company — Title (Dates)
                    parts = text.split("—") if "—" in text else text.split("-")
                    company = parts[0].strip() if parts else text
                    title = parts[1].strip() if len(parts) > 1 else "Engineer / Professional"
                    
                    exp_counter += 1
                    exp_id = f"exp_{exp_counter:03d}"
                    current_exp = Experience(
                        id=exp_id,
                        company=company,
                        title=title,
                        bullets=[],
                    )
                    experiences.append(current_exp)
                elif block.block_type == "bullet" and current_exp is not None:
                    bullet_counter += 1
                    bullet_id = f"{current_exp.id}_b{bullet_counter:02d}"
                    bullet = ResumeBullet(id=bullet_id, text=text, source_location_id=block.id)
                    current_exp.bullets.append(bullet)

                    ev_id = f"ev_{ev_counter:04d}"
                    ev_counter += 1
                    evidence_list.append(Evidence(
                        id=ev_id,
                        source_type="experience",
                        source_id=bullet_id,
                        text=f"{current_exp.company} ({current_exp.title}): {text}",
                    ))

            # Skills section
            elif "skill" in section_lower or "technolog" in section_lower:
                parts = text.split(":")
                category = parts[0].strip() if len(parts) > 1 else "Technical Skills"
                skills_list = [s.strip() for s in (parts[1] if len(parts) > 1 else parts[0]).split(",") if s.strip()]
                skills_dict[category] = skills_list
                
                for skill in skills_list:
                    ev_id = f"ev_{ev_counter:04d}"
                    ev_counter += 1
                    evidence_list.append(Evidence(
                        id=ev_id,
                        source_type="skill",
                        source_id=f"skill_{skill.lower().replace(' ', '_')}",
                        text=skill,
                    ))

            # Education section
            elif "education" in section_lower or "academic" in section_lower:
                edu_counter += 1
                edu_id = f"edu_{edu_counter:03d}"
                edu_entry = Education(
                    id=edu_id,
                    institution=text,
                    degree=text,
                )
                education_list.append(edu_entry)
                ev_id = f"ev_{ev_counter:04d}"
                ev_counter += 1
                evidence_list.append(Evidence(
                    id=ev_id,
                    source_type="education",
                    source_id=edu_id,
                    text=text,
                ))

        candidate = Candidate(
            name=candidate_name,
            email=candidate_email,
            phone=candidate_phone,
            location=candidate_location,
        )

        resume = Resume(
            candidate=candidate,
            summary=" ".join(summary_text) if summary_text else None,
            experience=experiences,
            projects=projects,
            education=education_list,
            skills=skills_dict,
        )

        return resume, evidence_list
