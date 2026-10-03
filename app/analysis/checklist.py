"""Job conditions that aren't keywords (P8.20).

A state licence, a security clearance, night shifts, lifting 50 lbs, a
driver's licence, a second language, the right to work, or a minimum
number of years: an ATS keyword match can't show these, and a resume often
shouldn't list them. They become a checklist the user ticks once, shown
apart from the match rate, and never added to the resume or the score.
Built in code from the JD's own requirement lines (verbatim), no LLM.
"""
import re
from datetime import date
from typing import List, Optional

from pydantic import BaseModel

from app.analysis.experience import years_of_experience
from app.domain.job import JobDescription
from app.domain.resume import Resume

# (kind, label, pattern) in order: the first match names the condition.
_KINDS = [
    ("authorization", "Right to work",
     r"\b(?:authori[sz]ed to work|work authori[sz]ation|citizenship|u\.?s\.? citizen|visa sponsorship|right to work)\b"),
    ("clearance", "Security clearance", r"\b(?:security clearance|clearance|secret|ts/sci)\b"),
    ("driving", "Driving", r"\b(?:driver'?s licen[cs]e|driving licen[cs]e|valid licen[cs]e to drive|cdl)\b"),
    ("licence", "Licence or registration",
     r"\b(?:licen[cs]e|licensure|licensed|registration|registered|board certified|bar (?:membership|admission)"
     r"|member of the bar|active .{0,20}bar)\b"),
    ("physical", "Physical demands",
     r"\b(?:lift(?:ing)? (?:up to )?\d+\s*(?:lbs?|pounds|kg)|stand(?:ing)? for|climb|work at heights|kneel|on your feet)\b"),
    ("schedule", "Schedule and availability",
     r"\b(?:shifts?|nights?|weekends?|holidays?|overtime|on[- ]call|availability|available to|travel|relocat\w*|rotating)\b"),
    ("specialized", "Specialized experience", r"\b(?:specialized experience|equivalent to (?:the )?gs-\d+)\b"),
    ("language", "Languages",
     r"\b(?:bilingual|fluent|fluency|native speaker|english|spanish|french|german|mandarin|hindi|arabic|portuguese"
     r"|deutsch|englisch)\b"),
]
_YEARS_RE = re.compile(r"(?:minimum (?:of )?|at least )?(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|yrs)\b", re.IGNORECASE)


class Condition(BaseModel):
    id: str
    text: str  # the JD line, verbatim
    kind: str
    label: str
    priority: str = "required"
    # "met" / "not_met" when code can tell (years), else None: the user ticks it.
    auto: Optional[str] = None
    note: Optional[str] = None


def build_checklist(job: JobDescription, resume: Optional[Resume] = None,
                    today: Optional[date] = None) -> List[Condition]:
    out: List[Condition] = []
    years = years_of_experience(resume, today) if resume is not None else None
    for req in job.requirements:
        text = req.text
        low = text.lower()
        kind = next(((k, label) for k, label, pattern in _KINDS if re.search(pattern, low)), None)
        auto = note = None
        if kind is None:
            m = _YEARS_RE.search(text)
            if not m or not re.search(r"experience|years in|years of", low):
                continue
            kind = ("years", "Years of experience")
            if years is not None and years > 0:
                need = int(m.group(1))
                auto = "met" if years >= need else "not_met"
                note = f"Your dated roles add up to about {years:g} years; the job asks for {need}+."
        out.append(Condition(id=f"cond_{len(out) + 1}", text=text, kind=kind[0], label=kind[1],
                             priority=req.priority, auto=auto, note=note))
    return out
