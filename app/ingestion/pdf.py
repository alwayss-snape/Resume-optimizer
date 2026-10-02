import os
import re
import logging
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

try:
    import pymupdf as fitz  # PyMuPDF (the "fitz" alias prints a deprecation warning)
    _FITZ_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - runtime dependency may be missing in some environments
    fitz = None
    _FITZ_IMPORT_ERROR = e

from app.ingestion.docx import RawBlock, RawDocument
from app.ingestion.ocr import OCREngine
from app.rendering.document_map import DocumentLocation, DocumentMap

logger = logging.getLogger(__name__)

# Invisible characters that PDF exporters (Google Docs in particular) put
# after bullet glyphs or at line ends. Left in, they leak into bullets,
# education lines and the rendered output.
_INVISIBLE_RE = re.compile("[​‌‍⁠﻿]")
# A run of 3+ spaces inside a line is how some exporters push a right-hand
# column (location, dates) to the margin: "Company            City, Country".
_COLUMN_GAP_RE = re.compile(r"(?<=\S) {3,}(?=\S)")
# "Skills:", "Certifications:", "Tools:" — a labelled line starts a new item.
_LABEL_RE = re.compile(r"^[A-Z][\w&/+ -]{0,30}:\s")

COMMON_SECTIONS = {
    "summary", "professional summary", "profile", "about me", "objective",
    "experience", "work experience", "professional experience", "employment history",
    "skills", "technical skills", "core skills", "education", "projects",
    "certifications", "achievements", "awards", "interests", "certifications & interests",
    "certifications and interests",
}


@dataclass
class _Line:
    """One visual text line with the layout facts the parser needs."""
    text: str
    x0: float
    x1: float
    y0: float
    y1: float
    size: float
    bold: float  # fraction of visible characters set in a bold font
    page: int
    glyph_x0: Optional[float] = None  # set for bullet lines: where the glyph sits


def _clean(text: str) -> str:
    text = _INVISIBLE_RE.sub("", text)
    text = text.replace("\xa0", " ").replace("\xad", "-")
    return text


def _is_bold_span(span: dict) -> bool:
    return bool(span.get("flags", 0) & 16) or "bold" in span.get("font", "").lower()


def _join_wrapped(prev: str, nxt: str) -> str:
    """Join a wrapped line to the one before it. A line that breaks after
    the hyphen of a compound ("end-to-" / "end analytics") rejoins without a
    space, so "end-to-end" reads back intact."""
    if prev.endswith("-") and len(prev) > 1 and prev[-2].isalnum() and nxt[:1].isalnum():
        return f"{prev}{nxt}"
    return f"{prev} {nxt}"


