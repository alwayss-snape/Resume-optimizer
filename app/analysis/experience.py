"""Years of experience from role date ranges (P1.5), and the page target
that follows from them (P2.3).

Computed in code, never by the LLM: overlapping roles (a promotion listed
next to the earlier title, two part-time jobs) are merged so a month is
counted once.
"""
import re
from datetime import date
from typing import List, Optional, Tuple

from app.domain.resume import Resume

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
# Ways of saying "still in this role" (P8.6: "Till Date", "to date", German
# "heute", Spanish "actualidad" were read as no date at all).
PRESENT_WORDS = ("present", "current", "currently", "now", "today", "ongoing", "till date", "to date",
                 "till now", "date", "heute", "actualidad", "presente", "actual", "aujourd'hui")
_PRESENT = set(PRESENT_WORDS)
_MONTH_NAMES = {"january", "february", "march", "april", "may", "june", "july", "august", "september",
                "october", "november", "december"}
# Seasons -> the month they start in ("Summer 2021" -> Jun 2021).
SEASONS = {"spring": 3, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}


def is_ongoing(end_date: Optional[str]) -> bool:
    """'Present' / 'Current' / 'Till Date' / ... : the role hasn't ended."""
    return (end_date or "").strip().lower().rstrip(".") in _PRESENT


def day_first(*values: Optional[str]) -> Optional[bool]:
    """For "dd/mm/yyyy" vs "mm/dd/yyyy": True when any value can only be
    day-first (31/08/2023), False when any can only be month-first
    (08/31/2023), None when it can't be told."""
    verdict = None
    for value in values:
        m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](?:19|20)\d{2}", value or "")
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > 12 >= b:
                return True
            if b > 12 >= a:
                verdict = False
    return verdict


def parse_month(value: Optional[str], *, is_end: bool, today: date,
                dayfirst: Optional[bool] = None) -> Optional[Tuple[int, int]]:
    """'August 2024' / 'Aug. 2024' / '08/2024' / '31/08/2024' / '2024-08' /
    "Aug '24" / 'Summer 2024' / '2024' / 'Present' -> (year, month).
    A bare year starts in January or ends in December."""
    if not value:
        return None
    text = value.strip().lower().rstrip(".")
    if text in _PRESENT:
        return today.year, today.month
    year_m = re.search(r"(19|20)\d{2}", text)
    if year_m:
        year = int(year_m.group(0))
    else:
        short = re.search(r"['’](\d{2})\b", text)  # "Jan '19"
        if not short:
            return None
        year = 2000 + int(short.group(1))
        if year > today.year + 1:
            year -= 100
    month = next((_MONTHS[w[:3]] for w in re.findall(r"[a-z]+", text) if w[:3] in _MONTHS
                  and (len(w) == 3 or w in _MONTH_NAMES or w[:4] == "sept")), None)
    if month:  # the first month word, not the first word ("Expected May 2026")
        return year, month
    season = re.search(r"\b(spring|summer|fall|autumn|winter)\b", text)
    if season:
        return year, SEASONS[season.group(1)]
    iso = re.search(r"\b(?:19|20)\d{2}-(0[1-9]|1[0-2])\b", text)
    if iso:
        return year, int(iso.group(1))
    full = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](?:19|20)\d{2}", text)
    if full:  # dd/mm/yyyy or mm/dd/yyyy
        a, b = int(full.group(1)), int(full.group(2))
        first = dayfirst if dayfirst is not None else day_first(text)
        month = b if (first or (first is None and a > 12)) else a
        if 1 <= month <= 12:
            return year, month
    num_m = re.search(r"\b(0?[1-9]|1[0-2])\s*[/.-]\s*(19|20)\d{2}", text)
    if num_m:
        return year, int(num_m.group(1))
    return year, (12 if is_end else 1)


def future_dates(resume: Resume, today: Optional[date] = None) -> List[str]:
    """Roles whose start date is after this month (P8.6): usually a typo or a
    misread date, worth a look before tailoring."""
    today = today or date.today()
    now = today.year * 12 + today.month
    out = []
    for exp in resume.experience:
        for role in exp.all_roles():
            start = parse_month(role.start_date, is_end=False, today=today)
            if start and start[0] * 12 + start[1] > now:
                label = " at ".join(v for v in (role.title, exp.company) if v) or "a job"
                out.append(f"{label} starts in the future ({role.start_date})")
    return out


def role_intervals(resume: Resume, today: Optional[date] = None) -> List[Tuple[int, int]]:
    """Each dated role as [start, end] in absolute months (year*12 + month)."""
    today = today or date.today()
    intervals = []
    for exp in resume.experience:
        for role in exp.all_roles():
            first = day_first(role.start_date, role.end_date)
            start = parse_month(role.start_date, is_end=False, today=today, dayfirst=first)
            end = parse_month(role.end_date, is_end=True, today=today, dayfirst=first) if role.end_date else None
            if start is None:
                continue
            end = end or start
            a, b = start[0] * 12 + start[1], end[0] * 12 + end[1]
            if b >= a:
                intervals.append((a, b))
    return intervals


def years_of_experience(resume: Resume, today: Optional[date] = None) -> float:
    """Total months covered by any role (overlaps merged), in years."""
    merged: List[List[int]] = []
    for a, b in sorted(role_intervals(resume, today)):
        if merged and a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    months = sum(b - a + 1 for a, b in merged)
    return round(months / 12.0, 1)


def years_phrase(years: float) -> Optional[str]:
    """How a resume states it: '4+ years', '1 year', or None under 1 year."""
    if years < 1:
        return None
    whole = int(years)
    return f"{whole} year" if whole == 1 and years < 1.5 else f"{whole}+ years"


# Fixed decision: 1 page under 8 years of experience, 2 pages from 8 years.
TWO_PAGES_FROM_YEARS = 8.0


def target_pages(resume: Resume, today: Optional[date] = None) -> int:
    """How many A4 pages the tailored resume should fill."""
    return 2 if years_of_experience(resume, today) >= TWO_PAGES_FROM_YEARS else 1
