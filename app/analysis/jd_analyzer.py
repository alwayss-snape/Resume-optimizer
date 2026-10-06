import os
import re
from typing import Dict, List, Optional, Tuple

from app.domain.job import JobDescription, Requirement
from app.llm.client import LLMClient
from app.llm.schemas import JDAnalysisResult

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "llm", "prompts", "jd_analysis.txt")

class JDAnalyzer:
    """Extract only text that is visibly present in the supplied job description."""

    STOP_WORDS = {
        "and", "the", "with", "for", "such", "as", "that", "this", "should", "have",
        "must", "required", "knowledge", "experience", "familiarity", "job", "role",
        "about", "description", "responsibilities", "requirements", "qualifications",
    }
    HEADING_RE = re.compile(
        r"^(about( the)? job|about us|what we offer|benefits|equal opportunity|"
        r"nice to have|who you are|what you.ll do|"
        r"(minimum|required|basic|desired|preferred|additional|other|key|core|"
        r"technical|essential|primary|general)?\s*"
        r"(responsibilit(y|ies)|requirements?|qualifications?|skills)"
        r")[:\s]*$",
        re.IGNORECASE,
    )
    REQUIREMENT_SIGNALS = (
        "must", "required", "requirement", "qualified", "qualification", "proficien",
        "experience", "years", "degree", "bachelor", "master", "phd", "responsible",
        "responsibilities", "develop", "design", "build", "manage", "lead", "create",
        "implement", "maintain", "analyze", "collaborate", "knowledge of", "ability to",
    )
    PREFERRED_SIGNALS = ("preferred", "nice to have", "optional", "bonus", "plus")
    # Words in a section heading that make everything under it preferred:
    # "Nice To Have, But Not Required", "Bonus Points", "Good to have".
    PREFERRED_HEADING_SIGNALS = ("nice to have", "good to have", "preferred", "bonus", "not required",
                                 "desired", "optional", "plus")
    # A short line containing one of these phrases is a section heading.
    HEADING_PHRASES_RE = re.compile(
        r"\b(?:about (?:the )?(?:role|job|team|us|company)|nice to have|good to have|bonus|"
        r"responsibilit(?:y|ies)|requirements?|qualifications?|what you(?:'|’)?(?:ll| will) (?:do|need|bring)|"
        r"who you are|what we offer|benefits|perks)\b",
        re.IGNORECASE,
    )
    # "Contoso Media is looking for a <title> to join ..." (F44).
    INTRO_RE = re.compile(
        r"(?P<company>[A-Z][\w&.'’-]*(?:\s+[A-Z][\w&.'’-]*){0,4})\s+(?:is|are)\s+"
        r"(?:looking for|hiring|seeking|searching for|recruiting)\s+(?:an?\s+|the\s+)?"
        r"(?P<title>[^.;\n]{3,80}?)\s+(?:to\s+\w+|who|for|in|at|with)\b"
    )
    YEARS_RE = re.compile(
        r"(\d{1,2})\s*(?:\+|(?:-|–|—|to)\s*(\d{1,2}))?\s*\+?\s*(?:years|yrs)", re.IGNORECASE,
    )
    SENIORITY_WORDS = (
        ("principal", "principal"), ("staff", "staff"), ("lead", "lead"), ("manager", "manager"),
        ("senior", "senior"), ("sr.", "senior"), ("sr ", "senior"), ("junior", "junior"), ("jr", "junior"),
        ("intern", "intern"), ("mid", "mid"),
    )
    METADATA_PREFIXES = ("job title:", "role:", "position:", "company:")

    # Marks a bulleted line, in any of the glyph variants seen in real JDs.
    BULLET_LINE_RE = re.compile(r"^[-•*▪●◦‣▸–—]\s+")

    def __init__(self, llm_client: Optional[LLMClient] = None):
        # Used ONLY to pick which lines are genuine requirements vs
        # boilerplate (see _llm_select_requirement_lines) — never to
        # generate or paraphrase requirement text. Every requirement kept
        # is still one of the exact lines pulled straight from the JD, so
        # scoring stays recoverable verbatim from the source text. When
        # unavailable, analyze() falls back fully to the deterministic
        # REQUIREMENT_SIGNALS heuristic below.
        self.llm_client = llm_client

    # A word, optionally followed by symbol suffixes (C++, C#) or dotted /
    # slashed / hyphenated parts (Node.js, CI/CD, scikit-learn). A trailing
    # sentence period is not captured because [./-] must be followed by an
    # alphanumeric character.
    # Any script's letters (P8.17: "Enfermería" was cut to "Enfermer").
    KEYWORD_TOKEN_RE = re.compile(r"[^\W\d_][^\W_]*(?:[+#]+|(?:[./-][^\W_]+)+)?")
    # Capitalised words that start clauses or are generic, never skills.
    KEYWORD_NOISE = {
        "we", "you", "our", "your", "the", "a", "an", "and", "or", "in", "on", "at", "to", "of", "for",
        "with", "is", "are", "be", "as", "by", "this", "that", "it", "if", "all", "any", "strong",
        "excellent", "good", "great", "ability", "experience", "knowledge", "familiarity", "understanding",
        "proficiency", "bachelor", "bachelors", "master", "masters", "degree", "years", "year", "plus",
        "bonus", "preferred", "required", "requirements", "responsibilities", "qualifications", "skills",
        "about", "job", "role", "team", "company", "equal", "opportunity", "employer", "benefits",
        "e.g", "i.e", "etc", "us", "eeo", "inc", "ltd", "llc", "senior", "junior", "lead", "engineer",
        "developer", "manager", "analyst", "scientist", "intern",
    }
    MAX_KEYWORDS = 40
    # A line of perks or equal-opportunity text, wherever it stands.
    _BOILERPLATE_LINE_RE = re.compile(
        r"(?i)equal opportunity|regardless of|without regard to|benefits include|we offer|401\(k\)|paid time off"
        r"|reasonable accommodation")

    _TAG_BREAK_RE = re.compile(r"(?i)<\s*(?:br|/p|/li|/h[1-6]|/div|/tr)\s*/?>")
    _TAG_ITEM_RE = re.compile(r"(?i)<\s*li[^>]*>")
    # Only tag-shaped text on one line: "C++ with < 5 years ... > $100k" stays (Stage K review).
    _TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>\n]{0,200})?/?>")

    @classmethod
    def clean_text(cls, text: str) -> str:
        """A pasted JD as plain text (P8.18): HTML tags and entities removed
        (line breaks kept, list items as "- "), emoji and pictographs
        dropped, spaces tidied. "🚀 Senior Accountant 💼" -> "Senior Accountant"."""
        import html
        import unicodedata
        text = text or ""
        if cls._TAG_RE.search(text):
            text = cls._TAG_BREAK_RE.sub("\n", text)
            text = cls._TAG_ITEM_RE.sub("\n- ", text)
            text = cls._TAG_RE.sub(" ", text)
        text = html.unescape(text)
        keep = set("•●▪◦‣▸–—-*°™©®✓✔")
        text = "".join(ch for ch in text if ch in keep or ch in "\n\t" or not (
            unicodedata.category(ch) in ("So", "Cs", "Co") or ch in "\ufe0f\u200d"))
        lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    @staticmethod
    def too_short(text: str) -> bool:
        """Too little to score against (P8.18: a two-word JD scored 100%)."""
        return len(re.findall(r"\w+", text or "")) < 5

    def _not_benefit(self, keywords: List[str]) -> List[str]:
        from app.analysis.terminology import BENEFIT_TERMS
        return [k for k in keywords if k.lower().strip() not in BENEFIT_TERMS]

    def extract_keywords_from_text(self, text: str) -> List[str]:
        """Stopgap keyword extraction: keep only technical-looking terms,
        ranked by frequency. Kept terms are acronyms (AWS, SQL), tokens with
        symbols (C++, C#, Node.js, CI/CD), capitalised words that don't open
        a sentence (Python, Kubernetes), and multi-word canonical terms from
        the terminology registry ("machine learning"). Plain English words
        are dropped so the rewrite prompt isn't flooded with noise."""
        from app.analysis.terminology import ALIAS_MAP, TECH_TERMS

        counts: Dict[str, int] = {}
        display: Dict[str, str] = {}

        def add(term: str) -> None:
            key = term.lower()
            counts[key] = counts.get(key, 0) + 1
            display.setdefault(key, term)

        from app.analysis.terminology import DOMAIN_TERMS
        boilerplate = False
        opening_runs: List[str] = []
        for line in text.splitlines():
            line = self._clean_line(line)
            if self._is_heading(line) or line.lower().startswith(self.METADATA_PREFIXES):
                # Lines under "Benefits", "What we offer", "Equal opportunity"...
                boilerplate = bool(re.search(r"(?i)benefit|perk|what we offer|equal opportunity|about us", line))
                continue
            if boilerplate or self._BOILERPLATE_LINE_RE.search(line):
                continue
            for sentence in re.split(r"(?<=[.!?;:])\s+", line):
                run: List[str] = []  # adjacent capitalised words: "Six Sigma", "Supply Chain"
                initial = [False]  # the run starts with the sentence's first word
                last_end = -1

                def flush() -> None:
                    phrase = " ".join(run[:4])
                    if len(run) >= 2 and not initial[0]:
                        add(phrase)
                    elif len(run) >= 2:
                        # "Wingtip Cloud is looking for...": a name opening a
                        # sentence; kept only if it shows up mid-sentence too.
                        opening_runs.append(phrase)
                    elif run and not initial[0]:
                        add(run[0])  # a lone sentence-initial capital is just a capital
                    run.clear()
                    initial[0] = False

                for pos, match in enumerate(self.KEYWORD_TOKEN_RE.finditer(sentence)):
                    tok = match.group(0)
                    low = tok.lower()
                    adjacent = match.start() == last_end + 1 and sentence[last_end:match.start()] == " "
                    last_end = match.end()
                    if len(tok) < 2 or low in self.KEYWORD_NOISE:
                        flush()
                        continue
                    has_symbol = bool(re.search(r"[+#./0-9]", tok))
                    is_acronym = tok.isupper() and tok.isalpha()
                    is_capitalised = tok[0].isupper() and pos > 0
                    if low in TECH_TERMS or low in DOMAIN_TERMS:  # known term, wherever it stands
                        flush()
                        add(tok)
                        continue
                    if "-" in tok and not has_symbol and not re.search(r"[A-Z]", tok[1:]):
                        flush()
                        continue  # plain hyphenated English ("cross-functional")
                    if tok[0].isupper() and not has_symbol and not is_acronym:
                        if run and not adjacent:
                            flush()
                        if not run:
                            initial[0] = pos == 0
                        run.append(tok)
                        continue
                    flush()
                    if has_symbol or is_acronym:
                        add(tok)
                flush()

        for phrase in opening_runs:
            if phrase.lower() in counts or phrase.lower() in DOMAIN_TERMS or phrase.lower() in TECH_TERMS:
                add(phrase)

        lowered_text = text.lower()
        for canonical in ALIAS_MAP:
            if " " in canonical and re.search(rf"\b{re.escape(canonical)}\b", lowered_text):
                add(canonical)
        # Multi-word terms ("Power BI", "wound care", "month-end close"), in the JD's spelling.
        for term in [*TECH_TERMS, *DOMAIN_TERMS]:
            if " " in term:
                m = re.search(rf"(?<![\w/]){re.escape(term)}(?![\w/])", text, re.IGNORECASE)
                if m:
                    for part in term.split():  # "A/B testing" replaces a bare "A/B"
                        counts.pop(part, None)
                    add(m.group(0))

        ranked = sorted(counts, key=lambda k: (-counts[k], list(counts).index(k)))
        return [display[k] for k in ranked[: self.MAX_KEYWORDS]]

    def _category(self, line: str) -> str:
        lowered = line.lower()
        if any(k in lowered for k in ("degree", "education", "bachelor", "master", "phd", "certif")):
            return "qualification"
        if self.YEARS_RE.search(line):
            return "experience"
        if any(k in lowered for k in (
            "responsible", "develop", "design", "build", "manage", "lead", "implement",
            "maintain", "analyze", "collaborate", "create", "own ", "mentor", "contribute",
        )):
            return "responsibility"
        return "skill"

    def _clean_line(self, line: str) -> str:
        """Strip a bullet marker, including private-use glyphs pasted from Word/PDF."""
        line = re.sub(r"^[\ue000-\uf8ff\u200b\ufeff\s]+", "", line)
        return self.BULLET_LINE_RE.sub("", line).strip()

    def _is_heading(self, line: str) -> bool:
        """A section heading: the known patterns, an ALL-CAPS short line
        ("WHAT YOU WILL NEED"), or a short line naming a known section
        ("Nice To Have, But Not Required"). A "Label: content" line is not
        a heading."""
        text = self._clean_line(line)
        if self.HEADING_RE.match(text):
            return True
        if not text or len(text) > 60 or text.endswith("."):
            return False
        if ":" in text and text.split(":", 1)[1].strip():
            return False
        letters = [c for c in text if c.isalpha()]
        if letters and all(c.isupper() for c in letters) and len(text.split()) >= 2:
            return True
        return len(text.split()) <= 8 and bool(self.HEADING_PHRASES_RE.search(text))

    def _is_requirement(self, line: str, was_bullet: bool, in_requirement_section: bool) -> bool:
        lowered = line.lower()
        if self._is_heading(line) or len(line) < 4:
            return False
        # Bullets under a requirements-like heading are explicit source items.
        return was_bullet or in_requirement_section or any(
            signal in lowered for signal in self.REQUIREMENT_SIGNALS
        )

    def _reflow_lines(self, jd_text: str) -> List[str]:
        """Undo hard line-wrapping from pasted JDs (job boards/PDFs often wrap
        a single sentence or bullet across multiple lines at a fixed width).
        Left as separate lines, a wrapped requirement shreds into
        unrelated-looking fragments that get scored independently. A
        continuation line is merged into the previous line when: it isn't
        itself a new bullet or a section heading, the previous line doesn't
        already end at a sentence/clause boundary, and it starts with a
        lowercase letter — the strongest cheap signal that it continues the
        prior clause rather than starting a new label/heading/sentence
        (which almost always starts uppercase, e.g. "Company: Acme Inc.")."""
        raw_lines = [l.strip() for l in jd_text.splitlines()]
        reflowed: List[str] = []
        for line in raw_lines:
            if not line:
                reflowed.append("")  # preserve paragraph breaks
                continue
            is_bullet = bool(self.BULLET_LINE_RE.match(line))
            is_heading_like = self._is_heading(line)
            starts_lowercase = line[0].islower()
            prev = reflowed[-1] if reflowed else ""
            prev_ends_clause = (not prev) or bool(re.search(r"[.:;!?]$", prev))
            if (
                reflowed
                and prev
                and not is_bullet
                and not is_heading_like
                and not prev_ends_clause
                and starts_lowercase
            ):
                reflowed[-1] = f"{prev} {line}".strip()
            else:
                reflowed.append(line)
        return [l for l in reflowed if l]

    # -- verbatim guard -------------------------------------------------

    @staticmethod
    def _verbatim(value: Optional[str], jd_text: str) -> Optional[str]:
        """The JD's own spelling of `value` if it occurs in the JD (case- and
        whitespace-insensitive), else None. Anything the LLM returns that
        isn't in the JD is dropped here. Whole terms only, so "R" isn't the
        "r" in "Senior" and "Java" isn't in "JavaScript" (a plural still
        counts: "API" in "APIs"); the JD's own capitalisation wins (P9.23)."""
        if not value or not value.strip():
            return None
        words = [re.escape(w) for w in value.split()]
        pattern = r"(?<![A-Za-z0-9])" + r"\s+".join(words) + r"(?=(?:e?s)?(?![A-Za-z0-9]))"
        m = re.search(pattern, jd_text) or re.search(pattern, jd_text, re.IGNORECASE)
        return re.sub(r"\s+", " ", m.group(0)).strip() if m else None

    def _verbatim_list(self, values: List[str], jd_text: str) -> List[str]:
        out: List[str] = []
        seen = set()
        for value in values:
            found = self._verbatim(value, jd_text)
            if found and found.lower() not in seen:
                seen.add(found.lower())
                out.append(found)
        return out

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        """Whole-term containment: "A/B" is in "A/B testing", "ML" is not in "MLflow"."""
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.IGNORECASE))

    @staticmethod
    def count_occurrences(term: str, text: str) -> int:
        """Whole-term, case-insensitive count ("R" doesn't match "React")."""
        return len(re.findall(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9+#])", text, re.IGNORECASE))

    # -- deterministic metadata ------------------------------------------

    def _heuristic_title_company(self, lines: List[str]) -> Tuple[Optional[str], Optional[str]]:
        title = company = None
        for line in lines:
            lowered = line.lower()
            if lowered.startswith(("job title:", "role:", "position:")):
                title = title or line.split(":", 1)[1].strip() or None
            elif lowered.startswith("company:"):
                company = company or line.split(":", 1)[1].strip() or None
        if title and company:
            return title, company
        for line in lines[:15]:
            m = self.INTRO_RE.search(line)
            if not m:
                continue
            found_company = m.group("company").strip()
            if found_company.lower() not in ("we", "our team", "our company", "the team", "you"):
                company = company or found_company
            title = title or m.group("title").strip()
            break
        return title, company

    def _seniority(self, title: Optional[str]) -> Optional[str]:
        lowered = f" {(title or '').lower()} "
        for word, level in self.SENIORITY_WORDS:
            if re.search(rf"(?<![a-z]){re.escape(word.strip())}(?![a-z])", lowered):
                return level
        return None

    def _years(self, jd_text: str) -> Tuple[Optional[int], Optional[int]]:
        m = self.YEARS_RE.search(jd_text)
        if not m:
            return None, None
        return int(m.group(1)), (int(m.group(2)) if m.group(2) else None)

    # -- the LLM call ---------------------------------------------------

    def _llm_analyze(self, lines: List[str]) -> Optional[JDAnalysisResult]:
        """One structured call: metadata, requirement lines by index, skills.
        None (caller falls back to heuristics) when no LLM is configured, it's
        unreachable, the call fails, or no requirement line was selected."""
        if not lines or not self.llm_client or not self.llm_client.is_available():
            return None
        try:
            with open(_PROMPT_PATH, encoding="utf-8") as f:
                system_prompt = f.read()
        except OSError:
            return None
        numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Numbered JD lines:\n{numbered}"},
        ]
        try:
            result = self.llm_client.generate_json(
                messages=messages, schema_model=JDAnalysisResult, temperature=0.0, effort="medium",
            )
        except Exception:
            return None
        if not any(0 <= r.index < len(lines) for r in result.requirement_lines):
            return None
        return result

    # -- main entry -----------------------------------------------------

    def analyze(self, jd_text: str) -> JobDescription:
        jd_text = self.clean_text(jd_text)  # HTML, entities, emoji (P8.18); spans point into this cleaned text
        span_from = 0  # where the next requirement's span is searched from, so a repeated line maps to its own place
        lines = self._reflow_lines(jd_text)
        llm = self._llm_analyze(lines)
        llm_lines = {}
        if llm is not None:
            for item in llm.requirement_lines:
                if 0 <= item.index < len(lines) and item.index not in llm_lines:
                    llm_lines[item.index] = item

        requirements: List[Requirement] = []
        preferred_section = False
        requirement_section = False
        intro_section = False  # "About the role / us": context, not requirements
        for idx, line in enumerate(lines):
            lowered = line.lower()
            if lowered.startswith(self.METADATA_PREFIXES):
                continue
            if self._is_heading(line):
                heading = self._clean_line(line).lower()
                preferred_section = any(sig in heading for sig in self.PREFERRED_HEADING_SIGNALS)
                requirement_section = preferred_section or any(token in heading for token in (
                    "requirement", "qualification", "responsibilit", "skill", "who you are", "what you",
                    "need", "must have",
                ))
                intro_section = heading.startswith("about") and not requirement_section
                continue

            was_bullet = bool(self.BULLET_LINE_RE.match(line))
            clean_line = self._clean_line(line)
            item = llm_lines.get(idx)
            if llm is not None:
                # The LLM is the authority on inclusion when available: it
                # can drop a bulleted perks line the heuristic would keep.
                if item is None:
                    continue
            elif (intro_section and not was_bullet) or not self._is_requirement(
                    clean_line, was_bullet, requirement_section):
                continue

            # Whole lines, never split on "and" (F46): "Design and build
            # ranking models" is one requirement, not "Design" + "build...".
            line_says_preferred = any(sig in clean_line.lower() for sig in self.PREFERRED_SIGNALS)
            priority = "preferred" if (
                preferred_section or line_says_preferred or (item is not None and item.priority == "preferred")
            ) else "required"
            category = item.category if item is not None else self._category(clean_line)
            start = jd_text.find(clean_line, span_from)
            if start < 0:
                start = jd_text.find(clean_line)
            if start >= 0:
                span_from = start + len(clean_line)
            requirements.append(Requirement(
                id=f"req_{len(requirements) + 1:03d}",
                text=clean_line, category=category, priority=priority, criticality=priority,
                source_spans=[{"start": start, "end": start + len(clean_line)}] if start >= 0 else None,
            ))

        title, company = self._heuristic_title_company(lines)
        min_years, max_years = self._years(jd_text)
        hard_skills: List[str] = []
        soft_skills: List[str] = []
        education: List[str] = []
        certifications: List[str] = []
        seniority = None
        if llm is not None:
            title = self._verbatim(llm.job_title, jd_text) or title
            company = self._verbatim(llm.company, jd_text) or company
            seniority = llm.seniority
            if llm.min_years is not None and str(llm.min_years) in jd_text:
                min_years = llm.min_years
                max_years = llm.max_years if llm.max_years is not None and str(llm.max_years) in jd_text else None
            hard_skills = self._verbatim_list(llm.hard_skills, jd_text)
            soft_skills = self._verbatim_list(llm.soft_skills, jd_text)
            education = self._verbatim_list(llm.education, jd_text)
            certifications = self._verbatim_list(llm.certifications, jd_text)
        seniority = seniority or self._seniority(title)

        company_words = {w.lower() for w in re.findall(r"[^\W\d_]+", company or "")}
        keywords = hard_skills + [c for c in certifications if c not in hard_skills]
        # Deterministic terms from the requirement lines only (not the intro,
        # where team names and title codes live) fill gaps in the LLM's
        # list, which varies between runs, and are the whole list without it.
        requirement_text = "\n".join(r.text for r in requirements) or jd_text
        for term in self.extract_keywords_from_text(requirement_text):
            low = term.lower()
            if low in company_words or set(low.split()) <= company_words or any(
                    self._contains_term(k, term) or self._contains_term(term, k) for k in keywords):
                continue
            keywords.append(term)
        keywords = self._not_benefit(keywords)
        hard_skills, certifications = self._not_benefit(hard_skills), self._not_benefit(certifications)
        keyword_counts = {k: self.count_occurrences(k, jd_text) for k in keywords}
        # Most frequent first; ties keep the order the model/heuristic gave.
        keywords = sorted(keywords, key=lambda k: -keyword_counts[k])

        return JobDescription(
            job_title=title or "Target Role",
            company=company or "Company",
            requirements=requirements,
            keywords=keywords[: self.MAX_KEYWORDS],
            raw_text=jd_text,
            seniority=seniority,
            min_years=min_years,
            max_years=max_years,
            hard_skills=hard_skills,
            soft_skills=soft_skills,
            education=education,
            certifications=certifications,
            keyword_counts=keyword_counts,
            analysis_source="llm" if llm is not None else "heuristic",
        )
