import re
from typing import List, Optional, Tuple
from app.domain.evidence import Evidence
from app.domain.resume import Candidate, Education, Experience, Project, Resume, ResumeBullet, Role
from app.domain.resume_document import ResumeDocument
from app.ingestion.docx import RawDocument

class ResumeNormalizer:
    # Whole month names/abbreviations only: "Mar[a-z]*" used to match
    # "Market", "Decision", "Junior" and turn project headings into job lines.
    _MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
              r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
    DATE_PATTERN = re.compile(
        r"\b(?:19|20)\d{2}\b|\b" + _MONTH + r"\b\.?|\b(?:Present|Current)\b",
        re.IGNORECASE,
    )
    # A job line's dates always carry a year or "Present".
    YEAR_OR_PRESENT = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:Present|Current|Now)\b", re.IGNORECASE)
    # Trailing "<start> - <end>" / "(<start> - <end>)" date-range pattern, e.g.
    # "August 2024 - Present", "(2014 – 2018)" or "2019 to 2023". Only a month
    # name may precede the year ("Engineer 2019 - 2023" keeps "Engineer").
    DATE_RANGE_RE = re.compile(
        r"\(?\s*((?:\b" + _MONTH + r"\.?,?\s*)?\d{4})\s*(?:[-–—]|\bto\b)\s*"
        r"((?:\b" + _MONTH + r"\.?,?\s*)?\d{4}|Present|Current|Now)\s*\)?\s*$",
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

    # Where a new "Label:" starts inside a skills line, e.g. the gap before
    # "Frameworks:" in "Languages: Python, SQL<tab>Frameworks: Pandas". A single
    # capitalised word right before the colon, so "SQL Frameworks:" splits
    # before "Frameworks", not before "SQL".
    _SKILL_LABEL_SPLIT_RE = re.compile(r"\t+|\s{2,}|\s(?=[A-Z][A-Za-z/&+-]*:\s)")
    _LABEL_RE = re.compile(r"^([A-Za-z][\w &/+-]{0,30}):\s*(.*)$", re.DOTALL)

    def _split_skill_line(self, text: str) -> List[Tuple[str, List[str]]]:
        """'Languages: Python, SQL<tab>Frameworks: Pandas, and XGBoost' ->
        [('Languages', ['Python', 'SQL']), ('Frameworks', ['Pandas', 'XGBoost'])].
        An unlabelled line goes under 'Skills'."""
        result: List[Tuple[str, List[str]]] = []
        for segment in self._SKILL_LABEL_SPLIT_RE.split(text):
            segment = segment.strip()
            if not segment:
                continue
            m = self._LABEL_RE.match(segment)
            if m and m.group(2).strip():
                category, values = m.group(1).strip(), m.group(2)
            elif result:
                # A tab or double space inside one category's list, not a new label.
                result[-1][1].extend(self._skill_items(segment))
                continue
            else:
                category, values = "Skills", segment
            result.append((category, self._skill_items(values)))
        return result

    def _skill_items(self, values: str) -> List[str]:
        # Parenthesis-aware split: "Python (pandas, scikit-learn,
        # transformers)" must stay one skill entry, not four. A list's last
        # item often reads "and XGBoost".
        items = self._split_respecting_parens(values, ",;|*•\n")
        return [re.sub(r"^(?:and|&)\s+", "", item, flags=re.IGNORECASE) for item in items]

    # Experience line kinds forced by an LLM structure hint (P1.13).
    _HINT_KINDS = {"company": "company", "job_title": "dated", "subheading": "subheading", "bullet": "content"}

    def _is_dated_line(self, block) -> bool:
        """A job title/company line carrying a date range or year."""
        if block is None or block.block_type in ("bullet", "name"):
            return False
        text = block.text.strip()
        return bool(text) and len(text) < 100 and bool(self.YEAR_OR_PRESENT.search(text))

    def _experience_line_kind(self, block, text: str) -> str:
        """'dated' (title and/or company with dates), 'header_line' (a short
        heading-like line without dates: a company, or a sub-heading inside a
        job) or 'content' (a bullet or body text)."""
        if block.block_type == "bullet":
            return "content"
        if self._is_dated_line(block):
            return "dated"
        left = text.split("\t", 1)[0]
        has_sep = "—" in left or " - " in left or " | " in left
        heading_like = block.block_type == "heading" or block.bold or has_sep or "\t" in text
        if heading_like and len(text) < 90 and not left.rstrip().endswith("."):
            return "header_line"
        return "content"

    @staticmethod
    def _add_role(exp: Experience, role: Role) -> None:
        """Record a role; the first one also fills the entry's title/dates."""
        if not exp.title and not exp.roles:
            exp.title, exp.start_date, exp.end_date = role.title, role.start_date, role.end_date
            return
        if not exp.roles:
            exp.roles.append(Role(title=exp.title, start_date=exp.start_date, end_date=exp.end_date))
        exp.roles.append(role)

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
        # True once current_exp has a bullet: distinguishes "still reading
        # this job's header lines" from "a new header line here means a new
        # job/company has started".
        current_exp_has_content = False
        # Sub-heading (e.g. a project name) the next experience bullets sit under.
        current_group: Optional[str] = None

        exp_counter = 0
        bullet_counter = 0
        proj_counter = 0
        edu_counter = 0
        ev_counter = 0

        def new_experience(company: str, location: Optional[str]) -> Experience:
            nonlocal exp_counter, current_exp_has_content
            exp_counter += 1
            exp = Experience(id=f"exp_{exp_counter:03d}", company=company, title="", location=location)
            experiences.append(exp)
            current_exp_has_content = False
            return exp

        blocks = raw_doc.blocks
        for idx, block in enumerate(blocks):
            text = block.text.strip()
            if not text:
                continue

            if block.block_type == "name" or block.hint == "name":
                candidate_name = text
                continue

            if block.hint and block.hint.startswith("section:"):
                current_section = block.hint.split(":", 1)[1]
                continue

            if block.block_type == "heading" and not block.hint:
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
                if "\t" in text:
                    left, right_col = [p.strip() for p in text.split("\t", 1)]
                else:
                    left, right_col = text, None
                kind = self._HINT_KINDS.get(block.hint or "")
                if kind is None:
                    kind = self._experience_line_kind(block, text)
                    if kind == "header_line" and self._is_dated_line(blocks[idx + 1] if idx + 1 < len(blocks) else None):
                        kind = "company"

                if kind == "dated":
                    title, start, end = self._parse_title_and_dates(left)
                    body = self._strip_date_range(left)
                    dash_parts = [p.strip() for p in re.split(r"\s+—\s+|\s+-\s+", body) if p.strip()]
                    role = Role(title=title, start_date=start, end_date=end)

                    if len(dash_parts) >= 2 and (current_exp is None or current_exp_has_content or current_exp.title):
                        # Combined single line: "Company — Title (dates)"
                        current_exp = new_experience(dash_parts[0], right_col)
                        self._add_role(current_exp, Role(title=dash_parts[1], start_date=start, end_date=end))
                    elif current_exp is None:
                        current_exp = new_experience("", right_col)
                        self._add_role(current_exp, role)
                    elif current_exp_has_content:
                        # A new title after bullets, with no company line in
                        # between: another role at the same company, listed
                        # with its own bullets.
                        current_exp = new_experience(current_exp.company, current_exp.location)
                        self._add_role(current_exp, role)
                    else:
                        # First role for a company header, or a second role
                        # (promotion) listed before any bullets.
                        self._add_role(current_exp, role)
                        if right_col and not current_exp.location:
                            current_exp.location = right_col
                    current_group = None

                elif kind == "company" or (kind == "header_line" and current_exp is None):
                    # "Northwind Analytics - A Contoso Company<tab>Pune, India"
                    current_exp = new_experience(left, right_col)
                    current_group = None

                elif kind == "header_line" and not current_exp.company and not current_exp_has_content:
                    # "Title, dates" came first; this line names the company.
                    current_exp.company = left
                    if right_col and not current_exp.location:
                        current_exp.location = right_col

                elif kind in ("header_line", "subheading"):
                    # A sub-heading inside the job, e.g. a project name.
                    current_group = re.sub(r"\s+", " ", text).strip()

                else:
                    if current_exp is None:
                        current_exp = new_experience("", None)

                    text = re.sub(r"\s+", " ", text)
                    bullet_counter += 1
                    bullet_id = f"{current_exp.id}_b{bullet_counter:02d}"
                    bullet = ResumeBullet(id=bullet_id, text=text, source_location_id=block.id, group=current_group)
                    current_exp.bullets.append(bullet)
                    current_exp_has_content = True

                    ev_id = f"ev_{ev_counter:04d}"
                    ev_counter += 1
                    context = current_exp.company or current_exp.title or "Experience"
                    if current_group:
                        context = f"{context} — {current_group}"
                    evidence_list.append(Evidence(
                        id=ev_id,
                        source_type="experience",
                        # Link evidence to the canonical bullet id and also retain raw block id
                        source_id=bullet_id,
                        source_location_id=block.id,
                        text=f"{context}: {text}",
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
                skills_list = []
                for category, items in self._split_skill_line(text):
                    skills_dict.setdefault(category, []).extend(items)
                    skills_list.extend(items)

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
                # A line's own label ("Certifications: ...", "Interests: ...")
                # decides the bucket; otherwise the section heading does.
                # A mixed "CERTIFICATIONS & INTERESTS" section must not file
                # labelled certifications as interests.
                label_match = self._LABEL_RE.match(text)
                label = label_match.group(1).lower() if label_match else ""
                bucket_key = label if any(
                    k in label for k in ("interest", "hobb", "award", "achievement", "activit", "certif", "licen")
                ) else section_lower
                remainder = label_match.group(2) if label_match and label == bucket_key else text
                items = self._split_respecting_parens(remainder)
                if "certif" in bucket_key or "licen" in bucket_key:
                    bucket, source_type = "certifications", "certification"
                elif "interest" in bucket_key or "hobb" in bucket_key:
                    bucket, source_type = "interests", "general"
                elif any(k in bucket_key for k in ("award", "achievement", "activit")):
                    bucket, source_type = "achievements", "achievement"
                else:
                    bucket, source_type = "certifications", "certification"
                if bucket == "certifications":
                    certifications.extend({"name": item} for item in items)
                elif bucket == "interests":
                    interests.extend(items)
                else:
                    achievements.extend(items)

                ev_id = f"ev_{ev_counter:04d}"
                ev_counter += 1
                evidence_list.append(Evidence(
                    id=ev_id,
                    source_type=source_type,
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
