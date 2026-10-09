"""Achievements with context (P11.15): where and when, from evidence only.

An achievement line ("Won an internal hackathon with Route Pilot.") often
leaves out where it happened. When the line names exactly one job's project
heading or company, the job's company is added; a year is added only when
that project's own lines (or the job's dates) give exactly one. The result
is a proposal the user ticks on Review, never applied unseen, and no AI call
is made: every word added is copied from the resume or the notes.
"""
import re
from typing import Dict, List, Optional

from app.analysis.change_proposal import ChangeProposal
from app.domain.resume import Resume

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# A year written as a date, not a count ("in 2024", "Mar 2024", "(2024)", "2023 – 2024";
# never "2000 stores").
_MONTHS = r"jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december"
DATED_YEAR_RE = re.compile(
    r"\b(?:in|since|during|from|until|by|q[1-4]|" + _MONTHS + r")\.?,?\s+((?:19|20)\d{2})\b"
    r"|\(((?:19|20)\d{2})\)"
    r"|\b((?:19|20)\d{2})\s*[–-]\s*(?:(?:19|20)\d{2}|present)\b", re.I)
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.&-]*")
_SMALL = {"the", "and", "for", "with", "of", "a", "an", "to", "in", "on", "at", "by", "pvt", "ltd", "inc", "llc",
          "limited", "company", "group", "india", "private"}


def _words(text: str) -> List[str]:
    return [w.lower().strip(".") for w in _WORD_RE.findall(text or "")]


def _named(name: str, text_words: List[str], line: str = "", heading: bool = False) -> bool:
    """`name` (a company or project heading) is named in the text: all its
    content words, in order, as a run of the text's words. A one-word
    heading never counts ("Pilot", "Analytics" are ordinary words); a
    one-word company must be written with its own capitals."""
    want = [w for w in _words(name) if w not in _SMALL]
    if not want:
        return False
    if len(want) == 1:
        if heading or len(want[0]) < 4:
            return False
        return bool(re.search(r"\b" + re.escape(name.strip()) + r"\b", line))
    n = len(want)
    plain = [w for w in text_words if w not in _SMALL]
    return any(plain[i:i + n] == want for i in range(len(plain) - n + 1))


def _year_of(texts: List[str]) -> Optional[str]:
    years = {a or b or c for t in texts for a, b, c in DATED_YEAR_RE.findall(t or "")}
    return years.pop() if len(years) == 1 else None


def context_for(line: str, resume: Resume, notes: Dict[str, List[str]]) -> Optional[str]:
    """"Northwind, 2025", "Northwind", "2025" or None, for one achievement."""
    return _match(line, resume, notes)[0]


def _match(line: str, resume: Resume, notes: Dict[str, List[str]]):
    """(context or None, the job it came from or None)."""
    words = _words(line)
    matches = []  # (job, project heading or None)
    for exp in resume.experience:
        heads = [g for g, _ in exp.bullet_groups() if g]
        hit = [g for g in dict.fromkeys(heads) if _named(g, words, line, heading=True)]
        if hit:
            matches.append((exp, hit[0]))
        elif exp.company and _named(exp.company, words, line):
            matches.append((exp, None))
    if len({id(e) for e, _ in matches}) != 1:
        return None, None  # no job, or more than one: not ours to guess
    exp, group = matches[0]
    # Not when the line already names the company, even in part ("Northwind hackathon").
    named = {w for w in _words(exp.company or "") if w not in _SMALL and len(w) >= 4} & set(words)
    where = exp.company if exp.company and not named else None
    when = None
    if not YEAR_RE.search(line):
        if group:
            when = _year_of([group, *(b.text for b in exp.bullets if b.group == group),
                             *notes.get(f"{exp.id}::{group}", [])])
        if not when:
            roles = exp.all_roles()
            spans = [YEAR_RE.findall(f"{r.start_date or ''} {r.end_date or ''}") for r in roles]
            years = {y for s in spans for y in s}
            ended = all(not re.search(r"present|current|now|till", (r.end_date or "present"), re.I) for r in roles)
            if ended and len(years) == 1:
                when = years.pop()
    parts = [p for p in (where, when) if p]
    return (", ".join(parts) if parts else None), exp


def with_context(line: str, context: str) -> str:
    body = line.rstrip()
    end = "." if body.endswith(".") else ""
    return f"{body.rstrip('.').rstrip()} ({context}){end}"


def achievement_proposals(resume: Resume, notes: Dict[str, List[str]]) -> List[ChangeProposal]:
    """One proposal per achievement that gains context; targets "achievement::<index>"."""
    out = []
    for i, line in enumerate(resume.achievements):
        context, exp = _match(line, resume, notes)
        if not context or f"({context})" in line:
            continue
        # The job's own dates, for the fact check (they aren't evidence lines).
        dates = [f"{r.start_date or ''} {r.end_date or ''}".strip() for r in exp.all_roles()]
        out.append(ChangeProposal(
            target_semantic_id=f"achievement::{i}", kind="achievement", original_text=line,
            proposed_text=with_context(line, context), allowed_facts=[d for d in dates if d], status="ok",
            opt_in=True,  # starts unticked: the user adds it on Review, never applied unseen
            rationale="Adds where and when it happened, from your own resume and notes."))
    return out


def added_context(original: str, proposed: str) -> Optional[str]:
    """The parenthetical a proposal adds to its achievement, or None when
    anything else changed (then the fact check treats it like any rewrite)."""
    m = re.fullmatch(r"(.*?)\s*\(([^()]*)\)(\.?)\s*", proposed or "")
    if not m:
        return None
    if m.group(1).rstrip(".").strip() != (original or "").strip().rstrip(".").strip():
        return None
    return m.group(2).strip()
