"""Shared layout rules for the ATS template (P2.1).

The DOCX and HTML renderers both read these, so the downloaded file and the
browser preview show the same sections, in the same order, under the same
standard headings, with dates written the same way.
"""
import os
import re
from datetime import date
from typing import Dict, List, Optional

from app.analysis.experience import day_first, is_ongoing, parse_month, role_intervals, years_of_experience
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


def section_order_for(resume: Resume, today: Optional[date] = None) -> List[str]:
    """Default order; education moves before experience for someone with
    under about 2 years of dated experience (or no jobs at all). Sections
    kept as they are (P8.3) go before Interests, as "other:<id>"."""
    order = list(DEFAULT_SECTION_ORDER)
    has_dates = bool(role_intervals(resume, today))
    early_career = not resume.experience or (has_dates and years_of_experience(resume, today) < EDUCATION_FIRST_BELOW_YEARS)
    if early_career:
        order.remove("education")
        order.insert(order.index("experience"), "education")
    return _place_kept_sections(resume, order)


def _place_kept_sections(resume: Resume, order: List[str]) -> List[str]:
    """Each kept section goes right after the section it followed in the
    file (before everything if it came first), so "Bar Admissions" stays at
    the top and "Publications" stays after the jobs. Unknown: before Interests."""
    out = list(order)
    last_for: Dict[str, str] = {}
    for sec in resume.other_sections:
        key = f"other:{sec.id}"
        if key in out:
            continue
        anchor = sec.after or ""
        if anchor == "header":
            at = out.index(last_for[anchor]) + 1 if anchor in last_for else 0
        elif anchor in last_for:
            at = out.index(last_for[anchor]) + 1
        elif anchor in out:
            at = out.index(anchor) + 1
        else:
            at = out.index("interests") if "interests" in out else len(out)
        out.insert(at, key)
        last_for[anchor] = key
    return out


def other_section(resume: Resume, key: str):
    """The kept section an "other:<id>" order entry names, or None."""
    sec_id = key.split(":", 1)[1] if key.startswith("other:") else None
    return next((sec for sec in resume.other_sections if sec.id == sec_id), None)


def ordered_sections(resume: Resume, order: List[str]) -> List[str]:
    """`order` plus any kept section it doesn't list yet (an order saved
    before the section existed), so no section is ever left out."""
    return _place_kept_sections(resume, order)


