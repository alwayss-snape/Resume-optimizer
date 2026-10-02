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

# Having the left term means having the right one (PySpark is Spark's Python API).
IMPLIES: Dict[str, List[str]] = {
    "pyspark": ["spark"],
    "sklearn": ["scikit-learn"],
    "scikit-learn": ["sklearn"],
    "postgres": ["postgresql"],
    "gpt": ["llm"],
}
_ALIASES = flat_alias_to_canonical()
_TOKEN_RE = re.compile(r"[a-z0-9+#]+(?:[./-][a-z0-9+#]+)*")
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
        value = re.sub(r"(?<![a-z0-9])" + re.escape(source) + r"(?![a-z0-9])", target, value)
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


class KeywordMatcher:
    def _find(self, keyword: str, sections: List[Tuple[str, List[str]]]) -> List[str]:
        needle = tokens(keyword)
        if not needle:
            return []
        alternatives = [needle] + [tokens(t) for t in IMPLIES.get(" ".join(needle), [])]
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
        sections = [(label, tokens(text)) for label, text in resume_sections(resume)]
        required_text = " \n".join(r.text for r in job.requirements if r.priority == "required")
        rows: List[KeywordRow] = []
        seen = set()

        def add(keyword: str, kind: str) -> None:
            key = " ".join(tokens(keyword))
            if not key or key in seen:
                return
            seen.add(key)
            in_required = _contains_seq(tokens(required_text), tokens(keyword)) if required_text else True
            weight = KIND_WEIGHTS[kind] * (REQUIRED_MULTIPLIER if in_required else 1.0)
            where = self._find(keyword, sections)
            jd_count = len([1 for i in range(len(jd_tokens)) if jd_tokens[i:i + len(tokens(keyword))] == tokens(keyword)])
            rows.append(KeywordRow(keyword=keyword, kind=kind, required=in_required, weight=weight,
                                   found=bool(where), credit=1.0 if where else 0.0, where=where,
                                   jd_count=jd_count))

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

        total = sum(r.weight for r in rows)
        rate = round(100.0 * sum(r.weight * r.credit for r in rows) / total, 1) if total else 0.0
        return KeywordMatchReport(rate=rate, rows=rows)
