import re
from typing import List, Optional, Tuple
from app.domain.evidence import Evidence
from app.domain.resume import (Candidate, Education, Experience, OtherSection, Project, Resume, ResumeBullet, Role,
                               SectionLine)
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
    # A phone number in any common grouping (P8.4): "(602) 555-0147",
    # "+33 6 12 34 56 78", "+49 30 12345678", "+91 98765 43210", "216-555-0110".
    # Candidates are checked by find_phone(): 8-15 digits, not a year range
    # or a dotted date.
    PHONE_RE = re.compile(
        r"(?<![\w/.+-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{1,4}\)[\s.-]?)?\d{1,12}(?:[\s.-]\d{1,12}){0,5}(?![\w/])")
    # A URL written out in the text: "linkedin.com/in/x", "https://github.com/x".
    # Common generic and country top-level domains (P8.4: portfolio sites such
    # as "name.design" were dropped). A fixed list keeps "B.Sc", "e.g." and
    # "Node.js" from reading as links.
    _TLDS = ("com|net|org|io|dev|me|ai|co|app|page|design|art|studio|site|online|tech|xyz|info|biz|blog|link|"
             "portfolio|work|works|pro|name|codes|cloud|digital|space|website|tv|fm|edu|gov|ac|us|uk|ca|de|fr|"
             "es|it|nl|eu|in|au|nz|jp|cn|sg|ch|se|no|dk|fi|pl|pt|br|mx|ie|be|at|za|ng|ke|ae|il|kr|hk|tw|my|ph")
    URL_RE = re.compile(
        r"(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+(?:" + _TLDS + r")(?![a-z0-9-])(?:/[^\s|,;·]*)?",
        re.IGNORECASE,
    )

    @classmethod
    def find_phone(cls, text: str) -> Optional[str]:
        """The first phone number in a line, as written, or None."""
        for m in cls.PHONE_RE.finditer(text or ""):
            candidate = m.group(0).strip(" .-")
            digits = re.sub(r"\D", "", candidate)
            if not 8 <= len(digits) <= 15:
                continue
            groups = re.findall(r"\d+", candidate)
            if all(re.fullmatch(r"(?:19|20)\d{2}", g) for g in groups):
                continue  # "2019-2023"
            if "." in candidate and [len(g) for g in groups] in ([2, 2, 4], [1, 2, 4], [2, 1, 4]):
                continue  # "14.03.1990"
            return candidate
        return None
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
            urls.append(url)
        return urls

    def _is_headline(self, text: str) -> bool:
        """A short title line under the name, e.g. 'Senior Data Scientist |
        MLOps'. Contact lines, links and a bare location don't count."""
        if len(text) > 90 or "@" in text or self.find_phone(text) or self.URL_RE.search(text):
            return False
        if self.CONTACT_WORDS_RE.search(text) or self.LOCATION_RE.match(text.strip()):
            return False
        if text.rstrip().endswith("."):  # a sentence: summary text without a heading
            return False
        if ":" in text:  # "Security Clearance: Active Secret" is a detail, not a title
            return False
        return any(c.isalpha() for c in text)

    # -- section headings (P8.3) ----------------------------------------------

    # Words that name a section, checked in this order (the first match
    # wins, in the order the sections were always checked: "Research
    # Interests" is kept as is, "Career Objective" is a summary, "Academic
    # Appointments" is experience, "Academic Projects" is projects,
    # "Education & Training" is education). Words from before P8.3 switch section on any heading;
    # the newer ones only on a line styled like the document's own section
    # headings, so a bold "Languages" label inside Skills stays a label.
    _KIND_WORDS = (
        ("other", r"research interests?"),
        ("summary", r"summary|profile|about|objective"),
        ("experience", r"experience|work|employment|career|history|journey|appointments?|positions"),
        ("projects", r"projects?|portfolios?"),
        ("skills", r"skills?|technology|technologies|technological|competency|competencies|expertise|tools"
                   r"|proficienc(?:y|ies)"),
        ("education", r"education|academic|academics|qualifications?|university|degrees?|coursework|schooling"),
        ("certifications", r"certifications?|certificates?|licen[cs]es?|licensure|credentials"),
        ("interests", r"interests?|hobbies|hobby"),
        ("achievements", r"awards?|achievements?|honou?rs|activity|activities|accomplishments"),
        ("other", r"publications?|presentations?|talks|conferences?|grants?|funding|teaching|service"
                  r"|memberships?|affiliations?|associations?|references?|volunteer(?:ing)?|languages?"
                  r"|admissions?|rotations?|training|personal|declaration|military|clearances?|board|advisory"
                  r"|patents?|additional|information|other"),
    )
    _KIND_RES = [(kind, re.compile(r"\b(?:" + words + r")\b", re.IGNORECASE)) for kind, words in _KIND_WORDS]
    _GATED_WORDS_RE = re.compile(
        r"\b(?:journey|appointments?|positions|academics|degrees?|coursework|schooling|licen[cs]es?|licensure"
        r"|credentials|proficienc(?:y|ies)|hobbies|hobby|honou?rs|accomplishments|publications?|presentations?"
        r"|talks|conferences?|grants?|funding|teaching|service|memberships?|affiliations?|associations?"
        r"|references?|volunteer(?:ing)?|languages?|admissions?|rotations?|training|personal|declaration"
        r"|military|clearances?|board|advisory|patents?|additional|information|other|research interests?)\b",
        re.IGNORECASE)

    @classmethod
    def section_kind(cls, text: str) -> Optional[str]:
        """'Clinical Rotations' -> 'other', 'Work History' -> 'experience',
        'Licenses' -> 'certifications'; None when no section word is in it."""
        for kind, pattern in cls._KIND_RES:
            if pattern.search(text or ""):
                return kind
        return None

    @staticmethod
    def _heading_sig(block) -> Tuple:
        """How a heading line is set: capitals, bold, size, Word style."""
        text = block.text.strip()
        style = (getattr(block.location, "style_name", "") or "").lower()
        return (text.isupper(), bool(block.bold), round(block.font_size or 0), style.startswith(("heading", "title")))

    def _section_heading_sigs(self, blocks) -> set:
        """The look of the lines this document uses as section headings."""
        return {self._heading_sig(b) for b in blocks
                if b.block_type == "heading" and not b.hint and self._is_section_title(b.text.strip())}

    def _styled_as_heading(self, block, text: str, sigs: set) -> bool:
        """Set like the document's section headings, or (when none was
        recognised, e.g. every heading is in German) a short all-caps line."""
        if block.block_type != "heading":
            return False
        if sigs:
            return self._heading_sig(block) in sigs
        return text.isupper() or self._heading_sig(block)[3]

    _HEADING_SHAPE_RE = re.compile(r"^[^\W\d_][\w &/'’.-]*:?$")

    def _heading_kind(self, block, text: str, sigs: set, current_kind: str, blocks, idx: int,
                      name_known: bool = True) -> Optional[str]:
        """The section a heading line starts, or None when the line is content."""
        if block.block_type != "heading":
            return None
        words = [w for w in re.split(r"[\s,:/()&]+", text) if w]
        if self._is_section_title(text):  # a word from before P8.3: switches on any heading line
            return self.section_kind(text)
        if not name_known and current_kind == "header":
            return None  # the first bold line is the name
        if len(words) > 6 or not self._HEADING_SHAPE_RE.match(text):
            return None  # dates, pipes, commas: a job or entry line
        if not self._styled_as_heading(block, text, sigs):
            return None
        # Bold mixed-case lines are also employers, schools, projects and
        # skill labels; only an all-caps or Word-heading line names a
        # section the vocabulary doesn't know, or one inside Skills.
        strong = text.isupper() or self._heading_sig(block)[3]
        kind = self.section_kind(text)
        if kind and not (kind == "education" and self._CONTENT_HEADING_RE.search(text)):
            return kind if strong or current_kind != "skills" else None
        # Any other heading set like the document's own: a section to keep
        # as it is, unless it's an all-caps employer with a dated line
        # right after it, or a sub-heading over bullets inside a job.
        if len(words) > 5 or not strong:
            return None
        if current_kind in ("experience", "projects"):
            following = [b for b in blocks[idx + 1: idx + 4] if b.text.strip()]
            if any(self._is_dated_line(b) for b in following) or (following and following[0].block_type == "bullet"):
                return None
        return "other"

    @staticmethod
    def _display_heading(text: str) -> str:
        """'CLINICAL ROTATIONS' -> 'Clinical Rotations'; mixed case kept."""
        text = re.sub(r"\s+", " ", text).strip().rstrip(":")
        return text.title() if text.isupper() else text

    # -- header lines (P8.3, P8.7) -----------------------------------------

    @staticmethod
    def _header_segments(text: str) -> List[str]:
        """'Austin, TX · a@b.com · 512-555-0199' -> its parts."""
        return [seg.strip() for seg in re.split(r"\s*[|•·]\s*|\s{3,}|\t", text) if seg.strip()]

    def _looks_like_name(self, text: str) -> bool:
        words = text.split()
        return (1 <= len(words) <= 5 and len(text) < 40 and "@" not in text and not re.search(r"\d", text)
                and not self.URL_RE.search(text) and not self.CONTACT_WORDS_RE.search(text)
                and not self._is_section_title(text) and not self._looks_like_title(text)
                and all(w[:1].isupper() for w in words if w[:1].isalpha()))

    # "City, State" / "City, Country", or "City ST" with a US state code.
    _CITY_STATE_RE = re.compile(r"^[^\W\d_][\w .'-]*\s[A-Z]{2}$")

    def _looks_like_location(self, text: str) -> bool:
        text = text.strip()
        return bool(self.LOCATION_RE.match(text) or self._CITY_STATE_RE.match(text)) and len(text) <= 40

    def _is_detail(self, segment: str) -> bool:
        """A header part worth keeping as is: not contact data (email,
        phone, a link) and not a bare placeholder ("LinkedIn", "Email")."""
        if "@" in segment or self.URL_RE.search(segment):
            return False
        phone = self.find_phone(segment)
        if phone and not re.sub(re.escape(phone), "", segment).strip(" :.-"):
            return False
        rest = self.CONTACT_WORDS_RE.sub("", segment)
        if phone:
            rest = rest.replace(phone, "")
        return bool(re.search(r"\w", rest.strip(" :|-")))

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

    # A list piece that is a date or an expiry, not an item of its own:
    # "Certified Public Accountant (CPA), New York, 2021" is one entry.
    _DATE_PIECE_RE = re.compile(
        r"^(?:(?:exp(?:ires|iry|\.)?|valid(?: until)?|since|issued)\b.*|[\d/.\s–-]+|(?:\w+\.?\s)?(?:19|20)\d{2})$",
        re.IGNORECASE)

    def _split_list_items(self, text: str) -> List[str]:
        """Items of a certification / award line. ';' always separates
        entries; ',' only when no piece is a date, an expiry or a place, so
        "Registered Nurse (RN), Arizona State Board of Nursing, License
        #RN123456, exp. 06/2027" stays one licence (P8.3)."""
        entries = self._split_respecting_parens(text, ";|•\n")
        if len(entries) > 1:
            return entries  # "Treasurer, BU Statistics Club; Teaching Assistant, MA 113"
        items: List[str] = []
        for entry in entries:
            pieces = self._split_respecting_parens(entry, ",")
            if len(pieces) > 1 and not any(
                    self._DATE_PIECE_RE.match(p) or p.lower().startswith(("license", "licence", "#", "no."))
                    or self._looks_like_location(p) or len(p.split()) > 6 for p in pieces):
                items.extend(pieces)
            else:
                items.append(entry)
        return items

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
        section_headings: List[str] = []
        header_blocks: List[str] = []

        candidate_name = "Candidate"
        candidate_email = None
        candidate_phone = None
        candidate_location = None
        candidate_headline = None
        candidate_links: List[str] = []

        current_section = "Header"
        other_sections: List[OtherSection] = []
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
        heading_sigs = self._section_heading_sigs(blocks)
        current_kind = "header"
        current_other: Optional[OtherSection] = None
        candidate_details: List[str] = []
        for idx, block in enumerate(blocks):
            text = block.text.strip()
            if not text:
                continue

            if block.block_type == "name" or block.hint == "name":
                candidate_name = text
                continue

            heading_kind = None
            if block.hint and block.hint.startswith("section:"):
                hinted = block.hint.split(":", 1)[1]
                heading_kind = "other" if hinted.lower() == "other" else (self.section_kind(hinted) or "other")
            elif not block.hint:
                heading_kind = self._heading_kind(block, text, heading_sigs, current_kind, blocks, idx,
                                                  name_known=candidate_name != "Candidate")
            if heading_kind:
                current_section, current_kind = text, heading_kind
                if heading_kind == "other":
                    current_other = OtherSection(id=f"sec_{len(other_sections) + 1:02d}",
                                                 heading=self._display_heading(text))
                    other_sections.append(current_other)
                section_headings.append(text)
                continue

            section_lower = current_section.lower()

            # Header / Candidate info parsing
            if current_kind == "header" or block.location.paragraph_index in (0, 1) or candidate_name == "Candidate":
                in_header = current_kind == "header"
                if in_header:
                    header_blocks.append(block.id)
                if "@" in text:
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                    if email_match and candidate_email is None:
                        candidate_email = email_match.group(0)
                phone_match = self.find_phone(text)
                if phone_match and candidate_phone is None:
                    candidate_phone = phone_match
                segments = self._header_segments(text)
                is_name_line = False
                if candidate_name == "Candidate":
                    if "@" not in text and not phone_match and len(text) < 40 and not self._is_section_title(text):
                        candidate_name, is_name_line = text, True
                    elif len(segments) > 1 and self._looks_like_name(segments[0]):
                        # "Lena Park · Product Designer · lena@example.com" in
                        # a page header: the first part is the name (P8.7).
                        candidate_name = segments[0]
                for url in self._header_urls(text):
                    if url not in candidate_links:
                        candidate_links.append(url)
                if in_header and candidate_location is None:
                    candidate_location = next((seg for seg in segments if self._looks_like_location(seg)), None)
                is_headline_line = False
                if (in_header and not is_name_line and candidate_headline is None
                        and candidate_name != "Candidate" and text != candidate_name):
                    if self._is_headline(text):
                        candidate_headline, is_headline_line = text, True
                    else:
                        # A title among contact items: "Name · Product Designer · email".
                        candidate_headline = next((seg for seg in segments if seg != candidate_name
                                                   and self._looks_like_title(seg) and self._is_headline(seg)), None)
                    if candidate_headline:
                        evidence_list.append(Evidence(
                            id=f"ev_{ev_counter:04d}", source_type="summary",
                            source_id=block.id, source_location_id=block.id, text=candidate_headline,
                        ))
                        ev_counter += 1
                if in_header and not is_name_line and not is_headline_line:
                    if len(segments) == 1 and len(text) > 90 and not phone_match and "@" not in text:
                        # A summary paragraph under the name with no heading.
                        current_kind, current_section = "summary", "Summary"
                    else:
                        consumed = {candidate_name, candidate_headline, candidate_location}
                        candidate_details.extend(seg for seg in segments if seg not in consumed
                                                 and seg not in candidate_details and self._is_detail(seg))

            # Summary section
            if current_kind == "summary":
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
            elif current_kind == "experience":
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
                    current_exp.source_blocks.append(block.id)

                elif kind == "company_of_current":
                    if current_exp.id in inherited_company:
                        inherited_company.discard(current_exp.id)
                        current_exp.location = None
                    current_exp.company = left
                    if right_col and not current_exp.location:
                        current_exp.location = right_col
                    current_exp.source_blocks.append(block.id)

                elif kind == "company" or (kind == "header_line" and current_exp is None):
                    # "Northwind Analytics - A Contoso Company<tab>Pune, India"
                    current_exp = new_experience(left, right_col)
                    current_group = None
                    current_exp.source_blocks.append(block.id)

                elif kind == "header_line" and not current_exp.company and not current_exp_has_content:
                    # "Title, dates" came first; this line names the company.
                    current_exp.company = left
                    if right_col and not current_exp.location:
                        current_exp.location = right_col
                    current_exp.source_blocks.append(block.id)

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
            elif current_kind == "projects":
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
            elif current_kind == "skills":
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
            elif current_kind == "education":
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
                        current_edu = Education(id=edu_id, institution=body, degree="", dates=dates,
                                                location=right_col if right_col and right_col != dates else None)
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
            elif current_kind in ("certifications", "interests", "achievements"):
                # A line's own label ("Certifications: ...", "Interests: ...")
                # decides the bucket; otherwise the section heading does.
                # A mixed "CERTIFICATIONS & INTERESTS" section must not file
                # labelled certifications as interests.
                label_match = self._LABEL_RE.match(text)
                label = label_match.group(1).lower() if label_match else ""
                bucket_key = label if any(
                    k in label for k in ("interest", "hobb", "award", "achievement", "activit", "certif", "licen")
                ) else {"certifications": "certif", "interests": "interest"}.get(current_kind, "award")
                remainder = label_match.group(2) if label_match and label == bucket_key else text
                items = self._split_list_items(remainder)
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
            elif current_kind == "header":
                pass

            # A section kept as it is (P8.3): the line goes in verbatim.
            elif current_kind == "other" and current_other is not None:
                current_other.lines.append(SectionLine(text=re.sub(r"\s+", " ", text), source_location_id=block.id,
                                                       bullet=block.block_type == "bullet"))
                evidence_list.append(Evidence(
                    id=f"ev_{ev_counter:04d}", source_type="other", source_id=current_other.id,
                    source_location_id=block.id, text=f"{current_other.heading}: {text}",
                ))
                ev_counter += 1

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
            details=candidate_details,
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
            other_sections=[sec for sec in other_sections if sec.lines],
        )

        # Wrap into ResumeDocument (single source of truth)
        resume_doc = ResumeDocument(resume=resume, section_headings=section_headings, header_blocks=header_blocks)
        resume_doc.record_revision(rev_id="import_0001", actor="import", original=None, rewritten=None, evidence_ids=[e.id for e in evidence_list], source=raw_doc.filename)

        return resume_doc, evidence_list
