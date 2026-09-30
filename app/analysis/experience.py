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
_PRESENT = {"present", "current", "now", "today", "ongoing"}


def is_ongoing(end_date: Optional[str]) -> bool:
    """'Present' / 'Current' / 'Now' / ... : the role hasn't ended."""
    return (end_date or "").strip().lower().rstrip(".") in _PRESENT


def parse_month(value: Optional[str], *, is_end: bool, today: date) -> Optional[Tuple[int, int]]:
    """'August 2024' / 'Aug. 2024' / '08/2024' / '2024' / 'Present' -> (year, month).
    A bare year starts in January or ends in December."""
    if not value:
        return None
    text = value.strip().lower()
    if text in _PRESENT:
        return today.year, today.month
    year_m = re.search(r"(19|20)\d{2}", text)
    if not year_m:
        return None
    year = int(year_m.group(0))
    month_m = re.search(r"\b([a-z]{3})[a-z]*\.?", text)
    if month_m and month_m.group(1) in _MONTHS:
        return year, _MONTHS[month_m.group(1)]
    num_m = re.search(r"\b(0?[1-9]|1[0-2])\s*[/.-]\s*(19|20)\d{2}", text)
    if num_m:
        return year, int(num_m.group(1))
    return year, (12 if is_end else 1)


def role_intervals(resume: Resume, today: Optional[date] = None) -> List[Tuple[int, int]]:
    """Each dated role as [start, end] in absolute months (year*12 + month)."""
    today = today or date.today()
    intervals = []
    for exp in resume.experience:
        for role in exp.all_roles():
            start = parse_month(role.start_date, is_end=False, today=today)
            end = parse_month(role.end_date, is_end=True, today=today) if role.end_date else None
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
