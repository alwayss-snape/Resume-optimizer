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
    ("clearance", "Security clearance",
     r"\b(?:security clearance|(?:active |current )?(?:secret|top secret|ts/sci) clearance|clearance required"
     r"|(?:active|current) secret\b)"),
    ("driving", "Driving", r"\b(?:driver'?s licen[cs]e|driving licen[cs]e|valid licen[cs]e to drive|\bcdl\b)"),
    ("licence", "Licence or registration",
     r"\b(?:(?:active|current|valid|unrestricted|state|professional)\s+(?:\w+\s+){0,3}licen[cs]e(?!\s+management)"
     r"|licensed (?:to practice|in)|licensure|board certified|bar (?:membership|admission)|member of the bar"
     r"|active .{0,20}\bbar\b|journeyman (?:\w+ )?licen[cs]e|registered (?:nurse|pharmacist|dietitian))\b"),
    ("physical", "Physical demands",
     r"\b(?:lift(?:ing)? (?:up to )?\d+\s*(?:lbs?|pounds|kg)|stand(?:ing)? for (?:long|extended)|climb (?:ladders|stairs)"
     r"|work at heights|kneel|on your feet)\b"),
    ("schedule", "Schedule and availability",
     r"\b(?:night shifts?|day shifts?|rotating shifts?|\d+-hour shifts?|shift work|work(?:ing)? (?:nights|weekends)"
     r"|nights?,? weekends|weekends(?: and|,)? holidays|overtime|on[- ]call|available (?:to work|for)"
     r"|flexible availability|willing(?:ness)? to travel|travel (?:up to )?\d+\s*%|relocat(?:e|ion))\b"),
    ("specialized", "Specialized experience", r"\b(?:specialized experience|equivalent to (?:the )?gs-\d+)\b"),
    ("language", "Languages",
     r"\b(?:bilingual|fluen(?:t|cy) in|native (?:speaker|level)|(?:english|spanish|french|german|mandarin|hindi"
     r"|arabic|portuguese)(?:/\w+)? (?:a plus|required|fluency|speaking|proficiency)|(?:sehr )?gute deutsch\w*"
     r"|deutsch- und englischkenntnisse)"),
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
            # General experience only ("2 years of acute care experience"); "5+
            # years of Python" is a skill the keyword match already covers.
            if not m or not re.search(r"\d+\s*\+?\s*(?:-\s*\d+\s*)?(?:years|yrs)\s+(?:of\s+)?(?:[\w-]+\s+){0,3}"
                                      r"experience", low):
                continue
            kind = ("years", "Years of experience")
            if years is not None and years > 0:
                need = int(m.group(1))
                auto = "met" if years >= need else "not_met"
                note = f"Your dated roles add up to about {years:g} years; the job asks for {need}+."
        out.append(Condition(id=f"cond_{len(out) + 1}", text=text, kind=kind[0], label=kind[1],
                             priority=req.priority, auto=auto, note=note))
    return out