class PdfParser:
    # "●" (U+25CF) is what Google Docs / Word export for a default bullet; the
    # private-use U+F0B7 is Word's Symbol-font bullet.
    # P8.8: "·" (a font without "•" prints a middle dot), arrows and ticks.
    BULLET_PREFIXES = ("•", "●", "◦", "‣", "▸", "▪", "■", "\uf0b7", "·", "∙", "⁃", "➢", "➤", "►", "✓", "❖",
                       "-", "*", "–", "—", "o ")

    def __init__(self):
        self.ocr_engine = OCREngine()

    def _ensure_fitz(self) -> None:
        if fitz is None:
            raise RuntimeError(
                "PyMuPDF is required to parse PDFs but it's not installed. "
                "Install it with `pip install PyMuPDF` (or add `PyMuPDF` to your project dependencies). "
                f"Underlying import error: {_FITZ_IMPORT_ERROR!r}"
            )

    def _merge_wrapped_lines(self, lines: List[str]) -> List[str]:
        """Text-only fallback for joining word-wrapped lines: a line is joined
        onto the previous one only when it starts with a lowercase letter.

        The layout-aware path in `_assemble` uses indentation and the right
        margin first and falls back to this rule, which is conservative on
        its own: it under-merges continuations that start with a capital
        rather than risk swallowing a heading or name.
        """
        merged_lines: List[str] = []
        for line in lines:
            is_bullet_start = line.startswith(self.BULLET_PREFIXES)
            starts_lowercase = bool(line) and line[0].islower()
            if merged_lines and starts_lowercase and not is_bullet_start:
                merged_lines[-1] = _join_wrapped(merged_lines[-1], line).strip()
            else:
                merged_lines.append(line)
        return merged_lines

    # -- layout extraction ----------------------------------------------

    def _page_lines(self, page, page_num: int) -> List[_Line]:
        lines: List[_Line] = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for raw in block["lines"]:
                spans = [s for s in raw["spans"] if s["text"]]
                text = _COLUMN_GAP_RE.sub("\t", _clean("".join(s["text"] for s in spans)).strip())
                if not text.strip():
                    continue
                visible = [(s, len(_clean(s["text"]).replace(" ", ""))) for s in spans]
                total = sum(n for _, n in visible) or 1
                bold = sum(n for s, n in visible if _is_bold_span(s)) / total
                size = max(s["size"] for s in spans)
                x0, y0, x1, y1 = raw["bbox"]
                lines.append(_Line(text, x0, x1, y0, y1, size, bold, page_num))
        return self._attach_right_columns(lines)

    _DATE_OR_PLACE_RE = re.compile(
        r"^(?:(?:[A-Za-z]{3,9}\.?\s+)?(?:19|20)\d{2}\s*(?:[-–—]|to)\s*(?:(?:[A-Za-z]{3,9}\.?\s+)?(?:19|20)\d{2}|"
        r"Present|Current|Now)|[A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+)$")

    def _attach_right_columns(self, lines: List[_Line]) -> List[_Line]:
        """A short, right-aligned run printed on the same row as a left-hand
        line (a location or date column) is appended to that line after a
        tab, which is how the normalizer reads a right-hand column. Only
        right-aligned runs qualify, so a real two-column page layout isn't
        stitched together line by line."""
        if not lines:
            return lines
        right_edge = max(l.x1 for l in lines)
        out: List[_Line] = []
        used = set()

        left_margin = min(l.x0 for l in lines)

        def meta_column(x0: float) -> bool:
            """A tab-stop column: only dates / places start at this x, and
            some line from the left margin runs straight across it (so the
            page is single-column)."""
            at_x = [l for l in lines if abs(l.x0 - x0) < 3]
            crosses = any(l.x0 <= left_margin + 25 and l.x1 > x0 + 10 for l in lines)
            return bool(at_x) and crosses and all(self._DATE_OR_PLACE_RE.search(l.text.strip()) for l in at_x)

        for i, line in enumerate(lines):
            if i in used:
                continue
            for j, other in enumerate(lines):
                if j == i or j in used:
                    continue
                overlap = min(line.y1, other.y1) - max(line.y0, other.y0)
                same_row = overlap > 0.5 * min(line.y1 - line.y0, other.y1 - other.y0)
                # A tab-stop column mid-page ("Title    Jan 2020 - Present")
                # counts too when the run is plainly a date range or a place.
                right_aligned = other.x1 >= right_edge - 60
                # A mid-page tab stop ("Title    Jan 2020 - Present") counts only
                # when everything printed at that x is a date or a place: in a
                # two-column page that x also holds ordinary text.
                tab_column = not right_aligned and meta_column(other.x0)
                min_gap = 20 if right_aligned else 6  # a tab stop can sit close to a bold name
                if (same_row and other.x0 > line.x1 + min_gap and (right_aligned or tab_column)
                        and len(other.text.strip()) <= 40):
                    line.text = f"{line.text.rstrip()}\t{other.text.strip()}"
                    line.x1 = other.x1
                    used.add(j)
                    break
            out.append(line)
        return out

    def _split_bullet(self, text: str) -> Optional[str]:
        """Return the bullet text without its glyph, or None if not a bullet."""
        for prefix in self.BULLET_PREFIXES:
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        return None

    def _continues(self, prev: _Line, line: _Line, right_edge: float) -> bool:
        """Is `line` a word-wrap continuation of the item ending with `prev`?"""
        if line.page != prev.page or "\t" in line.text or "\t" in prev.text:
            return False
        if line.y0 - prev.y1 > line.size:  # a paragraph gap, not a wrap
            return False
        if abs(line.size - prev.size) > 1.5:  # e.g. the name, then the contact line
            return False
        if _LABEL_RE.match(line.text):
            return False
        if prev.glyph_x0 is not None:
            # Inside a bullet, wrapped lines are indented to the bullet text;
            # this holds even when the continuation is set in bold.
            if line.x0 >= prev.glyph_x0 + 6:
                return True
        elif (prev.bold < 0.6 and line.bold < 0.6
              and abs(line.size - prev.size) < 0.6
              and prev.x1 >= 0.8 * right_edge
              and line.x0 <= prev.x0 + 12):
            # A plain paragraph line that ran to the right margin wraps.
            return True
        return bool(line.text) and line.text[0].islower()

    def _assemble(self, lines: List[_Line]) -> List[_Line]:
        """Join continuation lines onto their bullet/paragraph. Each returned
        item keeps the first line's position and the last line's bottom."""
        if not lines:
            return []
        right_edge = max(l.x1 for l in lines)
        items: List[_Line] = []
        for line in lines:
            text = line.text.strip()
            bullet_text = self._split_bullet(text)
            if bullet_text is not None:
                items.append(_Line(bullet_text, line.x0, line.x1, line.y0, line.y1,
                                   line.size, line.bold, line.page, glyph_x0=line.x0))
                continue
            line.text = text
            if items and self._continues(items[-1], line, right_edge):
                prev = items[-1]
                prev.text = _join_wrapped(prev.text, text)
                prev.x1, prev.y1 = line.x1, line.y1
                continue
            items.append(line)
        return items

    @staticmethod
    def _body_size(lines: List[_Line]) -> float:
        sizes = Counter()
        for l in lines:
            sizes[round(l.size, 1)] += len(l.text)
        return sizes.most_common(1)[0][0] if sizes else 0.0

    @staticmethod
    def _is_heading(text: str, item: _Line, body_size: float) -> bool:
        if item.glyph_x0 is not None or "\t" in text:
            return False
        if text.lower().rstrip(":") in COMMON_SECTIONS:
            return True
        letters = [c for c in text if c.isalpha()]
        return (
            bool(letters)
            and len(text) < 40
            and not text.endswith(".")
            and text.upper() == text
            and (item.bold >= 0.6 or item.size >= body_size)
        )

    # -- main entry -----------------------------------------------------

    def parse(self, file_path: str) -> RawDocument:
        self._ensure_fitz()
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at path: {file_path}")

        doc = fitz.open(file_path)
        blocks: List[RawBlock] = []
        document_map = DocumentMap()
        full_text_lines: List[str] = []
        links: List[str] = []

        current_section = "Header"
        block_counter = 0

        page_items: List[List[_Line]] = []
        all_lines: List[_Line] = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            lines = self._page_lines(page, page_num)
            all_lines.extend(lines)
            page_items.append(self._assemble(lines))
            for link in page.get_links():
                uri = link.get("uri")
                if uri and uri not in links:
                    links.append(uri)
        total_text_length = sum(len(l.text.strip()) for l in all_lines)
        body_size = self._body_size(all_lines)

        # The candidate's name is the largest text on page 1, when it is
        # clearly larger than body text. Otherwise the normalizer falls back
        # to "first short header line".
        name_item = None
        if page_items and page_items[0]:
            biggest = max(page_items[0], key=lambda it: it.size)
            if biggest.size >= body_size * 1.3 and biggest.glyph_x0 is None:
                name_item = biggest

        for page_num, items in enumerate(page_items):
            for item in items:
                is_bullet = item.glyph_x0 is not None
                if is_bullet:
                    line = re.sub(r"\s+", " ", item.text).strip()
                else:
                    line = "\t".join(re.sub(r" {2,}", " ", part).strip() for part in item.text.strip().split("\t"))
                if not line:
                    continue

                if item is name_item:
                    block_type = "name"
                elif self._is_heading(line, item, body_size):
                    current_section = line
                    block_type = "heading"
                elif is_bullet:
                    block_type = "bullet"
                else:
                    block_type = "paragraph"

                block_id = f"pdf_p{page_num+1}_b{block_counter:04d}"
                location = DocumentLocation(
                    section=current_section,
                    paragraph_index=block_counter,
                    original_text=line,
                )
                block_counter += 1

                raw_block = RawBlock(
                    id=block_id,
                    block_type=block_type,
                    text=line,
                    section=current_section,
                    location=location,
                    bold=item.bold >= 0.6,
                    font_size=round(item.size, 1),
                )
                blocks.append(raw_block)
                document_map.add_location(block_id, location)
                full_text_lines.append(line)

        # Fallback to OCR if total text extracted is minimal (scanned PDF)
        if total_text_length < 50 and len(doc) > 0:
            logger.info("PDF has minimal text layer; attempting OCR fallback...")
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")
                ocr_text = self.ocr_engine.extract_text_from_image(img_bytes)
                if ocr_text:
                    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
                    for line in lines:
                        block_id = f"ocr_p{page_num+1}_b{block_counter:04d}"
                        block_counter += 1
                        location = DocumentLocation(
                            section=current_section,
                            paragraph_index=block_counter,
                            original_text=line,
                        )
                        raw_block = RawBlock(
                            id=block_id,
                            block_type="paragraph",
                            text=line,
                            section=current_section,
                            location=location,
                        )
                        blocks.append(raw_block)
                        document_map.add_location(block_id, location)
                        full_text_lines.append(line)

        doc.close()

        return RawDocument(
            filename=os.path.basename(file_path),
            blocks=blocks,
            document_map=document_map,
            raw_text="\n".join(full_text_lines),
            links=links,
        )
