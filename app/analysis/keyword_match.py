"""Keyword-level match rate, the headline score (P1.2).

Applicant tracking systems and tools like Jobscan score a resume by which of
the JD's keywords it contains, not by whole-sentence similarity. This module
does the same, transparently: every JD keyword becomes a row saying whether
the resume has it and where, and the rate is the weighted share found.

Weights: hard skills 3, job title 2, education / certifications 1.5, soft
skills 1; a keyword that appears in a required JD line counts ×1.5.
"""
import re
from typing import Dict, List, Optional, Tuple

from app.analysis.terminology import flat_alias_to_canonical
from app.domain.job import JobDescription
from app.domain.report import KeywordMatchReport, KeywordRow
from app.domain.resume import Resume

KIND_WEIGHTS = {"hard": 3.0, "title": 2.0, "education": 1.5, "certification": 1.5, "soft": 1.0}
REQUIRED_MULTIPLIER = 1.5
# A skill or soft skill only listed under Skills, never shown in a bullet,
# summary or project, earns this share of its weight (P8.19: one Skills line
# pasted from the JD outscored a strong resume, 87.5% vs 37.5%; at half
# credit the Stage K gate's stuffed resume still won, 50% vs 36%).
SKILLS_ONLY_CREDIT = 0.5
# ...and this when most of what's found is only listed under Skills, the
# pattern of a Skills line pasted from the JD (Stage K gate: 50% vs 36%).
STUFFED_SKILLS_ONLY_CREDIT = 0.25
STUFFED_SHARE = 0.5

# Having the left term means having the right one (PySpark is Spark's Python API).
IMPLIES: Dict[str, List[str]] = {
    "pyspark": ["spark"],
    "sklearn": ["scikit-learn"],
    "scikit-learn": ["sklearn"],
    "postgres": ["postgresql"],
    "gpt": ["llm"],
}
_ALIASES = flat_alias_to_canonical()
# Letters of any script, digits, + and # (P8.17: accented words were cut short).
_TOKEN_RE = re.compile(r"(?:[^\W_]|[+#])+(?:[./-](?:[^\W_]|[+#])+)*")
# Words in a job title that say nothing about the role itself.
_TITLE_NOISE = {"i", "ii", "iii", "iv", "l1", "l2", "l3", "l4", "l5", "sr", "jr", "senior", "junior", "lead",
                "staff", "principal", "the", "a", "an", "of", "and", "or", "for", "in", "at", "to", "with"}


# "HIPAA-compliant", "AWS-certified", "cloud-native": a term plus one of these
# suffixes. Other hyphenated words ("go-to-market", "R-squared", "C-suite")
# are never split, so short keywords can't match inside them.
_TERM_SUFFIXES = {"compliant", "certified", "based", "driven", "native", "enabled", "powered", "ready",
                  "focused", "first", "backed", "centric", "savvy"}


# Fields named by an -ing word: "marketing" is not "market", "accounting" not "account".
_ING_NOUNS = {"marketing", "accounting", "networking", "engineering", "banking", "staffing", "consulting",
              "advertising", "manufacturing", "publishing", "housing", "clothing", "catering", "wedding"}


def _stem(token: str) -> str:
    """Plural- and verb-form-insensitive: "communicate", "communicated" and
    "communicating" all read "communicat". Stems shorter than four letters
    are left alone, so "string", "spring" and "used" keep their meaning."""
    if token in _ING_NOUNS:
        return token
    if len(token) > 3 and token.endswith("ies"):
        token = token[:-3] + "y"
    elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[:-len(suffix)]
    if len(token) > 4 and token.endswith("e") and not token.endswith("ee"):
        return token[:-1]
    return token


def _alias(text: str) -> str:
    value = text.lower()
    for source, target in _ALIASES.items():
        # A plural acronym too: "KPIs" -> "key performance indicators" (Stage K review).
        value = re.sub(r"(?<![a-z0-9])" + re.escape(source) + r"(s?)(?![a-z0-9])",
                       lambda m, t=target: t + m.group(1), value)
    return value


_TERM_SUFFIX_STEMS = {_stem(s) for s in _TERM_SUFFIXES}


