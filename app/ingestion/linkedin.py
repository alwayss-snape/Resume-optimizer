"""LinkedIn "Save to PDF" profile export (P10.1).

The export is a two-column page: a grey sidebar (Contact, Top Skills,
Languages, Certifications, Honors-Awards) and a main column with the name,
headline, location, then Summary, Experience and Education. Read line by
line like a resume, the two columns interleave and the experience layout
(company → title → "April 2022 - Present (2 years 7 months)" → location →
description) has no bullets or right-hand dates for the normalizer to go on.

So this reader takes the layout apart deterministically: the columns are
read separately, page footers ("Page 1 of 2") and LinkedIn's durations are
dropped, and every block it returns carries a `hint` (name, headline,
location, company, job_title, bullet, section:<Name>) so the normalizer
doesn't have to guess. Text is copied from the file; only the separators
around dates are rewritten ("Title<tab>April 2022 - Present").

When anything doesn't fit the pattern, it returns None and the normal PDF
parse runs instead.
"""
import re
from collections import Counter
from dataclasses import replace
from typing import List, Optional, Tuple

from app.ingestion.docx import RawBlock, RawDocument
from app.rendering.document_map import DocumentLocation, DocumentMap

LAYOUT = "linkedin_export"
# Shown on Check details with the other parse notes.
NOTE = ("Read as a LinkedIn profile (Save to PDF): the sidebar and the main column were read separately and "
        "LinkedIn's page numbers and durations left out. Please check the details below.")

_FOOTER_RE = re.compile(r"^Page \d+ of \d+$")
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_WHEN = rf"(?:(?:{_MONTHS}) )?(?:19|20)\d{{2}}"
# "April 2022 - Present (2 years 7 months)", "2015 - 2017 (2 years)"
_RANGE_RE = re.compile(rf"^({_WHEN})\s*[-–]\s*({_WHEN}|Present)(?:\s*\([^)]*\))?$")
# The total time at a company with several roles: "4 years 10 months".
_DURATION_RE = re.compile(r"^(?:\d+ years?(?: \d+ months?)?|\d+ months?|Less than a year)$")
# "Degree, Field · (2013 - 2017)"
_EDU_DATES_RE = re.compile(r"\s*·\s*\(([^)]*)\)\s*$")
_CONTACT_LABEL_RE = re.compile(
    r"\s*\((?:Mobile|Home|Work|LinkedIn|Personal|Company|Portfolio|Blog|Other|RSS Feed)\)$", re.IGNORECASE)

_SIDEBAR_HEADINGS = {"contact", "top skills", "languages", "certifications", "honors-awards", "publications",
                     "patents"}
# Sidebar sections the normalizer has a home for; the rest (Languages,
# Publications, Patents) are kept verbatim under their own heading.
_SIDEBAR_KINDS = {"top skills": "Skills", "certifications": "Certifications", "honors-awards": "Awards"}
# One item per line: a skill or a language never wraps onto a second line
# in the export's narrow column in practice, and two short items must not merge.
_ONE_PER_LINE = {"top skills", "languages"}
_MAIN_KINDS = {"summary": "Summary", "experience": "Experience", "education": "Education"}

_BULLETS = ("•", "●", "◦", "▪", "■", "‣", "▸", "➢", "➤", "►", "✓", "❖", "·", "-", "–", "—", "*")


def _strip_bullet(text: str) -> Optional[str]:
    for glyph in _BULLETS:
        if text.startswith(glyph) and text[len(glyph):len(glyph) + 1] in (" ", ""):
            return text[len(glyph):].strip()
    return None


def _join(prev: str, nxt: str) -> str:
    """A wrapped line rejoins the one above; a break after a hyphen
    ("morgan-" / "ellis-4b7a") rejoins without a space."""
    if prev.endswith("-") and len(prev) > 1 and prev[-2].isalnum() and nxt[:1].isalnum():
        return prev + nxt
    return f"{prev} {nxt}"


def _common(values) -> object:
    counts = Counter()
    for value, weight in values:
        counts[value] += weight
    return counts.most_common(1)[0][0] if counts else None


