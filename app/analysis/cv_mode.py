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


# -- Academic CV (P10.6) -----------------------------------------------------

_APPOINTMENT = re.compile(r"\b(?:professor|postdoc(?:toral)?|lecturer|research (?:fellow|associate|scientist)"
                          r"|visiting (?:scholar|researcher)|reader in|instructor)\b", re.IGNORECASE)
_PUBLICATIONS = re.compile(r"\b(?:publications?|papers|articles|preprints|book chapters|proceedings)\b", re.IGNORECASE)
_YEAR = re.compile(r"(?:19|20)\d{2}")


def is_publications(heading: str) -> bool:
    return bool(_PUBLICATIONS.search(heading or ""))


def experience_heading(resume: Resume) -> str:
    """"Academic Appointments" when every role is an academic one, otherwise
    "Professional Experience" (both read as experience by an ATS)."""
    roles = [r for exp in resume.experience for r in exp.all_roles()]
    if roles and all(_APPOINTMENT.search(r.title or "") for r in roles):
        return "Academic Appointments"
    return "Professional Experience"


def academic_section_order(resume: Resume) -> List[str]:
    """CV order: sections kept from the top of the file, the summary,
    Education, Appointments, then every other kept section (Grants,
    Publications, Teaching, Talks, Service...) in the file's order, then
    skills and the rest."""
    top = [f"other:{s.id}" for s in resume.other_sections if (s.after or "") == "header"]
    rest = [f"other:{s.id}" for s in resume.other_sections if (s.after or "") != "header"]
    return top + ["summary", "education", "experience"] + rest + [
        "projects", "skills", "certifications", "achievements", "interests"]


def move_appointments_from_education(resume: Resume) -> List[str]:
    """An appointment read as education ("Postdoctoral Fellow, Harvard
    University, 2016 – 2019") becomes a job, words unchanged; a degree
    stays. Returns a note per move."""
    from app.domain.resume import Experience
    notes = []
    for edu in list(resume.education):
        title = edu.degree or ""
        if not _APPOINTMENT.search(title) or re.search(r"\b(?:ph\.?d|m\.?s|b\.?s|degree|diploma)\b", title, re.I):
            continue
        start = end = None
        if edu.dates:
            parts = re.split(r"\s*(?:–|—|-|\bto\b)\s*", edu.dates.strip(), maxsplit=1)
            start, end = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], parts[0])
        resume.education.remove(edu)
        resume.experience.append(Experience(id=f"appt_{edu.id}", company=edu.institution, title=title,
                                            location=edu.location, start_date=start, end_date=end,
                                            details=list(edu.details)))
        notes.append(f"Moved \"{title}\" from Education to your appointments (an Academic CV lists it as a job).")
    if notes:
        def newest_first(exp):
            years = _YEAR.findall(f"{exp.end_date or ''} {exp.start_date or ''}")
            ongoing = bool(re.search(r"present|current", exp.end_date or "", re.I))
            return (ongoing, max(map(int, years)) if years else 0)
        resume.experience.sort(key=newest_first, reverse=True)
    return notes


# -- US Federal (P10.7) --------------------------------------------------------

# USAJOBS order for a job's fields; anything else follows, as written.
_FEDERAL_FIELDS = [
    re.compile(r"\b(?:address|street|\d{3,5}\s+\w+\s+(?:st|street|ave|avenue|rd|road|blvd|drive|dr)\b)", re.I),
    re.compile(r"\bhours (?:per|a) week\b|\bhrs/wk\b", re.I),
    re.compile(r"\bsalary\b|\$\s?\d", re.I),
    re.compile(r"\b(?:series|grade)\b|\b(?:GS|GG|WG)-\d", re.I),
    re.compile(r"\bsupervisor\b", re.I),
    re.compile(r"\b(?:may|okay to|ok to|do not|don't) contact\b", re.I),
]
_FIELD_SPLIT = re.compile(r"\s*[|•·;]\s*")


def federal_fields(details: List[str]) -> List[str]:
    """A job's detail lines as USAJOBS fields, one per line and word for word,
    in USAJOBS order (address, hours, salary, series / grade, supervisor,
    may contact), then anything unmatched in its own order. A supervisor's
    phone and "may contact" stay with the supervisor."""
    parts = [p for line in details for p in _FIELD_SPLIT.split(line) if p.strip()]

    def rank(part: str) -> int:
        return next((i for i, field_re in enumerate(_FEDERAL_FIELDS) if field_re.search(part)), len(_FEDERAL_FIELDS))
    return sorted(parts, key=rank)  # stable: same-rank parts keep their order