def format_date(value: Optional[str], dayfirst: Optional[bool] = None) -> str:
    """'August 2024' / 'Aug. 2024' / '08/2024' -> 'Aug 2024'; 'Current' ->
    'Present'; a bare year stays a year; anything unrecognised is kept."""
    text = (value or "").strip()
    if not text:
        return ""
    qualifier = re.match(r"^(expected|anticipated|graduating|graduated|class of)\s+", text, re.IGNORECASE)
    if qualifier:  # "Expected May 2026" keeps its word
        return f"{qualifier.group(1).capitalize()} {format_date(text[qualifier.end():], dayfirst)}"
    if is_ongoing(text):
        return "Present"
    lowered = text.lower()
    year_m = re.search(r"(19|20)\d{2}", lowered)
    if not year_m:
        short = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*['’]\d{2}\b", lowered)
        if not short:
            return text
        year, month = parse_month(text, is_end=False, today=date.today())
        return f"{_MONTH_NAMES[month - 1]} {year}"  # "Jan '19" -> "Jan 2019"
    has_month = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?", lowered) \
        or re.search(r"\b(0?[1-9]|1[0-2])\s*[/.-]\s*(19|20)\d{2}", lowered) \
        or re.search(r"\b(19|20)\d{2}-(0[1-9]|1[0-2])\b", lowered) \
        or re.search(r"\b\d{1,2}[/.]\d{1,2}[/.](?:19|20)\d{2}", lowered)
    if not has_month:
        return text if re.search(r"[a-z]", lowered) else year_m.group(0)
    if re.search(r"\b\d{1,2}[/.]\d{1,2}[/.](?:19|20)\d{2}", lowered):
        first = dayfirst if dayfirst is not None else day_first(text)
        if first is None:
            return text  # 05/06/2023 could be May or June: print it as written
        year, month = parse_month(text, is_end=False, today=date.today(), dayfirst=first)
        return f"{_MONTH_NAMES[month - 1]} {year}"
    year, month = parse_month(text, is_end=False, today=date.today())
    return f"{_MONTH_NAMES[month - 1]} {year}"


def date_range(start: Optional[str], end: Optional[str]) -> str:
    """'Jan 2022 – Present'; one side only when the other is missing. Both
    sides read day-first or month-first alike ("01/09/2019 – 31/08/2023")."""
    first = day_first(start, end)
    return DATE_SEPARATOR.join(v for v in (format_date(start, first), format_date(end, first)) if v)


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


# A lone category with one of these names says nothing the SKILLS heading
# doesn't (P9.18: "SKILLS / Skills: Epic, Cerner, ...").
_GENERIC_SKILL_LABELS = {"skills", "skill", "key skills", "core skills", "general", "other", "skills & abilities"}


def skill_label(category: str, skills: Dict[str, List[str]]) -> Optional[str]:
    """The label printed before a skills line, or None when the resume has a
    single, generically named category."""
    if len(skills) == 1 and category.strip().lower().rstrip(":") in _GENERIC_SKILL_LABELS:
        return None
    return category


def output_basename(resume: Resume, company: Optional[str] = None) -> str:
    """First_Last_Resume_<Company>: letters of any script kept ("Lucía
    Fernández" stays, P8.25), unsafe characters replaced, and no company part
    when the JD's company is unknown (was "..._Resume_Company")."""
    safe = lambda s: re.sub(r"[^\w]+", "_", s or "", flags=re.UNICODE).strip("_")
    name = safe(resume.candidate.name if resume.candidate.name != "Candidate" else "")
    company = "" if (company or "").strip().lower() in ("", "company", "target company") else company
    # Each part capped, so a long name or JD company can't exceed the 255-byte
    # file-name limit once ".docx" and the run folder are added (P9.1).
    cap = lambda s, n: s.encode("utf-8")[:n].decode("utf-8", "ignore").rstrip("_")
    parts = [cap(name, 80), "Resume", cap(safe(company), 60)]
    return "_".join(p for p in parts if p)


# Fonts that cover Chinese, Japanese, Korean, Cyrillic and other scripts,
# best first (P8.25: a Chinese-script name rendered blank in the PDF because
# Arial has no glyphs for it). Linux servers: install fonts-noto-cjk.
_FALLBACK_FONTS = [
    ("Noto Sans CJK SC", "NotoSansCJK"), ("Arial Unicode MS", "Arial Unicode"), ("PingFang SC", "PingFang"),
    ("Hiragino Sans GB", "Hiragino Sans GB"), ("Microsoft YaHei", "msyh"), ("Noto Sans", "NotoSans-Regular"),
]
_FONT_DIRS = ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts"),
              "/usr/share/fonts", "/usr/local/share/fonts", "C:/Windows/Fonts"]
_fallback_cache: List[str] = []


def fallback_font() -> str:
    """The best installed font for scripts Arial lacks."""
    if _fallback_cache:
        return _fallback_cache[0]
    found = "Noto Sans CJK SC"
    names = []
    for root in _FONT_DIRS:
        if os.path.isdir(root):
            for _dirpath, _dirs, files in os.walk(root):
                names.extend(files)
    for family, needle in _FALLBACK_FONTS:
        if any(needle.lower() in n.lower() for n in names):
            found = family
            break
    _fallback_cache.append(found)
    return found


def needs_fallback_font(text: str) -> bool:
    """Characters outside Latin / Greek: CJK, Cyrillic, Arabic, Devanagari..."""
    return any(ord(ch) > 0x24F and not 0x2000 <= ord(ch) <= 0x2BFF for ch in text or "")
