"""What the proposal review screen shows (P3.4), as plain functions so the
Streamlit page stays thin and this stays testable: a word-level diff with
JD keywords highlighted, one status badge per proposal, the match rate
broken down by keyword kind, and the keyword gap table."""
import difflib
import html
import re
from typing import Iterable, List, Optional, Tuple

from app.domain.report import KeywordMatchReport

KIND_LABELS = {"hard": "Hard skills", "title": "Job title", "education": "Education",
               "certification": "Certifications", "soft": "Soft skills"}

_DEL_STYLE = "background:#fde2e2;color:#8a1c1c;text-decoration:line-through"
_ADD_STYLE = "background:#dcfce7;color:#14532d"
_KEY_STYLE = "font-weight:700;border-bottom:2px solid #1f4e79"


def _words(text: str) -> List[str]:
    """Words, with each line break kept as its own token (skills are lines)."""
    return re.findall(r"\S+|\n", text or "")


# st.markdown still reads Markdown and LaTeX inside HTML: "$2M to $1M" would
# become math and "*" emphasis. These become numeric entities after escaping.
_MARKDOWN_CHARS = {c: f"&#{ord(c)};" for c in "$*_`[]#~\\|"}


def _escape(word: str) -> str:
    return "".join(_MARKDOWN_CHARS.get(c, c) for c in html.escape(word))


def _keyword_spans(words: List[str], keywords: Iterable[str]) -> set:
    """Indexes of words that are part of a JD keyword (case-insensitive,
    punctuation around a word ignored), multi-word keywords included."""
    clean = [re.sub(r"^[^\w+#.]+|[^\w+#]+$", "", w).lower() for w in words]  # keep ".NET"
    hits = set()
    for kw in keywords or []:
        parts = [p.lower() for p in kw.split()]
        n = len(parts)
        for i in range(len(clean) - n + 1):
            if clean[i:i + n] == parts:
                hits.update(range(i, i + n))
    return hits


def _render(words: List[str], marked: set, style: str, keywords: set) -> str:
    out = []
    for i, w in enumerate(words):
        if w == "\n":
            out.append("<br>")
            continue
        piece = _escape(w)
        if i in keywords:
            piece = f'<span style="{_KEY_STYLE}">{piece}</span>'
        if i in marked:
            piece = f'<span style="{style}">{piece}</span>'
        out.append(piece)
    return " ".join(out).replace(" <br> ", "<br>")


def diff_html(original: str, proposed: str, keywords: Optional[Iterable[str]] = None) -> Tuple[str, str]:
    """(original_html, proposed_html): removed words struck through on the
    left, added words highlighted on the right, JD keywords in bold on both.
    All text is HTML-escaped."""
    a, b = _words(original), _words(proposed)
    removed, added = set(), set()
    matcher = difflib.SequenceMatcher(a=[w.lower() for w in a], b=[w.lower() for w in b], autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op in ("delete", "replace"):
            removed.update(range(i1, i2))
        if op in ("insert", "replace"):
            added.update(range(j1, j2))
    kws = list(keywords or [])
    return (_render(a, removed, _DEL_STYLE, _keyword_spans(a, kws)),
            _render(b, added, _ADD_STYLE, _keyword_spans(b, kws)))


def status_badge(status: Optional[str], validation: Optional[str], changed: bool) -> Tuple[str, str]:
    """(badge, meaning) for one proposal. A failed call or a REJECT verdict
    wins over everything else, since that's what the user must act on."""
    if status in ("llm_unavailable", "llm_error"):
        return "❌ Not rewritten", "the AI call failed; your original text is shown"
    if validation == "REJECT":
        return "⛔ Will be dropped", "fails the fact check; edit it or it won't be used"
    if validation == "NEEDS_CONFIRM":
        return "⚠️ Check", "facts look right but need your confirmation"
    if not changed:
        return "➖ Kept as is", "the AI kept your wording"
    return "✅ Pass", "fact-checked against your resume"


def score_breakdown(report: Optional[KeywordMatchReport]) -> List[dict]:
    """Per keyword kind: how many found and how much of the rate it earns."""
    if report is None or not report.rows:
        return []
    total = sum(r.weight for r in report.rows) or 1.0
    rows = []
    for kind, label in KIND_LABELS.items():
        of_kind = [r for r in report.rows if r.kind == kind]
        if not of_kind:
            continue
        earned = sum(r.weight * r.credit for r in of_kind)  # same sum as the rate
        possible = sum(r.weight for r in of_kind)
        rows.append({"Kind": label, "Found": f"{sum(r.found for r in of_kind)} of {len(of_kind)}",
                     "Points": f"{100 * earned / total:.1f} of {100 * possible / total:.1f}"})
    return rows


def gap_table(report: Optional[KeywordMatchReport], asked: Iterable[str] = ()) -> List[dict]:
    """Missing JD keywords, required and heaviest first, and whether a gap
    question below asks about each."""
    if report is None:
        return []
    asked_lower = {a.lower() for a in asked}
    missing = sorted(report.missing, key=lambda r: (not r.required, -r.weight, r.keyword.lower()))
    return [{"Missing keyword": r.keyword, "Kind": KIND_LABELS.get(r.kind, r.kind),
             "Required": "yes" if r.required else "no",
             "Asked below": "yes" if r.keyword.lower() in asked_lower else "—"} for r in missing]