class _Reader:
    def __init__(self, sidebar, main, links, filename):
        self.sidebar, self.main, self.links, self.filename = sidebar, main, links, filename
        self.blocks: List[RawBlock] = []
        self.document_map = DocumentMap()
        self.body_size = _common((round(l.size, 1), len(l.text)) for l in main)
        self.body_color = _common((l.color, len(l.text)) for l in main)
        self.main_right = max(l.x1 for l in main)
        self.side_right = max(l.x1 for l in sidebar)

    # -- output ------------------------------------------------------------

    def emit(self, text: str, hint: str, section: str, block_type: str = "paragraph", line=None) -> None:
        text = text.strip()
        if not text:
            return
        index = len(self.blocks)
        page = (line.page + 1) if line is not None else 1
        block_id = f"pdf_p{page}_b{index:04d}"
        location = DocumentLocation(section=section, paragraph_index=index, original_text=text)
        self.blocks.append(RawBlock(
            id=block_id, block_type=block_type, text=text, section=section, location=location,
            bold=bool(line is not None and line.bold >= 0.6),
            font_size=round(line.size, 1) if line is not None else None, hint=hint,
        ))
        self.document_map.add_location(block_id, location)

    # -- wrapped lines -----------------------------------------------------

    @staticmethod
    def _wraps(prev, line, right: float, may_wrap: bool) -> bool:
        """Is `line` the wrapped continuation of `prev`? The export wraps a
        description back to the column's left edge with no indent, so the
        test is whether the line's first word would have fitted after
        `prev`: if it would, the line break was the author's."""
        text = line.text.strip()
        if _strip_bullet(text) is not None:
            return False
        if abs(line.size - prev.size) > 0.6 or abs(line.bold - prev.bold) > 0.5:
            return False
        if line.page == prev.page and line.y0 - prev.y1 > 0.6 * line.size:
            return False  # a paragraph gap
        if text[:1].islower():
            return True
        if not may_wrap:
            return False
        first = text.split()[0]
        word = (line.x1 - line.x0) * len(first) / max(len(text), 1)
        # A margin past the widest line seen: the column's true edge is at
        # least that far right, and two short items must not merge.
        return prev.x1 + 0.28 * line.size + word > right + 0.5 * line.size

    def items(self, lines, right: float, may_wrap: bool = True) -> List[Tuple[str, object]]:
        out: List[Tuple[str, object]] = []
        last = None
        for line in lines:
            text = line.text.strip()
            if out and self._wraps(last, line, right, may_wrap):
                out[-1] = (_join(out[-1][0], text), out[-1][1])
            else:
                out.append((text, line))
            last = line
        return out

    # -- sidebar -----------------------------------------------------------

    def sidebar_sections(self) -> Optional[List[Tuple[object, List]]]:
        # Headings are set like the known ones ("Contact", "Top Skills"), so
        # an unfamiliar one ("Volunteer Work") is found by its size.
        known = [l.size for l in self.sidebar if l.text.strip().lower() in _SIDEBAR_HEADINGS]
        heading_size = min(known) - 0.3
        sections: List[Tuple[object, List]] = []
        for line in self.sidebar:
            text = line.text.strip()
            if line.size >= heading_size or text.lower() in _SIDEBAR_HEADINGS:
                sections.append((line, []))
            elif sections:
                sections[-1][1].append(line)
            else:
                return None  # sidebar text before any heading: not the layout we know
        return sections

    def contact_items(self, lines) -> List[str]:
        """Email, phone, profile and site URLs, without LinkedIn's
        "(Mobile)" / "(LinkedIn)" labels. A URL broken across lines is
        rejoined."""
        items: List[str] = []
        for line in lines:
            text = line.text.strip()
            prev = items[-1] if items else ""
            if prev and not prev.endswith(")") and " " not in prev and "@" not in prev:
                items[-1] = _join(prev, text)
            else:
                items.append(text)
        return [_CONTACT_LABEL_RE.sub("", item).strip() for item in items if item.strip()]

    # -- main column ---------------------------------------------------------

    def is_main_heading(self, line) -> bool:
        return line.size >= self.body_size * 1.3 and len(line.text.strip()) < 40

    def is_grey(self, line) -> bool:
        return line.color != self.body_color

    def experience(self, lines, section: str) -> bool:
        """Company → [total duration] → title → dates → [location] →
        description, for each role. False when a line doesn't fit."""
        big = lambda l: l.size >= self.body_size + 0.75  # noqa: E731
        run: List = []           # title / company lines waiting for their dates
        open_company = None      # (text, line) of a company whose first role is next
        last_location = None
        i = 0
        while i < len(lines):
            line = lines[i]
            text = line.text.strip()
            if big(line):
                run.append(line)
                i += 1
                continue
            if _DURATION_RE.match(text) and run:
                open_company = (" ".join(l.text.strip() for l in run), run[0])
                run = []
                i += 1
                continue
            m = _RANGE_RE.match(text)
            if m:
                if not run:
                    return False
                if len(run) >= 2:
                    # A new company: its lines are set in the first line's style.
                    head = [run[0]]
                    for l in run[1:]:
                        if abs(l.size - run[0].size) < 0.3 and abs(l.bold - run[0].bold) < 0.5:
                            head.append(l)
                        else:
                            break
                    if len(head) == len(run):
                        head = run[:1]
                    open_company = (" ".join(l.text.strip() for l in head), head[0])
                    run = run[len(head):]
                title = " ".join(l.text.strip() for l in run)
                dates = f"{m.group(1)} - {m.group(2)}"
                location = None
                nxt = lines[i + 1] if i + 1 < len(lines) else None
                if nxt is not None and self._is_location(nxt, line):
                    location = nxt.text.strip()
                    i += 1
                if open_company is not None:
                    company, company_line = open_company
                    self.emit(f"{company}\t{location}" if location else company, "company", section,
                              line=company_line)
                    self.emit(f"{title}\t{dates}", "job_title", section, line=run[0])
                    last_location, open_company = location, None
                else:
                    # Another role at the same company: its place only when it differs.
                    where = f"{location} {dates}" if location and location != last_location else dates
                    self.emit(f"{title}\t{where}", "job_title", section, line=run[0])
                run = []
                i += 1
                continue
            if run or not self.blocks or self.blocks[-1].hint not in ("job_title", "bullet"):
                return False  # a description with no role above it
            j = i
            while j < len(lines) and not big(lines[j]) and not _RANGE_RE.match(lines[j].text.strip()):
                j += 1
            for item, first in self.items(lines[i:j], self.main_right):
                self.emit(_strip_bullet(item) or item, "bullet", section, block_type="bullet", line=first)
            i = j
        return not run and open_company is None

    def _is_location(self, line, dates_line) -> bool:
        """The grey place line under a role's dates. Without colours to go
        on, a short place-like line ("Pune, Maharashtra, India", "Remote")."""
        text = line.text.strip()
        if _RANGE_RE.match(text) or line.size >= self.body_size + 0.75:
            return False
        if dates_line.color != self.body_color:
            return line.color == dates_line.color
        return (len(text.split()) <= 6 and not text.endswith(".") and not re.search(r"\d", text)
                and ("," in text or re.search(r"\b(?:Area|Region|Remote)\b", text) is not None))

    def education(self, lines, section: str) -> None:
        big = lambda l: l.size >= self.body_size + 0.75  # noqa: E731
        i = 0
        while i < len(lines):
            if big(lines[i]):
                self.emit(lines[i].text, "text", section, line=lines[i])
                i += 1
                continue
            j = i
            while j < len(lines) and not big(lines[j]):
                j += 1
            for item, first in self.items(lines[i:j], self.main_right):
                self.emit(_EDU_DATES_RE.sub(lambda m: "\t" + m.group(1), item), "text", section, line=first)
            i = j

    # -- the whole page ----------------------------------------------------

    def read(self) -> Optional[RawDocument]:
        name_line = max((l for l in self.main if l.page == 0), key=lambda l: l.size)
        headings = [i for i, l in enumerate(self.main) if l is not name_line and self.is_main_heading(l)]
        if not headings:
            return None
        sides = self.sidebar_sections()
        if sides is None:
            return None

        # Header: name, headline, location, then one contact line from the sidebar.
        header = [l for l in self.main[:headings[0]] if l is not name_line]
        self.emit(name_line.text, "name", "Header", block_type="name", line=name_line)
        grey = [l for l in header if self.is_grey(l)]
        plain = [l for l in header if not self.is_grey(l)]
        for text, first in self.items(plain, self.main_right):
            self.emit(text, "headline", "Header", line=first)
        for line in grey[:1]:
            self.emit(line.text, "location", "Header", line=line)
        for line in grey[1:]:
            self.emit(line.text, "text", "Header", line=line)
        contact = next((lines for head, lines in sides if head.text.strip().lower() == "contact"), [])
        items = self.contact_items(contact)
        if items:
            self.emit(" | ".join(items), "text", "Header", line=contact[0])

        # Main column sections.
        bounds = headings + [len(self.main)]
        for start, end in zip(bounds, bounds[1:]):
            head = self.main[start]
            text = head.text.strip()
            kind = _MAIN_KINDS.get(text.lower(), "Other")
            self.emit(text, f"section:{kind}", text, block_type="heading", line=head)
            lines = self.main[start + 1:end]
            if kind == "Experience":
                if not self.experience(lines, text):
                    return None
            elif kind == "Education":
                self.education(lines, text)
            else:
                for item, first in self.items(lines, self.main_right):
                    self.emit(item, "text", text, line=first)

        # Sidebar sections after the main column, Contact already used.
        for head, lines in sides:
            key = head.text.strip().lower()
            if key == "contact" or not lines:
                continue
            text = head.text.strip()
            self.emit(text, f"section:{_SIDEBAR_KINDS.get(key, 'Other')}", text, block_type="heading", line=head)
            for item, first in self.items(lines, self.side_right, may_wrap=key not in _ONE_PER_LINE):
                self.emit(item, "text", text, line=first)

        return RawDocument(
            filename=self.filename, blocks=self.blocks, document_map=self.document_map,
            raw_text="\n".join(b.text for b in self.blocks), links=list(self.links), layout=LAYOUT,
        )