def tokens(text: str) -> List[str]:
    """Lowercased, alias-canonical, plural- and verb-form-insensitive tokens.
    Each part of a hyphenated word is stemmed on its own ("AWS-certified")."""
    return ["-".join(_stem(p) for p in t.split("-")) for t in _TOKEN_RE.findall(_alias(text))]


def _contains_seq(haystack: List[str], needle: List[str]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def resume_sections(resume: Resume) -> List[Tuple[str, str]]:
    """(label, text) for every part of the resume a recruiter or ATS reads."""
    parts: List[Tuple[str, str]] = []
    c = resume.candidate
    if c.headline:
        parts.append(("headline", c.headline))
    if resume.summary:
        parts.append(("summary", resume.summary))
    for exp in resume.experience:
        label = exp.company or exp.title or "experience"
        for role in exp.all_roles():
            parts.append((f"{label} (title)", role.title))
        for group, bullets in exp.bullet_groups():
            if group:
                parts.append((f"{label} (project)", group))
            for b in bullets:
                parts.append((f"{label} (bullet)", b.text))
    for proj in resume.projects:
        parts.append((f"{proj.name} (project)", " ".join([proj.name, proj.description, *proj.technologies])))
        for b in proj.bullets:
            parts.append((f"{proj.name} (project)", b.text))
    for category, items in resume.skills.items():
        parts.append(("skills", f"{category}: " + ", ".join(items)))
    for edu in resume.education:
        parts.append(("education", " ".join(v for v in (edu.degree, edu.field_of_study or "", edu.institution) if v)))
    for cert in resume.certifications:
        parts.append(("certifications", " ".join(str(v) for v in cert.values() if v)))
    for item in resume.achievements:
        parts.append(("achievements", item))
    return [(label, text) for label, text in parts if text and text.strip()]


# "Generally Accepted Accounting Principles (GAAP)" in the JD or the resume
# defines an acronym for this run (P8.17).
_DEFINITION_RE = re.compile(r"((?:[A-Z][\w'’-]*[\s/-]+(?:(?:of|and|for|the|&)[\s]+)?){1,7}[A-Z][\w'’-]*)\s*\(([A-Z][A-Za-z0-9&/-]{1,7})\)")
# Small words that never start an acronym's expansion nor give it a letter
# ("Or Associate (OA)" isn't a definition; P9.5).
_CONNECTORS = {"of", "and", "for", "the", "&", "or", "in", "with", "a", "an", "to", "on", "at", "as", "by"}
# A degree on the resume covers a lower one the JD asks for.
_DEGREE_KEYWORD_RE = re.compile(r"(?i:degree|bachelor|master|diploma|\bged\b|ph\.?\s?d|doctorate|associate's)")
# "Salesforce CRM" is shown by "Salesforce": a product name and a generic tail.
_GENERIC_TAIL = {"crm", "platform", "suite", "software", "tool", "system", "studio", "cloud", "program"}
# Role and credential words that "X or Y <word>" shares between X and Y.
_SHARED_TAIL = {_stem(w) for w in {"developer", "developers", "engineer", "engineers", "engineering", "development", "programming",
                "programmer", "experience", "skills", "analyst", "specialist", "designer", "administrator",
                "certification", "certified", "license", "licence", "licensed", "degree", "nurse", "teacher",
                "technician", "framework", "frameworks", "database", "databases", "language", "languages"}}
_US_STATES = {"alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
              "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
              "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
              "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york",
              "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
              "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
              "west virginia", "wisconsin", "wyoming", "dc", "d.c."}


def is_place(keyword: str, jd_text: str = "") -> bool:
    """A location the JD names, not a skill (P8.17: "Arizona" and "DC" were
    scored as hard skills)."""
    k = keyword.strip().lower()
    if k in _US_STATES:
        return True
    from app.analysis.resume_normalizer import ResumeNormalizer
    if k in ResumeNormalizer._COUNTRIES:
        return True
    if not jd_text or len(keyword.split()) > 3 or not keyword[:1].isupper() or keyword.isupper():
        return False
    for m in re.finditer(re.escape(keyword.strip()) + r",\s*([A-Z]{2}\b|[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", jd_text):
        after = m.group(1)
        if after in ResumeNormalizer._US_STATES or after.lower() in _US_STATES \
                or after.lower() in ResumeNormalizer._COUNTRIES:
            return True  # "Phoenix, AZ", "Lyon, France"
    return False


def definitions(*texts: str) -> Dict[str, str]:
    """acronym -> expansion (both lowercase), from "Full Name (ACR)" in texts."""
    out: Dict[str, str] = {}
    for text in texts:
        for long, short in _DEFINITION_RE.findall(text or ""):
            words = [w for w in re.split(r"[\s/-]+", long) if w]
            acronym = short.lower().replace("&", "").replace("/", "")
            content = [w for w in words if w.lower() not in _CONNECTORS]
            initials = "".join(w[0] for w in content).lower()
            if content and (initials.endswith(acronym[:len(initials)]) or acronym in initials):
                # keep only the words that spell the acronym (the regex may grab a few before)
                keep = content[-len(acronym):] if len(acronym) <= len(content) else content
                out[short.lower()] = " ".join(words[words.index(keep[0]):]).lower()
                continue
            # "Point Of Sale (POS)": the connector is one of the letters (P9.5)
            span = words[-len(acronym):]
            if len(span) == len(acronym) and span[0].lower() not in _CONNECTORS and \
                    "".join(w[0] for w in span).lower() == acronym:
                out[short.lower()] = " ".join(span).lower()
    return out


def alternatives_of(keyword: str) -> List[List[str]]:
    """Token sequences that count as the keyword: "OSHA 10 or 30" -> OSHA 10,
    OSHA 30; "NetSuite or Oracle ERP" -> NetSuite, Oracle ERP (P8.17)."""
    parts = [p for p in re.split(r"\s+or\s+", keyword, flags=re.IGNORECASE) if p.strip()]
    if len(parts) < 2:
        return [tokens(keyword)]
    prefix = [t for t in tokens(parts[0]) if not t.isdigit()]
    out = []
    for p in parts:
        toks = tokens(p)
        if toks and all(t.isdigit() for t in toks):
            toks = prefix + toks
        if toks:
            out.append(toks)
    # "Java or Python developer": the role word belongs to both, so Python
    # alone counts just as Java alone does (P9.5)
    last = out[-1] if out else []
    if len(last) == 2 and last[-1] in _SHARED_TAIL and all(len(o) == 1 for o in out[:-1]):
        out.append(last[:1])
    return out


class KeywordMatcher:
    def __init__(self):
        self._defs: Dict[str, str] = {}
        self._education_level = -1

    def _slash_parts(self, keyword: str) -> List[str]:
        """"Compact/NLC", "English/Spanish": words joined by a slash, each
        counted (not "A/B", "CI/CD", "TCP/IP", "S/4HANA")."""
        if "/" not in keyword or " " in keyword.strip():
            return []
        parts = keyword.split("/")
        if len(parts) == 2 and all(len(p) >= 3 and p[:1].isalpha() for p in parts) and keyword.lower() != "lockout/tagout":
            return parts
        return []

    def _found_with_credit(self, keyword: str, kind: str, sections) -> Tuple[List[str], float]:
        where = self._find(keyword, sections)
        if where:
            return where, 1.0
        parts = self._slash_parts(keyword)
        if parts:
            hits = [self._find(p, sections) for p in parts]
            found = [h for h in hits if h]
            if found:
                return sorted({w for h in found for w in h}), round(len(found) / len(parts), 2)
        if kind == "education" and _DEGREE_KEYWORD_RE.search(keyword):
            from app.analysis.gap_questions import _degree_level
            asked = _degree_level(keyword)
            if asked >= 0 and self._education_level >= asked:
                return ["education"], 1.0
        written = re.findall(r"[^\W_]+", keyword.lower())  # before aliasing: "CRM", not its expansion
        if len(written) > 1 and all(w.rstrip("s") in _GENERIC_TAIL for w in written[1:]):
            where = self._find(written[0], sections)
            if where:
                return where, 1.0
        return [], 0.0

    def _find(self, keyword: str, sections: List[Tuple[str, List[str]]]) -> List[str]:
        needle = tokens(keyword)
        if not needle:
            return []
        alternatives = alternatives_of(keyword) + [tokens(t) for t in IMPLIES.get(" ".join(needle), [])]
        key = " ".join(needle)
        if key in self._defs:  # an acronym the texts define
            alternatives.append(tokens(self._defs[key]))
        alternatives += [tokens(short) for short, long in self._defs.items() if " ".join(tokens(long)) == key]
        where: List[str] = []
        for label, toks in sections:
            token_set = set(toks)
            # "HIPAA-compliant" contains HIPAA: also look at hyphenated
            # tokens split into their parts (dots and slashes stay: Node.js, A/B).
            split = [p for t in toks for p in (t.split("-") if t.rsplit("-", 1)[-1] in _TERM_SUFFIX_STEMS else [t]) if p]
            hit = any(_contains_seq(toks, alt) or _contains_seq(split, alt) for alt in alternatives)
            # A multi-word term also counts when all its words appear in one
            # sentence ("recommendation systems" vs "systems for recommendation").
            if not hit and len(needle) >= 2:
                hit = all(t in token_set for t in needle)
            if not hit:
                # The resume side may imply the keyword ("PySpark" -> "Spark").
                hit = any(" ".join(needle) in [" ".join(tokens(i)) for i in IMPLIES.get(t, [])] for t in token_set)
            if hit and label not in where:
                where.append(label)
        return where

    def _title_credit(self, title: Optional[str], sections: List[Tuple[str, List[str]]]) -> Tuple[float, List[str]]:
        title_tokens = [t for t in dict.fromkeys(tokens(re.sub(r"\([^)]*\)", " ", title or ""))) if t not in _TITLE_NOISE]
        if not title_tokens:
            return 0.0, []
        title_sections = [(label, toks) for label, toks in sections if label.endswith("(title)") or label == "headline"]
        have = set(t for _, toks in title_sections for t in toks)
        found = [t for t in title_tokens if t in have]
        where = [label for label, toks in title_sections if set(toks) & set(found)]
        return len(found) / len(title_tokens), where

    def match(self, job: JobDescription, resume: Resume) -> KeywordMatchReport:
        raw_sections = resume_sections(resume)
        sections = [(label, tokens(text)) for label, text in raw_sections]
        self._defs = definitions(job.raw_text or "", *(text for _, text in raw_sections))
        from app.analysis.gap_questions import _degree_level
        self._education_level = _degree_level(" ".join(f"{e.degree} {e.institution}" for e in resume.education))
        required_text = " \n".join(r.text for r in job.requirements if r.priority == "required")
        rows: List[KeywordRow] = []
        seen = set()

        def add(keyword: str, kind: str) -> None:
            key = " ".join(tokens(keyword))
            if not key or key in seen:
                return
            seen.add(key)
            if kind == "hard" and is_place(keyword, job.raw_text or ""):
                return  # a location the JD names, not a skill
            in_required = _contains_seq(tokens(required_text), tokens(keyword)) if required_text else True
            weight = KIND_WEIGHTS[kind] * (REQUIRED_MULTIPLIER if in_required else 1.0)
            where, credit = self._found_with_credit(keyword, kind, sections)
            skills_only = bool(where) and kind in ("hard", "soft") and set(where) == {"skills"}
            if skills_only:
                credit = round(credit * SKILLS_ONLY_CREDIT, 2)
            jd_count = len([1 for i in range(len(jd_tokens)) if jd_tokens[i:i + len(tokens(keyword))] == tokens(keyword)])
            rows.append(KeywordRow(keyword=keyword, kind=kind, required=in_required, weight=weight,
                                   found=bool(where) and credit >= 0.25, credit=credit, where=where,
                                   jd_count=jd_count, skills_only=skills_only))

        jd_tokens = tokens(job.raw_text or "")
        certs = {c.lower() for c in job.certifications}
        for kw in job.keywords:
            add(kw, "certification" if kw.lower() in certs else "hard")
        for kw in job.certifications:
            add(kw, "certification")
        for kw in job.education:
            add(kw, "education")
        for kw in job.soft_skills:
            add(kw, "soft")
        if job.job_title and job.job_title != "Target Role":
            credit, where = self._title_credit(job.job_title, sections)
            rows.append(KeywordRow(keyword=job.job_title, kind="title", required=True,
                                   weight=KIND_WEIGHTS["title"] * REQUIRED_MULTIPLIER,
                                   found=credit >= 0.5, credit=round(credit, 2), where=where, jd_count=1))

        found_weight = sum(r.weight for r in rows if r.where)
        skills_only_weight = sum(r.weight for r in rows if r.skills_only)
        if found_weight and skills_only_weight / found_weight > STUFFED_SHARE:
            for r in rows:
                if r.skills_only:
                    r.credit = round(r.credit * STUFFED_SKILLS_ONLY_CREDIT / SKILLS_ONLY_CREDIT, 2)
                    r.found = r.credit >= 0.25
        total = sum(r.weight for r in rows)
        rate = round(100.0 * sum(r.weight * r.credit for r in rows) / total, 1) if total else 0.0
        report = KeywordMatchReport(rate=rate, rows=rows, approximate=job.analysis_source != "llm")
        report.guidance = guidance(report, job)
        return report


# Below this rate, with no title in common, the job is in another field.
DIFFERENT_FIELD_BELOW = 30.0
STRETCH_BELOW = 50.0


def guidance(report: KeywordMatchReport, job: JobDescription) -> Optional[Dict]:
    """What a low match means (P8.21): a nurse applying to a sales job scored
    0 and a teacher moving into instructional design 16%, and both were told
    to "aim for 75-85%". A different field gets a plain explanation and
    career-changer steps; a stretch gets its own; a fair match gets none."""
    title = next((r for r in report.rows if r.kind == "title"), None)
    # Only a known title with nothing in common says "another field"; when the
    # JD's title couldn't be read (offline), a low rate is just a stretch.
    if report.rate < DIFFERENT_FIELD_BELOW and title is not None and title.credit == 0:
        return {
            "kind": "different_field",
            "headline": "This job looks like a different field from your experience.",
            "text": ("A low match is expected here, and rewording can't change it: Tailores never adds experience you "
                     "don't have. Recruiters read a career change as a story, so make the story clear."),
            "tips": [
                "Tick the job keywords you really have in Review, and say where you used them in your own words.",
                "Add courses, certificates or projects in the new field under \"Add anything else\".",
                "Write the summary in your own words: what you're moving into and which of your skills carry over.",
                "Keep the bullets that show transferable work (training others, budgets, client work, tools) near the top in Arrange.",
            ],
        }
    if report.rate < STRETCH_BELOW:
        return {
            "kind": "stretch",
            "headline": "A stretch: the job asks for a fair amount your resume doesn't show yet.",
            "text": "The match only rises through keywords you really have; rewrites reword what's already there.",
            "tips": [
                "Tick the job keywords you really have in Review, with a line saying where.",
                "Check the missing keywords: if one is true but phrased differently on your resume, add it in your words.",
            ],
        }
    return None


def reconcile(matches, report: KeywordMatchReport):
    """A requirement can't read "not shown" while every job keyword in it is
    found (P1.16 / P8.18): "Proficient in Python and libraries like PyTorch
    and XGBoost" with all three on the resume is supported, and partly
    supported when some are."""
    rows = [(tokens(r.keyword), r) for r in report.rows if r.kind != "title" and tokens(r.keyword)]
    for m in matches:
        if m.status not in ("MISSING", "UNCERTAIN", "SEMANTIC_PARTIAL"):
            continue
        line = tokens(m.requirement_text)
        inside = [r for toks, r in rows if _contains_seq(line, toks)]
        if not inside:
            continue
        found = [r for r in inside if r.found and not r.skills_only]  # a Skills list entry shows nothing done
        covered = set(t for toks, r in rows if r in inside for t in toks)
        content = [t for t in line if len(t) > 3 and t not in _GENERIC_TAIL]
        thin = (re.search(r"\d+\s*\+?\s*(?:years|yrs)", m.requirement_text, re.IGNORECASE)
                or (content and len([t for t in content if t in covered]) / len(content) < 0.4))
        if len(found) == len(inside) and not thin:
            m.status = "SUPPORTED"
            m.explanation = "Every job keyword in this line is on your resume: " + ", ".join(r.keyword for r in found)
            m.confidence = max(getattr(m, "confidence", 0.0) or 0.0, 0.8)
        elif found and m.status in ("MISSING", "UNCERTAIN"):
            m.status = "PARTIAL"
            m.explanation = ("Some of this line's job keywords are on your resume: "
                             + ", ".join(r.keyword for r in found))
    return matches
