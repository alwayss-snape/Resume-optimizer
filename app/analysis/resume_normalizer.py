import re
from typing import List, Tuple
from app.domain.evidence import Evidence
from app.domain.resume import Candidate, Education, Experience, Project, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument
from app.ingestion.docx import RawDocument

class ResumeNormalizer:
<<<<<<< HEAD
    DATE_PATTERN = re.compile(r'\b(?:19|20)\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|Current)\b', re.IGNORECASE)

    def normalize(self, raw_doc: RawDocument) -> Tuple[Resume, List[Evidence]]:
=======
    def normalize(self, raw_doc: RawDocument) -> Tuple["ResumeDocument", List[Evidence]]:
>>>>>>> cbd4d9f (WIP: save local changes before rebase)
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
            if "header" in section_lower or block.location.paragraph_index in (0, 1) or candidate_name == "Candidate":
                if "@" in text:
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                    if email_match:
                        candidate_email = email_match.group(0)
                if re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text):
                    phone_match = re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text)
                    if phone_match:
                        candidate_phone = phone_match.group(0)
                if "@" not in text and not re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text) and len(text) < 40 and candidate_name == "Candidate":
                    candidate_name = text

            # Summary section
            if any(k in section_lower for k in ("summary", "profile", "about", "objective")):
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
            elif any(k in section_lower for k in ("experience", "work", "employment", "career", "history")):
                is_job_header = (
                    current_exp is None
                    or (self.DATE_PATTERN.search(text) and len(text) < 90 and not block.block_type == "bullet")
                    or (("—" in text or " - " in text or " | " in text) and len(text) < 70 and not block.block_type == "bullet")
                )

                if is_job_header:
                    exp_counter += 1
                    exp_id = f"exp_{exp_counter:03d}"
                    parts = re.split(r'[—\-\|]', text)
                    company = parts[0].strip() if parts else text
                    title = parts[1].strip() if len(parts) > 1 else "Professional Role"
                    current_exp = Experience(
                        id=exp_id,
                        company=company,
                        title=title,
                        bullets=[],
                    )
                    experiences.append(current_exp)
                else:
                    if current_exp is None:
                        exp_counter += 1
                        exp_id = f"exp_{exp_counter:03d}"
                        current_exp = Experience(
                            id=exp_id,
                            company="Professional Experience",
                            title="Role",
                            bullets=[],
                        )
                        experiences.append(current_exp)

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
                        text=f"{current_exp.company}: {text}",
                    ))

            # Projects section
            elif any(k in section_lower for k in ("project", "portfolio")):
                if current_proj is None or (len(text) < 60 and not block.block_type == "bullet"):
                    proj_counter += 1
                    proj_id = f"proj_{proj_counter:03d}"
                    current_proj = Project(id=proj_id, name=text, bullets=[])
                    projects.append(current_proj)
                else:
                    bullet_counter += 1
                    bullet_id = f"{current_proj.id}_b{bullet_counter:02d}"
                    bullet = ResumeBullet(id=bullet_id, text=text, source_location_id=block.id)
                    current_proj.bullets.append(bullet)
                    ev_id = f"ev_{ev_counter:04d}"
                    ev_counter += 1
                    evidence_list.append(Evidence(
                        id=ev_id,
                        source_type="project",
                        source_id=bullet_id,
                        text=f"Project ({current_proj.name}): {text}",
                    ))

            # Skills section
            elif any(k in section_lower for k in ("skill", "technolog", "competenc", "expertise", "tools")):
                parts = text.split(":")
                category = parts[0].strip() if len(parts) > 1 else "Skills"
                raw_skills_text = parts[1] if len(parts) > 1 else parts[0]
                skills_list = [s.strip() for s in re.split(r'[,;\|\*\•\n]', raw_skills_text) if s.strip()]
                
                if category not in skills_dict:
                    skills_dict[category] = []
                skills_dict[category].extend(skills_list)
                
                for skill in skills_list:
                    ev_id = f"ev_{ev_counter:04d}"
                    ev_counter += 1
                    evidence_list.append(Evidence(
                        id=ev_id,
                        source_type="skill",
                        source_id=f"skill_{ev_counter:04d}",
                        text=skill,
                    ))

            # Education section
            elif any(k in section_lower for k in ("education", "academic", "qualification", "degree", "university")):
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

            # Catch-all general section if text contains substantial candidate experience
            else:
                ev_id = f"ev_{ev_counter:04d}"
                ev_counter += 1
                evidence_list.append(Evidence(
                    id=ev_id,
                    source_type="general",
                    source_id=block.id,
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

        # Wrap into ResumeDocument (single source of truth)
        resume_doc = ResumeDocument(resume=resume)
        resume_doc.record_revision(rev_id="import_0001", actor="import", original=None, rewritten=None, evidence_ids=[e.id for e in evidence_list], source=raw_doc.filename)

        return resume_doc, evidence_list
