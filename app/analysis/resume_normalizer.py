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
    # A URL written out in the text: "linkedin.com/in/x", "https://github.com/x".
    URL_RE = re.compile(
        r"(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+(?:com|in|io|dev|me|org|net|ai|co|app|page)(?:/[^\s|,;]*)?",
        re.IGNORECASE,
    )
    # Words that make a header segment a contact item, not a headline.
    CONTACT_WORDS_RE = re.compile(
        r"\b(?:linkedin|github|gitlab|leetcode|kaggle|portfolio|website|email|e-mail|phone|mobile|tel)\b",
        re.IGNORECASE,
    )
    LOCATION_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]*,\s*[A-Za-z][A-Za-z .'-]*$")

    def _header_urls(self, text: str) -> List[str]:
        urls = []
        for m in self.URL_RE.finditer(text):
            url = m.group(0).rstrip(".)")
            # Skip the domain part of an email address.
            if m.start() > 0 and text[m.start() - 1] == "@":
                continue
            if "/" in url or url.lower().startswith(("http", "www.")):
                urls.append(url)
        return urls

    def _is_headline(self, text: str) -> bool:
        """A short title line under the name, e.g. 'Senior Data Scientist |
        MLOps'. Contact lines, links and a bare location don't count."""
        if len(text) > 90 or "@" in text or self.PHONE_RE.search(text) or self.URL_RE.search(text):
            return False
        if self.CONTACT_WORDS_RE.search(text) or self.LOCATION_RE.match(text.strip()):
            return False
        if text.rstrip().endswith("."):  # a sentence: summary text without a heading
            return False
        return any(c.isalpha() for c in text)

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
        "project", "projects", "portfolio", "portfolios",
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

    # A heading with a section keyword is a section title ("Internship
    # Experience", "Licenses & Certifications", "Programming Skills")
    # unless it reads as content: a school name ("Riverside Institute of
    # Technology") or a long line.
    _CONTENT_HEADING_RE = re.compile(
        r"\b(?:university|institute|college|school|academy|inc|ltd|llc|corp|corporation|gmbh|pvt)\b\.?",
        re.IGNORECASE)

    # Keywords that are also part of institution names; a heading whose only
    # keywords are these and which names an institution is content.
    _NAME_KEYWORDS = {"technology", "technologies", "technological", "university"}

    def _is_section_title(self, text: str) -> bool:
        keywords = {m.group(0).lower() for m in self.SECTION_KEYWORDS_RE.finditer(text)}
        if not keywords:
            return False
        words = [w for w in re.split(r"[\s,:/()&]+", text) if w]
        if len(words) > 6:
            return False
        # "Riverside Institute of Technology" is a school; "University
        # Projects" is still a Projects section.
        return not (keywords <= self._NAME_KEYWORDS and self._CONTENT_HEADING_RE.search(text))

    # "Senior Data Scientist", "Software Engineering Intern": the title side
    # of a "Title | Company" or "Company — Title" job line.
    _ROLE_WORDS_RE = re.compile(
        r"\b(?:engineer|engineering|developer|scientist|analyst|manager|intern|internship|teacher|designer|"
        r"consultant|lead|director|administrator|architect|specialist|officer|associate|assistant|head|vp|"
        r"president|founder|co-founder|coordinator|executive|researcher|fellow|trainee|technician|"
        r"programmer|owner|principal|staff|sde|sre|devops|writer|editor|accountant|advisor|tutor)\b",
        re.IGNORECASE)

    def _looks_like_title(self, text: str) -> bool:
        return bool(self._ROLE_WORDS_RE.search(text or ""))

    def _split_title_company(self, body: str) -> Tuple[str, str]:
        """'Title | Company | Place', 'Company — Title', 'Title — Team — Company'
        -> (title, company). The most title-like part is the title. With
        pipes, the company is the first other pipe segment (a trailing
        location is ignored); with dashes only, the last other part."""
        split_dash = lambda t: [p.strip() for p in re.split(r"\s+—\s+|\s+-\s+", t) if p.strip()]
        segments = [seg.strip() for seg in re.split(r"\s+\|\s+", body) if seg.strip()]
        parts = [p for seg in segments for p in split_dash(seg)]
        scores = [self._title_score(p) for p in parts]
        if len(set(scores)) == 1:  # nothing to tell them apart: "Company — Title"
            return parts[1], parts[0]
        title = parts[scores.index(max(scores))]
        if len(segments) >= 2:
            others = [seg for seg in segments if title not in split_dash(seg)]
            return title, split_dash(others[0])[0]
        return title, [p for p in parts if p is not title][-1]

    def _title_score(self, text: str) -> int:
        """2 when a role word ends the phrase ("Data Analyst"), 1 when it's
        only inside it ("Lead Bank", "Principal Financial Group"), else 0."""
        words = re.findall(r"[A-Za-z-]+", text or "")
        if words and self._ROLE_WORDS_RE.fullmatch(words[-1]):
            return 2
        return 1 if self._looks_like_title(text) else 0

    # Chars trimmed off a title/company fragment once the trailing date range
    # (and whatever separated it, e.g. "Title | Aug 2024 - Present") has been
    # removed. Missing "|" here left literal pipes baked into every title
    # for resumes that separate title from dates with " | " rather than ",".
    _TRIM_CHARS = " \t,|()-–—"

    # Where a new "Label:" starts inside a skills line, e.g. the gap before
    # "Frameworks:" in "Languages: Python, SQL<tab>Frameworks: Pandas". A single
    # capitalised word right before the colon, so "SQL Frameworks:" splits
    # before "Frameworks", not before "SQL".
    # Never right after "&", "/" or "and": "Frameworks & Tools:" is one label.
    _SKILL_LABEL_SPLIT_RE = re.compile(r"\t+|\s{2,}|(?<![&/])(?<!\band)\s(?=[A-Z][A-Za-z/&+-]*:\s)")
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

    _DEGREE_RE = re.compile(
        r"\b(?:B\.?\s?(?:Tech|Ed|E|Sc|S|A|Com)|M\.?\s?(?:Tech|Ed|E|Sc|S|A|Com)|Bachelor|Master|Ph\.?\s?D|MBA|BBA|BCA|MCA"
        r"|Diploma|Certificate|Associate(?:'s)? (?:of|in|degree))\b", re.IGNORECASE)
    _INSTITUTION_RE = re.compile(r"\b(?:University|Institute|College|School|Academy|IIT|NIT)\b", re.IGNORECASE)

    def _looks_like_degree(self, text: str) -> bool:
        """'B.Tech in Computer Science' yes; 'State University' no."""
        return bool(self._DEGREE_RE.search(text)) and not self._INSTITUTION_RE.search(text)

    @staticmethod
    def _split_middle_dot(text: str) -> Tuple[str, Optional[str]]:
        """'Acme Corp · Pune, India' -> ('Acme Corp', 'Pune, India'), the
        ATS template's company / institution line."""
        if " · " in text:
            main, rest = text.split(" · ", 1)
            if main.strip() and rest.strip():
                return main.strip(), rest.strip()
        return text, None

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
        if len(text) <= 60 and not left.rstrip().endswith("."):
            # A short plain line: a company only if a dated line follows.
            return "maybe_company"
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

    @staticmethod
    def _merge_links(text_urls: List[str], file_links: List[str]) -> List[str]:
        """Profile links from the file's hyperlinks and from URLs written in
        the header. mailto:/tel: targets are contact details, not links."""
        merged: List[str] = []
        seen = set()
        for url in list(file_links) + list(text_urls):
            if not url or url.lower().startswith(("mailto:", "tel:")):
                continue
            key = re.sub(r"^(?:https?://)?(?:www\.)?", "", url.lower()).rstrip("/")
            if key and key not in seen:
                seen.add(key)
                merged.append(url)
        return merged

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
        candidate_headline = None
        candidate_links: List[str] = []

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

        # Jobs whose company was carried over from the previous entry (a new
        # title after bullets); a company line right after the title wins.
        inherited_company: set = set()

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
                if self._is_section_title(text):
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
                is_name_line = False
                if "@" not in text and not phone_match and len(text) < 40 and candidate_name == "Candidate":
                    candidate_name = text
                    is_name_line = True
                for url in self._header_urls(text):
                    if url not in candidate_links:
                        candidate_links.append(url)
                if ("header" in section_lower and not is_name_line and candidate_headline is None
                        and candidate_name != "Candidate" and text != candidate_name and self._is_headline(text)):
                    candidate_headline = text
                    evidence_list.append(Evidence(
                        id=f"ev_{ev_counter:04d}", source_type="summary",
                        source_id=block.id, source_location_id=block.id, text=text,
                    ))
                    ev_counter += 1
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
                    left, right_col = self._split_middle_dot(text)
                kind = self._HINT_KINDS.get(block.hint or "")
                if (kind is None and current_exp is not None and current_exp.title
                        and (not current_exp.company or current_exp.id in inherited_company)
                        and not current_exp_has_content and block.block_type != "bullet"
                        and len(text) < 90 and not left.rstrip().endswith(".")
                        and not self._is_dated_line(block)):
                    # Title line first, then "Company · Location" (the ATS
                    # template's order): this line names the job's company.
                    kind = "company_of_current"
                if kind is None:
                    kind = self._experience_line_kind(block, text)
                    next_is_dated = self._is_dated_line(blocks[idx + 1] if idx + 1 < len(blocks) else None)
                    if kind in ("header_line", "maybe_company") and next_is_dated:
                        kind = "company"
                    elif kind == "maybe_company":
                        kind = "content"

                if kind == "dated":
                    title, start, end = self._parse_title_and_dates(left)
                    if start is None and right_col and self.DATE_RANGE_RE.search(right_col):
                        # "Title<tab>Aug 2024 – Present": the dates are the
                        # right column, not a location.
                        _, start, end = self._parse_title_and_dates(right_col)
                        right_col = None
                    body = self._strip_date_range(left)
                    dash_parts = [p.strip() for p in re.split(r"\s+—\s+|\s+-\s+|\s+\|\s+", body) if p.strip()]
                    role = Role(title=title, start_date=start, end_date=end)

                    if len(dash_parts) >= 2 and (current_exp is None or current_exp_has_content or current_exp.title):
                        # Combined single line: "Company — Title (dates)" or
                        # "Title | Company | dates"; role words decide which is which.
                        # The most title-like part is the title; the company is
                        # the last remaining part ("Title - Team | Company").
                        title_part, company_part = self._split_title_company(body)
                        current_exp = new_experience(company_part, right_col)
                        self._add_role(current_exp, Role(title=title_part, start_date=start, end_date=end))
                    elif current_exp is None:
                        current_exp = new_experience("", right_col)
                        self._add_role(current_exp, role)
                    elif current_exp_has_content:
                        # A new title after bullets, with no company line in
                        # between: another role at the same company, listed
                        # with its own bullets.
                        current_exp = new_experience(current_exp.company, current_exp.location)
                        inherited_company.add(current_exp.id)
                        self._add_role(current_exp, role)
                    else:
                        # First role for a company header, or a second role
                        # (promotion) listed before any bullets.
                        self._add_role(current_exp, role)
                        if right_col and not current_exp.location:
                            current_exp.location = right_col
                    current_group = None

                elif kind == "company_of_current":
                    if current_exp.id in inherited_company:
                        inherited_company.discard(current_exp.id)
                        current_exp.location = None
                    current_exp.company = left
                    if right_col and not current_exp.location:
                        current_exp.location = right_col

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
                    left, right_col = self._split_middle_dot(text)

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
                    elif has_date and self._looks_like_degree(body):
                        # "B.Tech in X<tab>2016 – 2020", institution on the next line
                        current_edu = Education(id=edu_id, institution="", degree=body, dates=dates,
                                                location=right_col if right_col and right_col != dates else None)
                    elif has_date:
                        current_edu = Education(id=edu_id, institution=body, degree="", location=right_col, dates=dates)
                    else:
                        # No date on this line yet — treat as the institution
                        # (+ location) line; a following line may complete it
                        # with the degree (+ dates).
                        current_edu = Education(id=edu_id, institution=body, degree="", location=right_col, dates=None)
                    education_list.append(current_edu)
                elif not current_edu.institution:
                    current_edu.institution = body
                    if right_col and not current_edu.location and right_col != dates:
                        current_edu.location = right_col
                elif not current_edu.degree:
                    current_edu.degree = body
                    if dates:
                        current_edu.dates = dates
                    if right_col and not current_edu.location and right_col != dates:
                        current_edu.location = right_col  # a place, never the date column
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

            # Short header lines (name, contact, headline, links) were handled
            # above; they aren't evidence of experience.
            elif "header" in section_lower and len(text) <= 90:
                pass

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

        if candidate_email is None:
            mailto = next((l for l in raw_doc.links if l.lower().startswith("mailto:")), None)
            if mailto:
                candidate_email = mailto.split(":", 1)[1].split("?", 1)[0] or None
        candidate = Candidate(
            name=candidate_name,
            email=candidate_email,
            phone=candidate_phone,
            location=candidate_location,
            headline=candidate_headline,
            links=self._merge_links(candidate_links, raw_doc.links),
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
