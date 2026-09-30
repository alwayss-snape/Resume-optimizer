"""Shared layout rules for the ATS template (P2.1).

The DOCX and HTML renderers both read these, so the downloaded file and the
browser preview show the same sections, in the same order, under the same
standard headings, with dates written the same way.
"""
import re
from datetime import date
from typing import Dict, List, Optional

from app.analysis.experience import parse_month, role_intervals, years_of_experience
from app.domain.resume import Candidate, Resume
from app.domain.resume_document import ResumePresentation

DEFAULT_SECTION_ORDER = ResumePresentation().section_order

# Standard heading names only: ATS parsers look for these words.
SECTION_TITLES = {
    "summary": "Summary",
    "experience": "Work Experience",
    "skills": "Skills",
    "education": "Education",
    "projects": "Projects",
    "certifications": "Certifications",
    "achievements": "Achievements",
    "interests": "Interests",
}

# Under this much experience, education is the stronger evidence and goes
# before work experience.
EDUCATION_FIRST_BELOW_YEARS = 2.0
MAX_SKILL_CATEGORIES = 4
DATE_SEPARATOR = " – "

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_PRESENT_WORDS = {"present", "current", "now", "today", "ongoing", "till date", "to date"}


def section_order_for(resume: Resume, today: Optional[date] = None) -> List[str]:
    """Default order; education moves before experience for someone with
    under about 2 years of dated experience (or no jobs at all)."""
    order = list(DEFAULT_SECTION_ORDER)
    has_dates = bool(role_intervals(resume, today))
    early_career = not resume.experience or (has_dates and years_of_experience(resume, today) < EDUCATION_FIRST_BELOW_YEARS)
    if early_career:
        order.remove("education")
        order.insert(order.index("experience"), "education")
    return order


def format_date(value: Optional[str]) -> str:
    """'August 2024' / 'Aug. 2024' / '08/2024' -> 'Aug 2024'; 'Current' ->
    'Present'; a bare year stays a year; anything unrecognised is kept."""
    text = (value or "").strip()
    if not text:
        return ""
    if text.lower().rstrip(".") in _PRESENT_WORDS:
        return "Present"
    lowered = text.lower()
    year_m = re.search(r"(19|20)\d{2}", lowered)
    if not year_m:
        return text
    has_month = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?", lowered) \
        or re.search(r"\b(0?[1-9]|1[0-2])\s*[/.-]\s*(19|20)\d{2}", lowered)
    if not has_month:
        return text if re.search(r"[a-z]", lowered) else year_m.group(0)
    year, month = parse_month(text, is_end=False, today=date.today())
    return f"{_MONTH_NAMES[month - 1]} {year}"


def date_range(start: Optional[str], end: Optional[str]) -> str:
    """'Jan 2022 – Present'; one side only when the other is missing."""
    return DATE_SEPARATOR.join(v for v in (format_date(start), format_date(end)) if v)


def format_date_text(text: Optional[str]) -> str:
    """A free-text range such as an education's '2016 - 2020' or
    'Aug 2016 to May 2020', written like a role's dates."""
    text = (text or "").strip()
    parts = re.split(r"\s*(?:–|—|-|\bto\b)\s*", text, maxsplit=1)
    if len(parts) == 2 and all(parts):
        return date_range(parts[0], parts[1])
    return format_date(text)


def contact_parts(candidate: Candidate) -> List[str]:
    """email | phone | City, Country | linkedin | github | other links."""
    links = candidate.display_links()
    rank = lambda link: 0 if "linkedin." in link.lower() else 1 if "github." in link.lower() else 2
    ordered_links = sorted(links, key=rank)  # stable: other links keep their order
    return [v for v in (candidate.email, candidate.phone, candidate.location, *ordered_links) if v]


def display_skills(skills: Dict[str, List[str]], max_categories: int = MAX_SKILL_CATEGORIES) -> Dict[str, List[str]]:
    """At most `max_categories` lines: the first ones as they are (JD-relevant
    categories already come first, P1.6), the rest merged into 'Other'."""
    items = [(c, v) for c, v in skills.items() if v]
    if len(items) <= max_categories:
        return dict(items)
    kept = dict(items[:max_categories - 1])
    other: List[str] = []
    for _category, values in items[max_categories - 1:]:
        other.extend(v for v in values if v not in other)
    kept["Other"] = other
    return kept


def output_basename(resume: Resume, company: Optional[str] = None) -> str:
    """First_Last_Resume_<Company>, using only file-name-safe characters."""
    safe = lambda s: re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_")
    name = safe(resume.candidate.name if resume.candidate.name != "Candidate" else "")
    parts = [name, "Resume", safe(company)]
    return "_".join(p for p in parts if p)