def read_linkedin_export(pages: List[List], links: List[str], page_width: float,
                         filename: str) -> Optional[RawDocument]:
    """The export as a RawDocument, or None when the file isn't one (or
    doesn't read cleanly as one). `pages`: each page's text lines, before
    any right-column stitching."""
    if not pages or not pages[0] or not page_width:
        return None
    first = pages[0]
    name_line = max(first, key=lambda l: l.size)
    sizes = sorted(l.size for l in first)
    # The name is the biggest text, at the main column's left edge, well
    # right of the page margin.
    if name_line.size < 1.6 * sizes[len(sizes) // 2] or name_line.x0 < 0.25 * page_width:
        return None
    split = name_line.x0 - 4
    lines = [replace(l) for page in pages for l in page]
    footers = [l for l in lines if _FOOTER_RE.match(l.text.strip())]
    body = [l for l in lines if not _FOOTER_RE.match(l.text.strip())]
    sidebar = [l for l in body if l.x1 <= split]
    main = [l for l in body if l.x0 >= split]
    if len(sidebar) + len(main) != len(body) or not sidebar or not main:
        return None  # a line runs across both columns: a one-column page
    if max(l.x1 for l in sidebar) > 0.38 * page_width:
        return None
    if not any(l.page == 0 and l.text.strip().lower() in _SIDEBAR_HEADINGS for l in sidebar):
        return None
    profile = any("linkedin.com/in/" in u.lower() for u in links) or any(
        "linkedin.com/in/" in l.text.lower() for l in sidebar)
    if not (footers or profile):
        return None
    order = lambda l: (l.page, round(l.y0, 1), l.x0)  # noqa: E731
    return _Reader(sorted(sidebar, key=order), sorted(main, key=order), links, filename).read()
