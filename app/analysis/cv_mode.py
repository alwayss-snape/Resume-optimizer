"""CV mode (P10.5): a standard resume, an Academic CV or a US Federal
(USAJOBS-style) resume, suggested from signals in the resume and the JD.

Deterministic, with the words that decided it as evidence; the user confirms
or changes it. Academic and federal have no page cap.
"""
import re
from dataclasses import dataclass, field
from typing import List

from app.domain.resume import Resume

CV_MODES = {
    "standard": "Standard resume",
    "academic": "Academic CV",
    "federal": "US Federal (USAJOBS)",
}
NO_PAGE_CAP = ("academic", "federal")

_FEDERAL_JD = re.compile(r"\bUSAJOBS\b|\b(?:GS|GG)-\d{4}-\d{1,2}\b|\bGS-\d{1,2}\b|\bspecialized experience\b"
                         r"|\bKSAs?\b|\bOPM\b", re.IGNORECASE)
_FEDERAL_RESUME = [
    re.compile(r"\b\d{2}\s*hours per week\b", re.IGNORECASE),
    re.compile(r"\bsupervisor\s*:", re.IGNORECASE),
    re.compile(r"\b(?:GS|GG|WG)-\d{4}-\d{1,2}\b|\bhighest grade\b", re.IGNORECASE),
    re.compile(r"\bveterans?'? preference\b", re.IGNORECASE),
    re.compile(r"\bU\.?S\.? citizen(?:ship)?\b", re.IGNORECASE),
]
_ACADEMIC_JD = re.compile(r"\btenure[- ]track\b|\bfaculty (?:position|member)\b|\b(?:assistant|associate) professor\b"
                          r"|\bpostdoctoral (?:position|fellow(?:ship)?|researcher)\b|\bteaching statement\b"
                          r"|\bresearch statement\b|\blecturer\b", re.IGNORECASE)
_ACADEMIC_TITLE = re.compile(r"\b(?:professor|postdoc(?:toral)?|lecturer|research fellow|reader in)\b", re.IGNORECASE)
_ACADEMIC_HEADING = re.compile(r"\b(?:publications|academic appointments|grants|invited talks|conference presentations"
                               r"|research interests|teaching)\b", re.IGNORECASE)
_ORCID = re.compile(r"\bORCID\b", re.IGNORECASE)


@dataclass
class ModeGuess:
    mode: str
    evidence: List[str] = field(default_factory=list)  # what decided it, for the user

    @property
    def label(self) -> str:
        return CV_MODES[self.mode]

    def model_dump(self) -> dict:
        return {"mode": self.mode, "label": self.label, "evidence": self.evidence}


def _resume_text(resume: Resume) -> str:
    parts = list(resume.candidate.details)
    for exp in resume.experience:
        parts += [exp.title or "", exp.company or "", *exp.details]
        parts += [r.title for r in exp.roles]
    return "\n".join(p for p in parts if p)


def suggest_cv_mode(resume: Resume, jd_text: str) -> ModeGuess:
    """Federal: a federal JD (USAJOBS, a GS series), or two federal fields in
    the resume (hours per week, supervisor, series / grade, veterans'
    preference, citizenship). Academic: two academic signals in the resume
    (an appointment title, Publications / Grants / Teaching sections, ORCID),
    or one with an academic JD (faculty, tenure-track, postdoc). Otherwise
    the standard resume."""
    text = _resume_text(resume)
    jd = _FEDERAL_JD.search(jd_text or "")
    fed = [m.group(0) for p in _FEDERAL_RESUME if (m := p.search(text))]
    if jd or len(fed) >= 2:
        return ModeGuess("federal", ([f"the job says “{jd.group(0)}”"] if jd else []) + [f"“{f}”" for f in fed])

    signals = []
    title = next((m.group(0) for exp in resume.experience for r in exp.all_roles()
                  if (m := _ACADEMIC_TITLE.search(r.title or ""))), None)
    if title:
        signals.append(f"a “{title}” role")
    headings = [s.heading for s in resume.other_sections if _ACADEMIC_HEADING.search(s.heading or "")]
    if headings:
        signals.append("sections " + ", ".join(f"“{h}”" for h in headings[:3]))
    orcid = _ORCID.search("\n".join(resume.candidate.details + resume.candidate.links + [resume.candidate.headline or ""]))
    if orcid:
        signals.append("an ORCID iD")
    ajd = _ACADEMIC_JD.search(jd_text or "")
    if len(signals) >= 2 or (signals and ajd):
        return ModeGuess("academic", ([f"the job says “{ajd.group(0)}”"] if ajd else []) + signals)
    return ModeGuess("standard", [])


def apply_cv_mode(presentation, mode: str):
    """Set the mode on the presentation. Federal resumes are US documents
    with MM/YYYY dates, whatever the region (Decisions table)."""
    from app.analysis.region import apply_region
    presentation.cv_mode = mode if mode in CV_MODES else "standard"
    if presentation.cv_mode == "federal":
        apply_region(presentation, "us")
    return presentation
