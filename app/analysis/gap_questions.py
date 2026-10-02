"""Suggest-and-confirm gaps (P3.1): ask, never assume.

For JD lines whose keywords the resume doesn't show, the tool asks the
candidate whether they have that experience. Only what they confirm is
used: a ticked keyword goes into their skills, and a bullet is drafted
only from the words they typed. Questions are built in code (no LLM).
"""
import re
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

from app.analysis.keyword_match import _contains_seq, tokens
from app.domain.job import JobDescription
from app.domain.report import KeywordMatchReport

MAX_QUESTIONS = 6


class GapQuestion(BaseModel):
    id: str
    requirement: str  # the JD line, verbatim
    priority: str  # required | preferred
    keywords: List[str] = Field(default_factory=list)  # JD keywords the resume doesn't show
    question: str
    # Short label over the tick boxes, worded by what is asked (P8.12):
    # "Tick the ones you hold:" for licences, "Tick it if you have it:" for a
    # degree, "Tick what you can show with a real example:" for a soft skill.
    tick_label: str = "Tick what you have really used:"
    # keyword -> kind ("hard", "certification", "education", "soft").
    kinds: Dict[str, str] = Field(default_factory=dict)
    # Pre-fill from the saved profile (P3.2): keywords confirmed for an
    # earlier JD and the answer given then. Shown ticked, still editable.
    saved_keywords: List[str] = Field(default_factory=list)
    saved_answer: str = ""


class GapAnswer(BaseModel):
    question_id: str = ""
    confirmed_keywords: List[str] = Field(default_factory=list)  # ticked: "I have used this"
    answer: str = ""  # the candidate's own words; drafted into a bullet
    target: str = "auto"  # "auto", "new_project" or an experience id


# Words that say little on their own: "Salesforce CRM" is shown by
# "Salesforce", but "Project management" isn't shown by "management".
_GENERIC = {"experience", "knowledge", "skill", "degree", "management", "system", "tool", "year", "ability", "strong",
            "proficiency", "proficient", "certification", "certified", "license", "licence", "software", "platform",
            "data", "service", "process", "practice", "standard", "method", "methodology", "level", "the", "and"}
# A degree the resume shows covers a lower one the JD asks for.
_DEGREE_LEVELS = [
    ("high school", r"high school|ged|diploma"),
    ("associate", r"associate(?:'s)? (?:degree|of)"),
    ("bachelor", r"bachelor|b\.?\s?(?:s|a|sc|e|tech|com|ed)\b\.?|bsn|bfa|beng"),
    ("master", r"master|m\.?\s?(?:s|a|sc|e|tech|com|ed)\b\.?|mba|msn|mfa|mpa|mph|macc|meng|llm"),
    ("doctorate", r"ph\.?\s?d|doctor|j\.?\s?d\b|m\.?\s?d\b"),
]


def _degree_level(text: str) -> int:
    level = -1
    for i, (_name, pattern) in enumerate(_DEGREE_LEVELS):
        if re.search(rf"\b(?:{pattern})", text or "", re.IGNORECASE):
            level = i
    return level


def partly_shown(keyword: str, resume_tokens: List[str], education_text: str = "") -> bool:
    """The resume already shows this, or one of its alternatives (P8.12):
    "OSHA 10 or 30" by "OSHA 30", "Compact/NLC" by "NLC", "Salesforce CRM"
    by "Salesforce", "Bachelor's degree" by a Master's."""
    vocab = set(resume_tokens)
    alts = [a for a in re.split(r"\s+or\s+|/|,", keyword, flags=re.IGNORECASE) if a.strip()]
    prefix = [t for t in tokens(alts[0]) if not t.isdigit()] if alts else []
    for alt in alts:
        alt_tokens = tokens(alt)
        if alt_tokens and all(t.isdigit() for t in alt_tokens):
            alt_tokens = prefix + alt_tokens  # "OSHA 10 or 30": the second option is "OSHA 30"
        if alt_tokens and _contains_seq(resume_tokens, alt_tokens):
            return True
    words = tokens(keyword)
    distinctive = [t for t in words if len(t) >= 3 and t not in _GENERIC and not t.isdigit()]
    if len(words) > 1 and distinctive and distinctive[0] in vocab:
        return True
    asked = _degree_level(keyword)
    return asked >= 0 and _degree_level(education_text) >= asked  # degrees only, never "Boston, MA"


def _wording(kinds: Set[str], listed: str):
    """(question, tick label) for what is being asked."""
    if kinds == {"certification"}:
        return (f"The job asks for {listed}. Do you hold it? Tick what you hold; a licence or certificate goes "
                f"under Certifications.", "Tick the ones you hold:")
    if kinds == {"education"}:
        return f"The job asks for {listed}. Do you have it?", "Tick it if you have it:"
    if kinds == {"soft"}:
        return (f"The job asks for {listed}. Can you give a real example? Tick it only with an example in mind, "
                f"and describe it in your own words.", "Tick what you can show with a real example:")
    return (f"The job asks for {listed}. Have you used it? Tick what you have really used, and say where and how "
            f"in your own words.", "Tick what you have really used:")


def build_questions(job: JobDescription, report: KeywordMatchReport, limit: int = MAX_QUESTIONS,
                    resume_text: Optional[str] = None, education_text: str = "") -> List[GapQuestion]:
    missing = [r for r in report.missing if r.kind in ("hard", "certification", "soft", "education")]
    if resume_text is not None:  # never ask about what the resume already shows (P8.12)
        resume_tokens = tokens(resume_text)
        missing = [r for r in missing if not partly_shown(r.keyword, resume_tokens, education_text)]
    questions: List[Dict] = []
    asked = set()
    for req in sorted(job.requirements, key=lambda r: r.priority != "required"):
        line = tokens(req.text)
        kws = [r for r in missing if r.keyword not in asked and _contains_seq(line, tokens(r.keyword))]
        # "GED" inside "High school diploma or GED" is the same ask.
        kws = [r for r in kws if not any(o is not r and _contains_seq(tokens(o.keyword), tokens(r.keyword))
                                          and len(o.keyword) > len(r.keyword) for o in kws)]
        if not kws:
            continue
        asked.update(r.keyword for r in kws)
        names = [r.keyword for r in kws]
        listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]
        question, label = _wording({r.kind for r in kws}, listed)
        questions.append({
            "requirement": req.text, "priority": req.priority, "keywords": names,
            "weight": sum(r.weight for r in kws), "question": question, "tick_label": label,
            "kinds": {r.keyword: r.kind for r in kws},
        })
    questions.sort(key=lambda q: (q["priority"] != "required", -q["weight"]))
    return [GapQuestion(id=f"gap_{i + 1}", **{k: v for k, v in q.items() if k != "weight"})
            for i, q in enumerate(questions[:limit])]
