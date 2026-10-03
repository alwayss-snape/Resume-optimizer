"""Content checks on the finished resume (P2.6). Deterministic, no LLM.

These are advice, not errors: nothing is changed automatically. They cover
what recruiters and ATS guides flag most often: bullets per role, bullet
length, pronouns, buzzwords, tense, dates, repeated opening verbs, and how
many bullets carry a number.
"""
import re
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.analysis.experience import is_ongoing, parse_month
from app.analysis.rewriter import FILLER_WORDS, MAX_BULLET_WORDS
from app.domain.resume import Resume

MIN_BULLET_WORDS = 6
BULLETS_CURRENT = (3, 6)   # recent role: 3-6 bullets (template spec)
BULLETS_OLDER = (2, 4)     # older roles: 2-3, one extra tolerated
MIN_METRIC_SHARE = 0.3     # below this, suggest adding real numbers

_PRONOUN_RE = re.compile(r"\b(I|me|my|mine|we|our|us)\b")
BUZZWORDS = tuple(FILLER_WORDS) + (
    "passionate", "go-getter", "hard-working", "hardworking", "team player", "detail-oriented",
    "think outside the box", "self-starter", "best-in-class", "world-class", "responsible for",
    "duties included", "helped with", "worked on",
)
_BUZZ_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in BUZZWORDS) + r")\b", re.IGNORECASE)
_METRIC_RE = re.compile(r"\d|%|\$|€|£|₹")


class LintIssue(BaseModel):
    check: str        # bullets_per_role, length, pronoun, buzzword, tense, dates, repeated_verb, metrics
    where: str        # "Acme Corp", "Acme Corp: 'Built the…'", "resume"
    message: str


class ContentReport(BaseModel):
    issues: List[LintIssue] = Field(default_factory=list)
    bullets: int = 0
    bullets_with_metrics: int = 0

    @property
    def metric_share(self) -> float:
        return self.bullets_with_metrics / self.bullets if self.bullets else 0.0


def _short(text: str, limit: int = 50) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _is_present(value: Optional[str]) -> bool:
    return is_ongoing(value)


def lint(resume: Resume, today: Optional[date] = None) -> ContentReport:
    today = today or date.today()
    report = ContentReport()
    add = lambda check, where, message: report.issues.append(LintIssue(check=check, where=where, message=message))

    sections = [(exp.company or exp.title or "a job", exp.bullets, i == 0, exp.all_roles())
                for i, exp in enumerate(resume.experience)]
    sections += [(p.name or "a project", p.bullets, False, None) for p in resume.projects]

    for label, bullets, current, roles in sections:
        is_job = roles is not None
        if is_job:
            low, high = BULLETS_CURRENT if current else BULLETS_OLDER
            # Earlier roles at the same company (a promotion) add an older
            # role's worth of room.
            high += (BULLETS_OLDER[1] - 1) * max(0, len(roles) - 1)
            if len(bullets) < low:
                add("bullets_per_role", label, f"{len(bullets)} bullet(s); aim for {low}–{high}.")
            elif len(bullets) > high:
                add("bullets_per_role", label, f"{len(bullets)} bullets; {low}–{high} reads better.")
        ongoing = bool(roles) and _is_present(roles[0].end_date)
        openers = {}
        for bullet in bullets:
            text = (bullet.text or "").strip()
            where = f"{label}: \"{_short(text)}\""
            report.bullets += 1
            if _METRIC_RE.search(text):
                report.bullets_with_metrics += 1
            words = text.split()
            if len(words) > MAX_BULLET_WORDS:
                add("length", where, f"{len(words)} words; keep bullets to {MAX_BULLET_WORDS} or fewer.")
            elif len(words) < MIN_BULLET_WORDS:
                add("length", where, "Very short; say what you did and the result.")
            if _PRONOUN_RE.search(text):
                add("pronoun", where, "Drop personal pronouns (I, my, we).")
            buzz = sorted({m.group(1).lower() for m in _BUZZ_RE.finditer(text)})
            if buzz:
                add("buzzword", where, f"Replace vague wording: {', '.join(buzz)}.")
            first = re.sub(r"[^A-Za-z-]", "", words[0]) if words else ""
            if first.lower().endswith("ing") and len(first) > 4:
                add("tense", where, f"Start with an action verb (\"{first}\" reads as a gerund).")
            elif is_job and not ongoing and re.fullmatch(r"[A-Za-z]+[^siu]s", first) and first.lower() not in ("was", "has"):
                add("tense", where, f"Past role: use past tense (\"{first}\").")
            if first:
                openers.setdefault(first.lower(), []).append(text)
        for verb, texts in openers.items():
            if len(texts) > 1:
                add("repeated_verb", label, f"{len(texts)} bullets start with \"{verb.capitalize()}\"; vary the verbs.")

    for exp in resume.experience:
        for role in exp.all_roles():
            where = f"{exp.company or 'a job'}: {role.title or 'role'}"
            start = parse_month(role.start_date, is_end=False, today=today)
            end = parse_month(role.end_date, is_end=True, today=today) if role.end_date else None
            if start is None:
                add("dates", where, "No start date.")
                continue
            if not role.end_date:
                add("dates", where, "No end date (write \"Present\" for a current role).")
            if start > (today.year, today.month):
                add("dates", where, "Start date is in the future.")
            if end is not None and end < start:
                add("dates", where, "End date is before the start date.")

    if report.bullets and report.metric_share < MIN_METRIC_SHARE:
        add("metrics", "resume", f"{report.bullets_with_metrics} of {report.bullets} bullets include a number. Where "
                                 "you have a real one (people helped or trained, budget, volume, time saved) it "
                                 "helps; many roles don't measure everything, and that's fine. Never invent one.")
    return report
