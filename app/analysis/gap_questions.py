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
# Words are matched in any case; short forms ("B.S.", "MSc", "MBA") only as
# written, so "be" / "me" / "MS SQL" aren't degrees (Stage I review).
_DEGREE_LEVELS = [
    ("high school", r"(?i:high school|\bged\b|diploma)"),
    ("associate", r"(?i:associate(?:'s)? (?:degree|of))"),
    ("bachelor", r"(?i:bachelor)|\bB\.\s?(?:S|A|Sc|E|Tech|Com|Ed)\b\.?|\b(?:BS|BA|BSc|BEng|BSN|BFA|BTech|BCom)\b"),
    ("master", r"(?i:master)|\bM\.\s?(?:S|A|Sc|E|Tech|Com|Ed)\b\.?|\b(?:MS|MA|MSc|MBA|MSN|MFA|MPA|MPH|MAcc|MEng|LLM)\b"),
    ("doctorate", r"(?i:ph\.?\s?d|doctor)|\bM\.\s?D\b"),
]


def _degree_level(text: str) -> int:
    level = -1
    for i, (_name, pattern) in enumerate(_DEGREE_LEVELS):
        if re.search(pattern, text or ""):
            level = i
    return level


# A vendor or product name with a generic tail: "Salesforce CRM" is shown by
# "Salesforce", but "Spring Boot" isn't shown by "Spring 2019".
_GENERIC_TAIL = {"crm", "platform", "suite", "software", "tool", "system", "certification", "certificate",
                 "license", "licence", "program", "framework", "library", "studio", "cloud"}
_CREDENTIAL_LINE = re.compile(r"\b(?:certif\w*|licen[cs]\w*|credential\w*|registered|board[- ]certified)\b", re.I)


def infer_kind(keyword: str, kind: str, requirement: str = "") -> str:
    """The keyword's kind when the JD analysis couldn't tell (offline it
    calls everything "hard"): a degree or a credential (Stage I review)."""
    if kind not in ("hard", "", None):
        return kind
    from app.analysis.skills_tailor import is_trait
    if is_trait(keyword):  # "Fast learner" labelled hard by the JD analysis (P9.12)
        return "soft"
    if re.search(r"(?i:degree|bachelor|master|diploma|\bged\b|ph\.?\s?d|doctorate)", keyword):
        return "education"
    if re.search(r"(?i:certif|licen[cs]|credential)", keyword):
        return "certification"
    if re.fullmatch(r"[A-Z][A-Z0-9-]{1,6}", keyword.strip()) and _CREDENTIAL_LINE.search(requirement or ""):
        return "certification"  # "CCRN" in "BLS and ACLS certification required; CCRN preferred"
    return kind or "hard"


def partly_shown(keyword: str, resume_tokens: List[str], education_text: str = "", kind: str = "") -> bool:
    """The resume already shows this, or one of its alternatives (P8.12):
    "OSHA 10 or 30" by "OSHA 30", "Compact/NLC" by "NLC", "Salesforce CRM"
    by "Salesforce", "Bachelor's degree" by a Master's."""
    vocab = set(resume_tokens)
    # "Compact/NLC" and "English/Spanish" are alternatives; "lockout/tagout" is one thing.
    slash = "/" if re.search(r"[A-Z]", keyword) else r"(?!)"
    alts = [a for a in re.split(r"\s+or\s+|" + slash + "|,", keyword, flags=re.IGNORECASE) if a.strip()]
    prefix = [t for t in tokens(alts[0]) if not t.isdigit()] if alts else []
    for alt in alts:
        alt_tokens = tokens(alt)
        if alt_tokens and all(t.isdigit() for t in alt_tokens):
            alt_tokens = prefix + alt_tokens  # "OSHA 10 or 30": the second option is "OSHA 30"
        if alt_tokens and _contains_seq(resume_tokens, alt_tokens):
            return True
    written = re.findall(r"[^\W_]+", keyword.lower())  # before aliasing: "CRM", not its expansion
    if len(written) > 1 and all(w.rstrip("s") in _GENERIC_TAIL for w in written[1:]) and \
            _contains_seq(resume_tokens, tokens(written[0])):
        return True
    if kind != "education":
        return False
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
    line_of = {}
    for req in job.requirements:
        for r in missing:
            if r.keyword not in line_of and _contains_seq(tokens(req.text), tokens(r.keyword)):
                line_of[r.keyword] = req.text
    kind_of = {r.keyword: infer_kind(r.keyword, r.kind, line_of.get(r.keyword, "")) for r in missing}
    if resume_text is not None:  # never ask about what the resume already shows (P8.12)
        resume_tokens = tokens(resume_text)
        missing = [r for r in missing if not partly_shown(r.keyword, resume_tokens, education_text, kind_of[r.keyword])]
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
        question, label = _wording({kind_of[r.keyword] for r in kws}, listed)
        questions.append({
            "requirement": req.text, "priority": req.priority, "keywords": names,
            "weight": sum(r.weight for r in kws), "question": question, "tick_label": label,
            "kinds": {r.keyword: kind_of[r.keyword] for r in kws},
        })
    questions.sort(key=lambda q: (q["priority"] != "required", -q["weight"]))
    return [GapQuestion(id=f"gap_{i + 1}", **{k: v for k, v in q.items() if k != "weight"})
            for i, q in enumerate(questions[:limit])]
