import re
from typing import List, Optional, Tuple
from app.domain.evidence import Evidence
from app.domain.resume import Candidate, Education, Experience, Project, Resume, ResumeBullet
from app.domain.resume_document import ResumeDocument
from app.ingestion.docx import RawDocument

class ResumeNormalizer:
    DATE_PATTERN = re.compile(
        r"\b(?:19|20)\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b|\b(?:Present|Current)\b",
        re.IGNORECASE,
    )
    # Trailing "<start> - <end>" / "(<start> - <end>)" date-range pattern, e.g.
    # "August 2024 - Present" or "(2014 – 2018)".
    DATE_RANGE_RE = re.compile(
        r"\(?\s*((?:[A-Za-z]+\.?\s*)?\d{4})\s*[-–—]\s*"
        r"((?:[A-Za-z]+\.?\s*)?\d{4}|Present|Current)\s*\)?\s*$",
        re.IGNORECASE,
    )
    PHONE_RE = re.compile(r'(\+\d{1,3}[-.\s]?)?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b')

    # Only these mark a genuine new top-level résumé section. A heading-styled
    # line that doesn't match one of these (the candidate's name, a bold
    # company/title line, a project sub-heading inside a job) is NOT a
    # section boundary — it falls through and is handled as content of
    # whatever section we're already in, instead of silently discarding it
    # or resetting context away from "Work Experience" mid-job.
    # Whole words only (matched with \b...\b below) — plain substring
    # matching would false-positive on e.g. "Fraud Detection FrameWORK" or
    # "HomeWORK", silently swallowing project sub-headings as if they were
    # top-level "Work Experience" section boundaries.
    SECTION_KEYWORDS = (
        "summary", "profile", "about", "objective",
        "experience", "work", "employment", "career", "history",
        "project", "portfolio",
        "skill", "skills", "technology", "technologies", "technological",
        "competency", "competencies", "expertise", "tools",
        "education", "academic", "qualification", "qualifications", "university",
        "certification", "certifications", "certificate", "certificates",
        "interest", "interests", "award", "awards",
        "achievement", "achievements", "activity", "activities",
    )
    SECTION_KEYWORDS_RE = re.compile(
        r"\b(?:" + "|".join(SECTION_KEYWORDS) + r")\b", re.IGNORECASE
    )

    # Chars trimmed off a title/company fragment once the trailing date range
    # (and whatever separated it, e.g. "Title | Aug 2024 - Present") has been
    # removed. Missing "|" here left literal pipes baked into every title
    # for resumes that separate title from dates with " | " rather than ",".
    _TRIM_CHARS = " \t,|()-–—"

    def _extract_date_range(self, text: str) -> Optional[str]:
        m = self.DATE_RANGE_RE.search(text)
        return f"{m.group(1).strip()} – {m.group(2).strip()}" if m else None

    def _strip_date_range(self, text: str) -> str:
        m = self.DATE_RANGE_RE.search(text)
        return text[:m.start()].strip(self._TRIM_CHARS) if m else text.strip()

    def _parse_title_and_dates(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """'Data Scientist II | August 2024 - Present' ->
        ('Data Scientist II', 'August 2024', 'Present')."""
        m = self.DATE_RANGE_RE.search(text)
        if not m:
            return text.strip(), None, None
        title = text[:m.start()].strip(self._TRIM_CHARS)
        return (title or text.strip()), m.group(1).strip(), m.group(2).strip()

    def _split_respecting_parens(self, text: str, sep_chars: str = ",;|•\n") -> List[str]:
        """Split on sep_chars, but never inside ( ) or [ ] groups — so
        'Python (pandas, scikit-learn, transformers), SQL' splits into
        ['Python (pandas, scikit-learn, transformers)', 'SQL'] instead of
        shredding the parenthetical sub-list on every inner comma."""
        parts: List[str] = []
        current: List[str] = []
        depth = 0
        for ch in text:
            if ch in "([":
                depth += 1
                current.append(ch)
            elif ch in ")]":
                depth = max(0, depth - 1)
                current.append(ch)
            elif ch in sep_chars and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        parts.append("".join(current))
        return [p.strip() for p in parts if p.strip()]

    def normalize(self, raw_doc: RawDocument) -> Tuple["ResumeDocument", List[Evidence]]:
        summary_text: List[str] = []
        experiences: List[Experience] = []
        projects: List[Project] = []
        education_list: List[Education] = []
        skills_dict: dict[str, List[str]] = {}
        certifications: List[dict] = []
        interests: List[str] = []
        achievements: List[str] = []
        evidence_list: List[Evidence] = []

        candidate_name = "Candidate"
        candidate_email = None
        candidate_phone = None
        candidate_location = None

        current_section = "Header"
        current_exp: Optional[Experience] = None
        current_proj: Optional[Project] = None
        current_edu: Optional[Education] = None
        # True once current_exp has a real bullet (not a synthetic "Previously:"
        # note) — distinguishes "still reading this job's header lines" from
        # "a new header line here means a new job/company has started".
        current_exp_has_content = False

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
                if self.SECTION_KEYWORDS_RE.search(text):
                    current_section = text
                    continue
                # Else: a heading-styled line that isn't a recognized
                # top-level section (candidate name, bold company/title
                # line, a project sub-heading inside a job) — fall through
                # and process it as content of the CURRENT section instead
                # of silently resetting/discarding it.

            section_lower = current_section.lower()

            # Header / Candidate info parsing
            if "header" in section_lower or block.location.paragraph_index in (0, 1) or candidate_name == "Candidate":
                if "@" in text:
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                    if email_match:
                        candidate_email = email_match.group(0)
                phone_match = self.PHONE_RE.search(text)
                if phone_match:
                    candidate_phone = phone_match.group(0)
                if "@" not in text and not phone_match and len(text) < 40 and candidate_name == "Candidate":
                    candidate_name = text
                # A pipe/bullet-separated contact line (e.g. "LinkedIn | Email |
                # Leetcode | +91-... | Bangalore, India") often carries a
                # "City, Country/State" segment; pull it out as location
                # instead of leaving it undetected.
                if candidate_location is None:
                    for segment in re.split(r"[|•·]", text):
                        segment = segment.strip()
                        if not segment or segment == text.strip():
                            continue
                        if "@" in segment or self.PHONE_RE.search(segment):
                            continue
                        if re.match(r"^[A-Za-z][A-Za-z .'-]*,\s*[A-Za-z][A-Za-z .'-]*$", segment):
                            candidate_location = segment
                            break

            # Summary section
            if any(k in section_lower for k in ("summary", "profile", "about", "objective")):
                summary_text.append(text)
                ev_id = f"ev_{ev_counter:04d}"
                ev_counter += 1
                evidence_list.append(Evidence(
                    id=ev_id,
                    source_type="summary",
                    # No semantic node for a free-form summary; store raw location as both
                    source_id=block.id,
                    source_location_id=block.id,
                    text=text,
                ))

            # Experience section
            elif any(k in section_lower for k in ("experience", "work", "employment", "career", "history")):
                has_date = bool(self.DATE_PATTERN.search(text))
                has_sep = ("—" in text or " - " in text or " | " in text or "\t" in text)
                is_job_header = (
                    block.block_type != "bullet"
                    and (has_date or has_sep)
                    and len(text) < 90
                )

                if is_job_header:
                    if "\t" in text:
                        left, right_col = [p.strip() for p in text.split("\t", 1)]
                    else:
                        left, right_col = text, None

                    if has_date:
                        title, start, end = self._parse_title_and_dates(left)
                        body = self._strip_date_range(left)
                        dash_parts = [p.strip() for p in re.split(r"\s+—\s+|\s+-\s+", body) if p.strip()]
                        is_new_entry = (
                            current_exp is None
                            or current_exp_has_content
                            or len(dash_parts) >= 2
                        )

                        if is_new_entry and len(dash_parts) >= 2:
                            # Combined single line: "Company — Title (dates)"
                            exp_counter += 1
                            current_exp = Experience(
                                id=f"exp_{exp_counter:03d}", company=dash_parts[0], title=dash_parts[1],
                                start_date=start, end_date=end, location=right_col,
                            )
                            experiences.append(current_exp)
                            current_exp_has_content = False
                        elif is_new_entry:
                            # Bare "Title, dates" line, but the previous entry
                            # already has real content -> this starts a new
                            # role whose company we can't isolate from this
                            # line alone.
                            exp_counter += 1
                            current_exp = Experience(
                                id=f"exp_{exp_counter:03d}", company="Professional Experience", title=title,
                                start_date=start, end_date=end, location=right_col,
                            )
                            experiences.append(current_exp)
                            current_exp_has_content = False
                        elif not current_exp.start_date:
                            # First title/date info for this (already-started,
                            # still content-free) entry.
                            current_exp.title = title
                            current_exp.start_date = start
                            current_exp.end_date = end
                            if right_col and not current_exp.location:
                                current_exp.location = right_col
                        else:
                            # A second bare title/date line under the same
                            # company header, before any bullets -> a
                            # promotion. The schema holds one title per
                            # Experience, so record the earlier role as a note
                            # rather than silently dropping it or scrambling
                            # it into a fake separate company.
                            bullet_counter += 1
                            bullet_id = f"{current_exp.id}_prev{bullet_counter:02d}"
                            date_part = f" ({start} – {end})" if (start or end) else ""
                            note_text = f"Previously: {title}{date_part}"
                            current_exp.bullets.append(ResumeBullet(id=bullet_id, text=note_text, source_location_id=block.id))
                    else:
                        # A company (+ optional location) header line, e.g.
                        # "Epsilon - A Publicis Groupe Company" or, tab-separated,
                        # "Epsilon - A Publicis Groupe Company\tBengaluru, India".
                        exp_counter += 1
                        current_exp = Experience(
                            id=f"exp_{exp_counter:03d}", company=left,
                            title="Professional Role", location=right_col, bullets=[],
                        )
                        experiences.append(current_exp)
                        current_exp_has_content = False
                else:
                    if current_exp is None:
                        exp_counter += 1
                        current_exp = Experience(
                            id=f"exp_{exp_counter:03d}",
                            company="Professional Experience",
                            title="Role",
                            bullets=[],
                        )
                        experiences.append(current_exp)

                    bullet_counter += 1
                    bullet_id = f"{current_exp.id}_b{bullet_counter:02d}"
                    bullet = ResumeBullet(id=bullet_id, text=text, source_location_id=block.id)
                    current_exp.bullets.append(bullet)
                    current_exp_has_content = True

                    ev_id = f"ev_{ev_counter:04d}"
                    ev_counter += 1
                    evidence_list.append(Evidence(
                        id=ev_id,
                        source_type="experience",
                        # Link evidence to the canonical bullet id and also retain raw block id
                        source_id=bullet_id,
                        source_location_id=block.id,
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
                        source_location_id=block.id,
                        text=f"Project ({current_proj.name}): {text}",
                    ))

            # Skills section
            elif any(k in section_lower for k in ("skill", "technolog", "competenc", "expertise", "tools")):
                parts = text.split(":", 1)
                category = parts[0].strip() if len(parts) > 1 else "Skills"
                raw_skills_text = parts[1] if len(parts) > 1 else parts[0]
                # Parenthesis-aware split: "Python (pandas, scikit-learn,
                # transformers)" must stay one skill entry, not four.
                skills_list = self._split_respecting_parens(raw_skills_text, ",;|*•\n")
                
                if category not in skills_dict:
                    skills_dict[category] = []
                skills_dict[category].extend(skills_list)
                
                for skill in skills_list:
                    ev_id = f"ev_{ev_counter:04d}"
                    ev_counter += 1
                    evidence_list.append(Evidence(
                        id=ev_id,
                        source_type="skill",
                        # Skills are not always tied to a semantic node; store a generated id
                        source_id=f"skill_{ev_counter:04d}",
                        source_location_id=block.id,
                        text=skill,
                    ))

            # Education section
            elif any(k in section_lower for k in ("education", "academic", "qualification", "degree", "university")):
                has_date = bool(self.DATE_PATTERN.search(text))
                if "\t" in text:
                    left, right_col = [p.strip() for p in text.split("\t", 1)]
                else:
                    left, right_col = text, None

                body = self._strip_date_range(left)
                dates = right_col if (right_col and self.DATE_PATTERN.search(right_col)) else (
                    self._extract_date_range(left) if has_date else None
                )
                dash_parts = [p.strip() for p in re.split(r"\s+—\s+|\s+-\s+", body) if p.strip()]

                if current_edu is None or (current_edu.institution and current_edu.degree):
                    edu_counter += 1
                    edu_id = f"edu_{edu_counter:03d}"
                    if has_date and len(dash_parts) >= 2:
                        # Combined single line: "<Degree> — <Institution> (<dates>)"
                        current_edu = Education(
                            id=edu_id, degree=dash_parts[0], institution=dash_parts[1],
                            location=right_col if right_col and right_col != dates else None,
                            dates=dates,
                        )
                    elif has_date:
                        current_edu = Education(id=edu_id, institution=body, degree="", location=right_col, dates=dates)
                    else:
                        # No date on this line yet — treat as the institution
                        # (+ location) line; a following line may complete it
                        # with the degree (+ dates).
                        current_edu = Education(id=edu_id, institution=body, degree="", location=right_col, dates=None)
                    education_list.append(current_edu)
                elif not current_edu.degree:
                    current_edu.degree = body
                    if dates:
                        current_edu.dates = dates
                    if right_col and not current_edu.location:
                        current_edu.location = right_col
                else:
                    current_edu.degree = f"{current_edu.degree}; {body}".strip("; ")

                ev_id = f"ev_{ev_counter:04d}"
                ev_counter += 1
                evidence_list.append(Evidence(
                    id=ev_id,
                    source_type="education",
                    source_id=current_edu.id,
                    source_location_id=block.id,
                    text=text,
                ))

            # Certifications / interests / awards section
            elif any(k in section_lower for k in ("certification", "interest", "award", "achievement", "activit")):
                lowered_text = text.lower()
                # Decide the bucket from the SECTION heading first (e.g. a
                # block under "INTERESTS" belongs in interests even though
                # the line itself is just "Graphic Design • Badminton...").
                # A line's own "Awards: ..." / "Interests: ..." prefix is
                # only used as a tie-breaker for a section that mixes
                # categories (e.g. "Certifications & Awards").
                if "interest" in section_lower or lowered_text.startswith("interest"):
                    remainder = text.split(":", 1)[1] if ":" in text else text
                    interests.extend(self._split_respecting_parens(remainder))
                elif any(k in section_lower for k in ("award", "achievement", "activit")) or lowered_text.startswith(("award", "achievement")):
                    remainder = text.split(":", 1)[1] if ":" in text else text
                    achievements.extend(self._split_respecting_parens(remainder))
                elif "certif" in section_lower or lowered_text.startswith("certif"):
                    remainder = text.split(":", 1)[1] if ":" in text else text
                    for cert in self._split_respecting_parens(remainder):
                        certifications.append({"name": cert})
                else:
                    certifications.append({"name": text})

                ev_id = f"ev_{ev_counter:04d}"
                ev_counter += 1
                evidence_list.append(Evidence(
                    id=ev_id,
                    source_type="general",
                    source_id=block.id,
                    source_location_id=block.id,
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
                    source_location_id=block.id,
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
            certifications=certifications,
            achievements=achievements,
            interests=interests,
        )

        # Wrap into ResumeDocument (single source of truth)
        resume_doc = ResumeDocument(resume=resume)
        resume_doc.record_revision(rev_id="import_0001", actor="import", original=None, rewritten=None, evidence_ids=[e.id for e in evidence_list], source=raw_doc.filename)

        return resume_doc, evidence_list
